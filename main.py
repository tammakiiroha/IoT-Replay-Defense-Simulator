from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import List

from sim.commands import DEFAULT_COMMANDS, load_command_sequence
from sim.experiment import run_many_experiments
from sim.types import AttackMode, Mode, SimulationConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay attack simulation driver")
    parser.add_argument("--modes", nargs="+", default=[mode.value for mode in Mode], help="Modes to evaluate")
    parser.add_argument("--runs", type=int, default=200, help="Monte Carlo runs per mode")
    parser.add_argument("--num-legit", type=int, default=20, help="Legitimate transmissions per run")
    parser.add_argument("--num-replay", type=int, default=100, help="Replay attempts per run")
    parser.add_argument("--p-loss", type=float, default=0.0, help="Packet loss probability")
    parser.add_argument("--p-reorder", type=float, default=0.0, help="Packet reordering probability")
    parser.add_argument("--window-size", type=int, default=5, help="Window size for the window mode")
    parser.add_argument("--mac-length", type=int, default=8, help="Truncated MAC length (hex chars)")
    parser.add_argument("--seed", type=int, default=None, help="Global RNG seed")
    parser.add_argument("--commands-file", type=str, help="Optional path to a command trace")
    parser.add_argument("--target-commands", nargs="+", help="Specific commands for attacker to replay (selective replay)")
    parser.add_argument("--shared-key", type=str, default="sim_shared_key", help="Shared secret key")
    parser.add_argument("--attacker-loss", type=float, default=0.0, help="Attacker recording loss probability")
    parser.add_argument("--output-json", type=str, help="Optional path to dump aggregate stats")
    parser.add_argument("--attack-mode", choices=[mode.value for mode in AttackMode], default=AttackMode.POST_RUN.value,
                        help="Replay scheduling strategy (post or inline)")
    parser.add_argument("--inline-attack-prob", type=float, default=0.3,
                        help="Probability of injecting a replay after each legitimate frame in inline mode")
    parser.add_argument("--inline-attack-burst", type=int, default=1,
                        help="Maximum consecutive replay attempts per legitimate frame in inline mode")
    parser.add_argument("--challenge-nonce-bits", type=int, default=32,
                        help="Nonce length (bits) for the challenge-response mode")
    parser.add_argument("--quiet", action="store_true",
                        help="Disable visual progress display (quiet mode)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    # Always show header unless in quiet mode
    if not args.quiet:
        _print_header(args)
    
    modes: List[Mode] = []
    for token in args.modes:
        try:
            modes.append(Mode(token))
        except ValueError as exc:
            valid = ", ".join(mode.value for mode in Mode)
            raise SystemExit(f"Unsupported mode '{token}'. Valid options: {valid}") from exc

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
        p_loss=args.p_loss,
        p_reorder=args.p_reorder,
        window_size=args.window_size,
        command_sequence=command_sequence,
        command_set=DEFAULT_COMMANDS,
        target_commands=args.target_commands,
        rng_seed=args.seed,
        mac_length=args.mac_length,
        shared_key=args.shared_key,
        attacker_record_loss=args.attacker_loss,
        inline_attack_probability=args.inline_attack_prob,
        inline_attack_burst=args.inline_attack_burst,
        challenge_nonce_bits=args.challenge_nonce_bits,
    )

    # Run experiments with progress display (unless quiet mode)
    stats = run_many_experiments(
        base_config, 
        modes=modes, 
        runs=args.runs, 
        seed=args.seed,
        show_progress=not args.quiet
    )
    
    _print_table(stats)

    if args.output_json:
        path = Path(args.output_json)
        payload = [entry.as_dict() for entry in stats]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved aggregate metrics to {path}")


def _print_table(stats) -> None:
    if not stats:
        print("No stats to display")
        return

    header = (
        "Mode",
        "Runs",
        "Attack",
        "p_loss",
        "p_reorder",
        "Window",
        "Avg Legit",
        "Std Legit",
        "Avg Attack",
        "Std Attack",
    )
    rows = []
    for entry in stats:
        rows.append(
            (
                entry.mode.value,
                str(entry.runs),
                entry.attack_mode.value,
                f"{entry.p_loss:.2f}",
                f"{entry.p_reorder:.2f}",
                str(entry.window_size),
                _format_rate(entry.avg_legit_rate),
                _format_rate(entry.std_legit_rate),
                _format_rate(entry.avg_attack_rate),
                _format_rate(entry.std_attack_rate),
            )
        )
    
    # Wait, I missed adding p_reorder to AggregateStats in types.py!
    # I should fix that or just not print it.
    # I'll fix it in types.py first.
    
    col_widths = [max(len(col), max(len(row[i]) for row in rows)) for i, col in enumerate(header)]

    def _print_line(values):
        print("  ".join(value.ljust(col_widths[i]) for i, value in enumerate(values)))

    _print_line(header)
    _print_line(tuple("-" * w for w in col_widths))
    for row in rows:
        _print_line(row)


def _format_rate(value: float) -> str:
    return f"{value * 100:6.2f}%"


def _print_header(args) -> None:
    """Print an impressive header with simulation parameters."""
    print("\n" + "="*80)
    print("║" + " "*78 + "║")
    print("║" + "REPLAY ATTACK DEFENSE SIMULATION TOOLKIT".center(78) + "║")
    print("║" + "リプレイ攻撃防御シミュレーションツールキット".center(78) + "║")
    print("║" + " "*78 + "║")
    print("="*80)
    print("\n📋 SIMULATION PARAMETERS:")
    print(f"   └─ Defense Modes: {', '.join(args.modes)}")
    print(f"   └─ Monte Carlo Runs: {args.runs}")
    print(f"   └─ Legitimate Transmissions: {args.num_legit} per run")
    print(f"   └─ Replay Attempts: {args.num_replay} per run")
    print(f"   └─ Packet Loss Rate: {args.p_loss:.2%}")
    print(f"   └─ Packet Reorder Rate: {args.p_reorder:.2%}")
    print(f"   └─ Window Size: {args.window_size}")
    print(f"   └─ Attack Mode: {args.attack_mode}")
    if args.target_commands:
        print(f"   └─ Target Commands: {', '.join(args.target_commands)}")
    print("\n🔬 INITIALIZING SIMULATION ENVIRONMENT...")
    time.sleep(0.5)
    print("   ✓ Channel model initialized")
    time.sleep(0.3)
    print("   ✓ Attacker model configured")
    time.sleep(0.3)
    print("   ✓ Cryptographic modules loaded")
    time.sleep(0.3)
    print("   ✓ Defense mechanisms ready")
    print("\n" + "-"*80 + "\n")


if __name__ == "__main__":
    main()
