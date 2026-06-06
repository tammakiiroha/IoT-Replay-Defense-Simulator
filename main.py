from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from replay.contracts import SimulationSpec
from replay.core import (
    DEFAULT_ATTACK_MODE,
    DEFAULT_ATTACKER_RECORD_LOSS,
    DEFAULT_CHALLENGE_NONCE_BITS,
    DEFAULT_COMMANDS,
    DEFAULT_G_HARD,
    DEFAULT_INLINE_ATTACK_BURST,
    DEFAULT_INLINE_ATTACK_PROBABILITY,
    DEFAULT_MAC_LENGTH,
    DEFAULT_NUM_LEGIT,
    DEFAULT_NUM_REPLAY,
    DEFAULT_P_LOSS,
    DEFAULT_P_REORDER,
    DEFAULT_RUNS,
    DEFAULT_SHARED_KEY,
    DEFAULT_WINDOW_SIZE,
    Mode,
    load_command_sequence,
)
from replay.services import simulate_batch

VALID_MODE_VALUES = [mode.value for mode in Mode]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay attack simulation driver")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=VALID_MODE_VALUES,
        default=VALID_MODE_VALUES,
        help="Modes to evaluate",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help="Monte Carlo runs per mode",
    )
    parser.add_argument(
        "--num-legit",
        type=int,
        default=DEFAULT_NUM_LEGIT,
        help="Legitimate transmissions per run",
    )
    parser.add_argument(
        "--num-replay",
        type=int,
        default=DEFAULT_NUM_REPLAY,
        help="Replay attempts per run",
    )
    parser.add_argument(
        "--p-loss",
        type=float,
        default=DEFAULT_P_LOSS,
        help="Packet loss probability",
    )
    parser.add_argument(
        "--p-reorder",
        type=float,
        default=DEFAULT_P_REORDER,
        help="Packet reordering probability",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=DEFAULT_WINDOW_SIZE,
        help="Window size for window mode",
    )
    parser.add_argument(
        "--g-hard",
        type=int,
        default=DEFAULT_G_HARD,
        help="Forward-jump gate; bigger jumps need authenticated resync (sw_resync/hsw_cr)",
    )
    parser.add_argument(
        "--mac-length",
        type=int,
        default=DEFAULT_MAC_LENGTH,
        help="Truncated MAC length (hex chars)",
    )
    parser.add_argument("--seed", type=int, default=None, help="Global RNG seed")
    parser.add_argument(
        "--target-commands",
        nargs="+",
        help="Specific commands for attacker to replay",
    )
    parser.add_argument(
        "--commands-file",
        type=str,
        help="Path to a newline-delimited command trace captured from real hardware",
    )
    parser.add_argument(
        "--shared-key",
        type=str,
        default=DEFAULT_SHARED_KEY,
        help="Shared secret key",
    )
    parser.add_argument(
        "--attacker-loss",
        type=float,
        default=DEFAULT_ATTACKER_RECORD_LOSS,
        help="Attacker recording loss probability",
    )
    parser.add_argument("--output-json", type=str, help="Optional path to dump aggregate stats")
    parser.add_argument(
        "--attack-mode",
        choices=["post", "inline"],
        default=DEFAULT_ATTACK_MODE.value,
        help="Replay scheduling strategy",
    )
    parser.add_argument(
        "--inline-attack-prob",
        type=float,
        default=DEFAULT_INLINE_ATTACK_PROBABILITY,
        help="Inline replay probability",
    )
    parser.add_argument(
        "--inline-attack-burst",
        type=int,
        default=DEFAULT_INLINE_ATTACK_BURST,
        help="Max consecutive inline replays",
    )
    parser.add_argument(
        "--challenge-nonce-bits",
        type=int,
        default=DEFAULT_CHALLENGE_NONCE_BITS,
        help="Nonce length in bits",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable progress display")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _raise_cli_validation_error(errors: list[str]) -> None:
    if not errors:
        return

    print("\nParameter Validation Failed:\n", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    print("\nPlease fix the errors and try again.\n", file=sys.stderr)
    raise SystemExit(1)


def _format_spec_validation_error(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "Invalid parameter")
        errors.append(f"{location}: {message}" if location else str(message))
    return errors


def _load_command_sequence_from_args(commands_file: str | None) -> list[str] | None:
    if not commands_file:
        return None

    try:
        return load_command_sequence(commands_file)
    except (FileNotFoundError, ValueError) as exc:
        _raise_cli_validation_error([str(exc)])
        return None


def _build_simulation_spec(args: argparse.Namespace) -> SimulationSpec:
    try:
        return SimulationSpec(
            modes=args.modes,
            runs=args.runs,
            seed=args.seed,
            p_loss=args.p_loss,
            p_reorder=args.p_reorder,
            window_size=args.window_size,
            g_hard=args.g_hard,
            num_legit=args.num_legit,
            num_replay=args.num_replay,
            attack_mode=args.attack_mode,
            mac_length=args.mac_length,
            shared_key=args.shared_key,
            attacker_record_loss=args.attacker_loss,
            inline_attack_probability=args.inline_attack_prob,
            inline_attack_burst=args.inline_attack_burst,
            challenge_nonce_bits=args.challenge_nonce_bits,
            target_commands=args.target_commands,
            command_sequence=_load_command_sequence_from_args(args.commands_file),
            command_set=list(DEFAULT_COMMANDS),
        )
    except ValidationError as exc:
        _raise_cli_validation_error(_format_spec_validation_error(exc))
        raise AssertionError("unreachable") from exc


def validate_parameters(args: argparse.Namespace) -> None:
    errors: list[str] = []

    if not 0.0 <= args.p_loss <= 1.0:
        errors.append(f"Invalid p_loss: {args.p_loss}. Must be between 0.0 and 1.0")
    if not 0.0 <= args.p_reorder <= 1.0:
        errors.append(f"Invalid p_reorder: {args.p_reorder}. Must be between 0.0 and 1.0")
    if not 0.0 <= args.attacker_loss <= 1.0:
        errors.append(f"Invalid attacker_loss: {args.attacker_loss}. Must be between 0.0 and 1.0")
    if not 0.0 <= args.inline_attack_prob <= 1.0:
        errors.append(
            f"Invalid inline_attack_prob: {args.inline_attack_prob}. "
            "Must be between 0.0 and 1.0"
        )

    if args.runs <= 0:
        errors.append(f"Invalid runs: {args.runs}. Must be positive integer")
    if args.num_legit < 0:
        errors.append(f"Invalid num_legit: {args.num_legit}. Must be non-negative integer")
    if args.num_replay < 0:
        errors.append(f"Invalid num_replay: {args.num_replay}. Must be non-negative integer")
    if args.window_size < 0:
        errors.append(f"Invalid window_size: {args.window_size}. Must be non-negative integer")
    elif "window" in args.modes and args.window_size == 0:
        errors.append("Invalid window_size: must be positive when WINDOW mode is enabled")
    if args.mac_length <= 0:
        errors.append(f"Invalid mac_length: {args.mac_length}. Must be positive integer")
    if args.inline_attack_burst <= 0:
        errors.append(
            f"Invalid inline_attack_burst: {args.inline_attack_burst}. "
            "Must be positive integer"
        )
    if args.challenge_nonce_bits <= 0:
        errors.append(
            f"Invalid challenge_nonce_bits: {args.challenge_nonce_bits}. "
            "Must be positive integer"
        )
    if args.seed is not None and args.seed < 0:
        errors.append(f"Invalid seed: {args.seed}. Must be non-negative integer or None")

    _raise_cli_validation_error(errors)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    validate_parameters(args)
    spec = _build_simulation_spec(args)
    batch = simulate_batch(spec, show_progress=not args.quiet)
    rows = [entry.model_dump(mode="json") for entry in batch.results]
    _print_table(rows)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n✓ Saved aggregate metrics to {output_path}")

    print(f"\n__JSON_RESULT__:{json.dumps(rows, ensure_ascii=False)}")


def _print_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("No stats to display")
        return

    headers = [
        ("Mode", 12),
        ("Runs", 6),
        ("Attack", 8),
        ("p_loss", 8),
        ("p_reorder", 10),
        ("Window", 8),
        ("Avg Legit", 12),
        ("Std Legit", 12),
        ("Avg Attack", 12),
        ("Std Attack", 12),
    ]
    line = " ".join(name.ljust(width) for name, width in headers)
    print(line)
    print("-" * len(line))
    for row in rows:
        legit_rate = _coerce_float(row["avg_legit_rate"])
        legit_std = _coerce_float(row["std_legit_rate"])
        attack_rate = _coerce_float(row["avg_attack_rate"])
        attack_std = _coerce_float(row["std_attack_rate"])
        values = [
            str(row["mode"]),
            str(row["runs"]),
            str(row["attack_mode"]),
            f"{_coerce_float(row['p_loss']):.2f}",
            f"{_coerce_float(row['p_reorder']):.2f}",
            str(row["window_size"]),
            f"{legit_rate * 100:.2f}%",
            f"{legit_std * 100:.2f}%",
            f"{attack_rate * 100:.2f}%",
            f"{attack_std * 100:.2f}%",
        ]
        print(" ".join(value.ljust(width) for value, (_, width) in zip(values, headers)))


def _coerce_float(value: object) -> float:
    if isinstance(value, (float, int, str)):
        return float(value)
    raise TypeError(f"Expected a numeric table cell, got {type(value).__name__}")


if __name__ == "__main__":
    main()
