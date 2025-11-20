"""Convenience script for running parameter sweeps and exporting results."""
from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Iterable, List
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.commands import DEFAULT_COMMANDS, load_command_sequence
from sim.experiment import run_many_experiments
from sim.types import AttackMode, Mode, SimulationConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run replay-attack parameter sweeps")
    parser.add_argument("--runs", type=int, default=200, help="Monte Carlo runs per condition")
    parser.add_argument("--num-legit", type=int, default=20, help="Legitimate transmissions per run")
    parser.add_argument("--num-replay", type=int, default=100, help="Replay attempts per run (post-attack mode)")
    parser.add_argument("--modes", nargs="+", 
                        default=[Mode.NO_DEFENSE.value, Mode.ROLLING_MAC.value, Mode.WINDOW.value, Mode.CHALLENGE.value],
                        help="Modes to include in the sweep outputs")
    parser.add_argument("--p-loss-values", type=float, nargs="*", default=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
                        help="Packet-loss probabilities to evaluate")
    parser.add_argument("--p-reorder-values", type=float, nargs="*", default=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
                        help="Packet-reorder probabilities to evaluate")
    parser.add_argument("--window-values", type=int, nargs="*", default=[1, 3, 5, 7, 9, 15, 20],
                        help="Window sizes to evaluate (applies to window mode)")
    parser.add_argument("--window-size-base", type=int, default=5,
                        help="Window size used in modes that rely on a fixed window during p_loss sweeps")
    parser.add_argument("--fixed-p-loss", type=float, default=None,
                        help="Fixed p_loss value for p_reorder sweep (default: 0.10 for isolating reorder effect)")
    parser.add_argument("--fixed-p-reorder", type=float, default=None,
                        help="Fixed p_reorder value for p_loss sweep (default: 0.0 for isolating loss effect)")
    parser.add_argument("--window-p-loss", type=float, default=0.15,
                        help="Fixed p_loss value for window size sweep (default: 0.15 for moderate stress)")
    parser.add_argument("--window-p-reorder", type=float, default=0.15,
                        help="Fixed p_reorder value for window size sweep (default: 0.15 for moderate stress)")
    parser.add_argument("--attack-mode", choices=[mode.value for mode in AttackMode], default=AttackMode.POST_RUN.value,
                        help="Replay scheduling strategy for all sweeps")
    parser.add_argument("--inline-attack-prob", type=float, default=0.3,
                        help="Inline attack probability per legitimate frame (if inline mode)")
    parser.add_argument("--inline-attack-burst", type=int, default=1,
                        help="Max inline replay attempts per legitimate frame")
    parser.add_argument("--p-loss-output", type=str, default="results/p_loss_sweep.json",
                        help="Where to write the p_loss sweep JSON")
    parser.add_argument("--p-reorder-output", type=str, default="results/p_reorder_sweep.json",
                        help="Where to write the p_reorder sweep JSON")
    parser.add_argument("--window-output", type=str, default="results/window_sweep.json",
                        help="Where to write the window sweep JSON")
    parser.add_argument("--commands-file", type=str, help="Optional command trace used for all sweeps")
    parser.add_argument("--seed", type=int, help="Global RNG seed for reproducibility")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    command_sequence = load_command_sequence(args.commands_file) if args.commands_file else None

    try:
        attack_mode = AttackMode(args.attack_mode)
    except ValueError as exc:
        valid = ", ".join(mode.value for mode in AttackMode)
        raise SystemExit(f"Unsupported attack mode '{args.attack_mode}'. Valid options: {valid}") from exc

    base_config = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        attack_mode=attack_mode,
        num_legit=args.num_legit,
        num_replay=args.num_replay,
        command_sequence=command_sequence,
        command_set=DEFAULT_COMMANDS,
        rng_seed=args.seed,
        shared_key="sim_shared_key",
        window_size=args.window_size_base,
        inline_attack_probability=args.inline_attack_prob,
        inline_attack_burst=args.inline_attack_burst,
    )

    requested_modes = _parse_modes(args.modes)

    # Apply fixed parameters for each sweep
    fixed_p_reorder_for_loss = args.fixed_p_reorder if args.fixed_p_reorder is not None else 0.0
    fixed_p_loss_for_reorder = args.fixed_p_loss if args.fixed_p_loss is not None else 0.10

    p_loss_records = _sweep_p_loss(base_config, requested_modes, args.p_loss_values, args.runs, args.seed, fixed_p_reorder_for_loss)
    p_reorder_records = _sweep_p_reorder(base_config, requested_modes, args.p_reorder_values, args.runs, args.seed, fixed_p_loss_for_reorder)
    window_records = _sweep_window(base_config, requested_modes, args.window_values, args.runs, args.seed, args.window_p_loss, args.window_p_reorder)

    _write_json(Path(args.p_loss_output), p_loss_records)
    _write_json(Path(args.p_reorder_output), p_reorder_records)
    _write_json(Path(args.window_output), window_records)

    print(f"Saved p_loss sweep: {args.p_loss_output}")
    print(f"Saved p_reorder sweep: {args.p_reorder_output}")
    print(f"Saved window sweep: {args.window_output}")


def _parse_modes(raw_modes: List[str]) -> List[Mode]:
    modes: List[Mode] = []
    for token in raw_modes:
        try:
            modes.append(Mode(token))
        except ValueError as exc:
            valid = ", ".join(mode.value for mode in Mode)
            raise SystemExit(f"Unsupported mode '{token}'. Valid options: {valid}") from exc
    return modes


def _sweep_p_loss(
    base_config: SimulationConfig,
    modes: List[Mode],
    p_loss_values: Iterable[float],
    runs: int,
    seed: int | None,
    fixed_p_reorder: float = 0.0,
) -> List[dict]:
    """
    Sweep packet loss rate while keeping reordering fixed.
    
    Default: p_reorder=0.0 to isolate packet loss effect.
    """
    records: List[dict] = []
    for value in p_loss_values:
        config = dataclasses.replace(base_config, p_loss=value, p_reorder=fixed_p_reorder)
        stats = run_many_experiments(config, modes=modes, runs=runs, seed=seed)
        for entry in stats:
            record = entry.as_dict()
            record.update({"sweep_type": "p_loss", "sweep_value": value})
            records.append(record)
    return records


def _sweep_p_reorder(
    base_config: SimulationConfig,
    modes: List[Mode],
    p_reorder_values: Iterable[float],
    runs: int,
    seed: int | None,
    fixed_p_loss: float = 0.10,
) -> List[dict]:
    """
    Sweep packet reordering rate while keeping loss fixed.
    
    Default: p_loss=0.10 (typical IoT environment) to isolate reordering effect
    following single-variable control principle.
    """
    records: List[dict] = []
    for value in p_reorder_values:
        config = dataclasses.replace(base_config, p_reorder=value, p_loss=fixed_p_loss)
        stats = run_many_experiments(config, modes=modes, runs=runs, seed=seed)
        for entry in stats:
            record = entry.as_dict()
            record.update({"sweep_type": "p_reorder", "sweep_value": value})
            records.append(record)
    return records


def _sweep_window(
    base_config: SimulationConfig,
    modes: List[Mode],
    window_values: Iterable[int],
    runs: int,
    seed: int | None,
    stress_p_loss: float = 0.15,
    stress_p_reorder: float = 0.15,
) -> List[dict]:
    """
    Sweep window size under moderate network stress.
    
    Default: p_loss=0.15, p_reorder=0.15 creates realistic challenging conditions
    where the tradeoff between security and usability is most observable.
    """
    records: List[dict] = []
    
    for value in window_values:
        config = dataclasses.replace(
            base_config, 
            window_size=value,
            p_loss=stress_p_loss,
            p_reorder=stress_p_reorder
        )
        stats = run_many_experiments(config, modes=modes, runs=runs, seed=seed)
        for entry in stats:
            record = entry.as_dict()
            record.update({"sweep_type": "window", "sweep_value": value})
            records.append(record)
    return records


def _write_json(path: Path, payload: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
