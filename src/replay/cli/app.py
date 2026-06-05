"""Argparse-based CLI for the new Replay product surface."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import yaml

from replay.contracts import LabValidationSpec, SimulationSpec, SweepSpec
from replay.core import AttackMode, Mode
from replay.core.presets import load_preset
from replay.services import (
    DeviceProfile,
    build_demo_artifacts,
    compare_sim_vs_hardware,
    recommend,
    run_sweep,
    simulate_batch,
    validate_lab_run,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="replay", description="Replay research platform CLI")
    subparsers = parser.add_subparsers(dest="group", required=True)

    sim_parser = subparsers.add_parser("sim", help="Simulation commands")
    sim_subparsers = sim_parser.add_subparsers(dest="sim_command", required=True)

    run_parser = sim_subparsers.add_parser("run", help="Run a simulation batch")
    _add_simulation_arguments(run_parser)
    run_parser.add_argument("--output-json", type=str, help="Optional path to dump aggregate stats")

    sweep_parser = sim_subparsers.add_parser("sweep", help="Run a parameter sweep")
    _add_simulation_arguments(sweep_parser)
    sweep_parser.add_argument(
        "--sweep-type",
        choices=["p_loss", "p_reorder", "window", "mac_tag_bits"],
        required=True,
    )
    sweep_parser.add_argument("--values", nargs="+", required=True, help="Sweep values")
    sweep_parser.add_argument("--fixed-p-loss", type=float)
    sweep_parser.add_argument("--fixed-p-reorder", type=float)
    sweep_parser.add_argument("--output-json", type=str, help="Optional path to dump sweep results")

    artifact_parser = subparsers.add_parser("artifacts", help="Static artifact commands")
    artifact_subparsers = artifact_parser.add_subparsers(dest="artifact_command", required=True)
    artifact_subparsers.add_parser("build-demo", help="Build manifest and demo artifact files")

    lab_parser = subparsers.add_parser("lab", help="Physical experiment commands")
    lab_subparsers = lab_parser.add_subparsers(dest="lab_command", required=True)
    validate_parser = lab_subparsers.add_parser("validate", help="Run or load validation")
    _add_lab_arguments(validate_parser)
    lab_subparsers.add_parser("compare", help="Load latest sim-vs-hardware comparison")

    advise_parser = subparsers.add_parser("advise", help="Recommend defense parameters")
    advise_parser.add_argument("--profile", required=True, help="Preset/profile YAML path")

    return parser


def _add_simulation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset", type=str, help="Benchmark preset name or YAML path")
    parser.add_argument("--modes", nargs="+", choices=[mode.value for mode in Mode])
    parser.add_argument("--runs", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--p-loss", type=float)
    parser.add_argument("--p-reorder", type=float)
    parser.add_argument("--window-size", type=int)
    parser.add_argument("--num-legit", type=int)
    parser.add_argument("--num-replay", type=int)
    parser.add_argument(
        "--attack-mode",
        choices=[mode.value for mode in AttackMode],
    )
    parser.add_argument("--mac-length", type=int)
    parser.add_argument("--mac-tag-bits", type=int)
    parser.add_argument("--shared-key", type=str)
    parser.add_argument("--attacker-record-loss", type=float)
    parser.add_argument("--inline-attack-probability", type=float)
    parser.add_argument("--inline-attack-burst", type=int)
    parser.add_argument("--challenge-nonce-bits", type=int)
    parser.add_argument("--channel-model", choices=["iid", "gilbert_elliott", "trace"])
    parser.add_argument("--loss-good", type=float)
    parser.add_argument("--loss-bad", type=float)
    parser.add_argument("--risk-high", type=float)
    parser.add_argument("--paired", action="store_true")


def _add_lab_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-loopback", action="store_true")
    parser.add_argument("--no-quick", action="store_true")
    parser.add_argument("--no-goal-check", action="store_true")
    parser.add_argument("--loss-samples", type=str, default="0.0")
    parser.add_argument("--output-path", type=str)
    parser.add_argument("--extra-arg", action="append", default=[])


def _simulation_spec_from_args(args: argparse.Namespace) -> SimulationSpec:
    spec = load_preset(args.preset) if args.preset else SimulationSpec()
    updates: dict[str, object] = {}
    if args.modes is not None:
        updates["modes"] = [Mode(mode) for mode in args.modes]
    for arg_name, field_name in [
        ("runs", "runs"),
        ("seed", "seed"),
        ("p_loss", "p_loss"),
        ("p_reorder", "p_reorder"),
        ("window_size", "window_size"),
        ("num_legit", "num_legit"),
        ("num_replay", "num_replay"),
        ("mac_length", "mac_length"),
        ("mac_tag_bits", "mac_tag_bits"),
        ("shared_key", "shared_key"),
        ("attacker_record_loss", "attacker_record_loss"),
        ("inline_attack_probability", "inline_attack_probability"),
        ("inline_attack_burst", "inline_attack_burst"),
        ("challenge_nonce_bits", "challenge_nonce_bits"),
        ("channel_model", "channel_model"),
        ("loss_good", "loss_good"),
        ("loss_bad", "loss_bad"),
        ("risk_high", "risk_high"),
    ]:
        value = getattr(args, arg_name, None)
        if value is not None:
            updates[field_name] = value
    if args.attack_mode is not None:
        updates["attack_mode"] = AttackMode(args.attack_mode)
    if getattr(args, "paired", False):
        updates["paired"] = True
    payload = spec.model_dump()
    payload.update(updates)
    return SimulationSpec.model_validate(payload)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.group == "sim" and args.sim_command == "run":
        payload = simulate_batch(
            _simulation_spec_from_args(args),
            show_progress=True,
        ).model_dump(mode="json")
        _maybe_write_json(args.output_json, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.group == "sim" and args.sim_command == "sweep":
        values = [
            int(value) if args.sweep_type in {"window", "mac_tag_bits"} else float(value)
            for value in args.values
        ]
        payload_points = [
            point.model_dump(mode="json")
            for point in run_sweep(
                SweepSpec(
                    sweep_type=args.sweep_type,
                    values=values,
                    simulation=_simulation_spec_from_args(args),
                    fixed_p_loss=args.fixed_p_loss,
                    fixed_p_reorder=args.fixed_p_reorder,
                ),
                show_progress=True,
            )
        ]
        _maybe_write_json(args.output_json, payload_points)
        print(json.dumps(payload_points, indent=2, ensure_ascii=False))
        return 0

    if args.group == "artifacts":
        manifest = build_demo_artifacts()
        print(json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return 0

    if args.group == "lab" and args.lab_command == "validate":
        spec = LabValidationSpec(
            loopback=not args.no_loopback,
            quick=not args.no_quick,
            goal_check=not args.no_goal_check,
            loss_samples=[float(value) for value in args.loss_samples.split(",") if value],
            output_path=args.output_path,
            extra_args=args.extra_arg,
        )
        print(
            json.dumps(
                validate_lab_run(spec).model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.group == "lab" and args.lab_command == "compare":
        print(
            json.dumps(
                compare_sim_vs_hardware().model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.group == "advise":
        profile = _device_profile_from_yaml(args.profile)
        print(json.dumps(asdict(recommend(profile)), indent=2, ensure_ascii=False))
        return 0

    parser.error("Unsupported command")
    return 2


def _maybe_write_json(path: str | None, payload: object) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _device_profile_from_yaml(path_or_name: str) -> DeviceProfile:
    path = Path(path_or_name)
    if not path.exists():
        preset_spec = load_preset(path_or_name)
        return DeviceProfile(
            commands=list(preset_spec.command_set or []),
            command_risk=dict(preset_spec.command_risk or {}),
            p_loss=preset_spec.loss_good,
            p_reorder=preset_spec.p_reorder,
            ram_budget_bytes=128,
            max_latency_ticks=2,
            seed=preset_spec.seed,
        )

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid profile YAML: {path}")
    channel = dict(payload.get("channel") or {})
    p_loss_value = payload["p_loss"] if "p_loss" in payload else channel.get("loss_good", 0.0)
    return DeviceProfile(
        commands=list(payload.get("commands") or []),
        command_risk={
            str(key): float(value)
            for key, value in dict(payload.get("risk") or {}).items()
        },
        p_loss=float(p_loss_value),
        p_reorder=float(payload.get("p_reorder", 0.05)),
        ram_budget_bytes=int(payload.get("ram_budget_bytes", 128)),
        max_latency_ticks=int(payload.get("max_latency_ticks", 2)),
        target_asr=float(payload.get("target_asr", 0.05)),
        seed=payload.get("seed"),
    )
