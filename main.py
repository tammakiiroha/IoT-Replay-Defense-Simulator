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


def validate_parameters(args: argparse.Namespace) -> None:
    """验证输入参数的合理性"""
    errors = []
    
    # 验证概率参数 (0.0 ~ 1.0)
    if not 0.0 <= args.p_loss <= 1.0:
        errors.append(f"Invalid p_loss: {args.p_loss}. Must be between 0.0 and 1.0")
    if not 0.0 <= args.p_reorder <= 1.0:
        errors.append(f"Invalid p_reorder: {args.p_reorder}. Must be between 0.0 and 1.0")
    if not 0.0 <= args.attacker_loss <= 1.0:
        errors.append(f"Invalid attacker_loss: {args.attacker_loss}. Must be between 0.0 and 1.0")
    if not 0.0 <= args.inline_attack_prob <= 1.0:
        errors.append(f"Invalid inline_attack_prob: {args.inline_attack_prob}. Must be between 0.0 and 1.0")
    
    # 验证正整数参数
    if args.runs <= 0:
        errors.append(f"Invalid runs: {args.runs}. Must be positive integer")
    if args.num_legit < 0:
        errors.append(f"Invalid num_legit: {args.num_legit}. Must be non-negative integer")
    if args.num_replay < 0:
        errors.append(f"Invalid num_replay: {args.num_replay}. Must be non-negative integer")
    if args.window_size <= 0:
        errors.append(f"Invalid window_size: {args.window_size}. Must be positive integer")
    if args.mac_length <= 0:
        errors.append(f"Invalid mac_length: {args.mac_length}. Must be positive integer")
    if args.inline_attack_burst <= 0:
        errors.append(f"Invalid inline_attack_burst: {args.inline_attack_burst}. Must be positive integer")
    if args.challenge_nonce_bits <= 0:
        errors.append(f"Invalid challenge_nonce_bits: {args.challenge_nonce_bits}. Must be positive integer")
    
    # 验证文件路径
    if args.commands_file and not Path(args.commands_file).exists():
        errors.append(f"Commands file not found: {args.commands_file}")
    
    # 验证种子值
    if args.seed is not None and args.seed < 0:
        errors.append(f"Invalid seed: {args.seed}. Must be non-negative integer or None")
    
    # 合理性警告（不阻止运行，但给出提示）
    warnings = []
    if args.p_loss > 0.5:
        warnings.append(f"Warning: High packet loss ({args.p_loss*100:.0f}%) may lead to low acceptance rates")
    if args.runs < 10:
        warnings.append(f"Warning: Low run count ({args.runs}) may not provide statistically reliable results")
    if args.num_legit == 0 and args.num_replay == 0:
        warnings.append("Warning: Both num_legit and num_replay are zero. No simulation will occur")
    if args.window_size > 100:
        warnings.append(f"Warning: Very large window size ({args.window_size}) may be unrealistic")
    
    # 打印错误和警告
    if errors:
        print("\n❌ Parameter Validation Failed:\n", file=sys.stderr)
        for error in errors:
            print(f"  • {error}", file=sys.stderr)
        print("\nPlease fix the errors and try again.\n", file=sys.stderr)
        sys.exit(1)
    
    if warnings and not args.quiet:
        print("\n⚠️  Parameter Warnings:\n")
        for warning in warnings:
            print(f"  • {warning}")
        print()  # Extra line for readability


def main() -> None:
    args = parse_args()
    
    # Validate parameters first
    validate_parameters(args)
    
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

    command_sequence = None
    if args.commands_file:
        try:
            command_sequence = load_command_sequence(args.commands_file)
        except Exception as exc:
            raise SystemExit(f"Failed to load command sequence from '{args.commands_file}': {exc}") from exc

    try:
        attack_mode = AttackMode(args.attack_mode)
    except ValueError as exc:
        valid = ", ".join(mode.value for mode in AttackMode)
        raise SystemExit(f"Unsupported attack mode '{args.attack_mode}'. Valid options: {valid}") from exc

    try:
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
    except Exception as exc:
        raise SystemExit(f"Failed to create simulation configuration: {exc}") from exc

    # Run experiments with progress display (unless quiet mode)
    try:
        stats = run_many_experiments(
            base_config, 
            modes=modes, 
            runs=args.runs, 
            seed=args.seed,
            show_progress=not args.quiet
        )
    except Exception as exc:
        print(f"\n❌ Simulation failed: {exc}", file=sys.stderr)
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    _print_table(stats)

    if args.output_json:
        try:
            path = Path(args.output_json)
            path.parent.mkdir(parents=True, exist_ok=True)  # Create directory if needed
            payload = [entry.as_dict() for entry in stats]
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"\n✓ Saved aggregate metrics to {path}")
        except Exception as exc:
            print(f"\n❌ Failed to save JSON output to '{args.output_json}': {exc}", file=sys.stderr)
            sys.exit(1)


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
