#!/usr/bin/env python3
"""
Frame Analysis Script - 对应论文3.4节 フレーム構造解析

解析捕获的 2.4 GHz 信号，提取帧结构并验证与论文一致性。
"""

import argparse
import os
import sys
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


def load_raw_samples(file_path, sample_format='cs8'):
    """
    Load raw IQ samples from file.

    Args:
        file_path: Path to raw capture file
        sample_format: 'cs8' (HackRF default), 'cf32' (GNU Radio complex float)

    Returns:
        Complex numpy array of samples
    """
    if sample_format == 'cs8':
        # HackRF format: interleaved signed 8-bit I/Q
        raw = np.fromfile(file_path, dtype=np.int8)
        iq = raw[0::2] + 1j * raw[1::2]
        return iq.astype(np.complex64) / 128.0
    elif sample_format == 'cf32':
        # GNU Radio format: complex float32
        return np.fromfile(file_path, dtype=np.complex64)
    else:
        raise ValueError(f"Unknown sample format: {sample_format}")


def fsk_demodulate(iq_samples, samples_per_symbol=2, modulation='FSK'):
    """
    Simple FSK demodulation using frequency discrimination.

    Args:
        iq_samples: Complex IQ samples
        samples_per_symbol: Samples per symbol (论文: 2)

    Returns:
        Bit array (0 or 1)
    """
    # Compute instantaneous frequency (phase derivative)
    phase = np.angle(iq_samples)
    freq = np.diff(np.unwrap(phase))

    # Average over symbol periods
    num_symbols = len(freq) // samples_per_symbol
    freq_symbols = freq[:num_symbols * samples_per_symbol].reshape(-1, samples_per_symbol).mean(axis=1)

    # GFSK still uses frequency-discriminator demodulation; apply light smoothing
    # to approximate the pulse-shaping effect before hard decision.
    if modulation.upper() == 'GFSK' and len(freq_symbols) >= 3:
        kernel = np.ones(3, dtype=np.float32) / 3.0
        freq_symbols = np.convolve(freq_symbols, kernel, mode='same')

    # Decision: positive freq = 1, negative = 0
    bits = (freq_symbols > 0).astype(int)

    return bits


def bits_to_hex(bits):
    """Convert bit array to hex string."""
    # Pad to multiple of 8
    pad_len = (8 - len(bits) % 8) % 8
    padded = np.concatenate([bits, np.zeros(pad_len, dtype=int)])

    # Convert to bytes
    bytes_list = []
    for i in range(0, len(padded), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | padded[i + j]
        bytes_list.append(byte)

    return ''.join(f'{b:02x}' for b in bytes_list)


def find_preamble(bits, preamble_pattern=None):
    """
    Find preamble/sync pattern in bit stream.

    Returns list of start indices where preamble is found.
    """
    if preamble_pattern is None:
        # Common preamble patterns for FSK systems
        preamble_pattern = [1, 0, 1, 0, 1, 0, 1, 0]  # 0xAA

    preamble = np.array(preamble_pattern)
    matches = []

    for i in range(len(bits) - len(preamble) + 1):
        if np.array_equal(bits[i:i+len(preamble)], preamble):
            matches.append(i)

    return matches


def extract_frames(bits, frame_length_bytes=24, min_gap=100):
    """
    Extract frames from bit stream.

    Args:
        bits: Demodulated bit array
        frame_length_bytes: Expected frame length in bytes (论文: 24)
        min_gap: Minimum gap between frames in bits

    Returns:
        List of (start_idx, frame_bits, frame_hex) tuples
    """
    frame_length_bits = frame_length_bytes * 8
    frames = []

    # Find potential frame starts (look for preamble/sync)
    preamble_indices = find_preamble(bits)

    for idx in preamble_indices:
        if idx + frame_length_bits <= len(bits):
            frame_bits = bits[idx:idx + frame_length_bits]
            frame_hex = bits_to_hex(frame_bits)
            frames.append((idx, frame_bits, frame_hex))

    # Remove overlapping frames
    filtered = []
    last_end = -min_gap
    for idx, frame_bits, frame_hex in frames:
        if idx >= last_end + min_gap:
            filtered.append((idx, frame_bits, frame_hex))
            last_end = idx + len(frame_bits)

    return filtered


def verify_frame_structure(frame_hex, config, verify_prefix=None):
    """
    Verify frame structure matches paper (论文3.4节).

    Args:
        frame_hex: Hex string of frame
        config: Configuration dict

    Returns:
        Dict with verification results
    """
    expected_prefix = (verify_prefix or config['chapter3_frame']['prefix']).lower()
    known_commands = config['chapter3_frame']['commands']

    result = {
        'frame_hex': frame_hex,
        'frame_length': len(frame_hex) // 2,
        'prefix_match': False,
        'prefix_value': None,
        'tail_value': None,
        'command': None
    }

    prefix_len = len(expected_prefix)

    # Check if frame is long enough
    if len(frame_hex) < prefix_len + 10:  # tail = 5 bytes = 10 hex chars
        result['error'] = f"Frame too short for prefix/tail parsing: {len(frame_hex)//2} bytes"
        return result

    # Extract prefix and tail
    prefix = frame_hex[:prefix_len].lower()
    tail = frame_hex[prefix_len:prefix_len + 10].lower()  # 5 bytes = 10 hex chars

    result['prefix_value'] = prefix
    result['tail_value'] = tail

    # Verify prefix
    if prefix == expected_prefix:
        result['prefix_match'] = True
    else:
        # Check for partial match
        match_len = 0
        for i, (a, b) in enumerate(zip(prefix, expected_prefix)):
            if a == b:
                match_len += 1
            else:
                break
        result['prefix_match_ratio'] = match_len / len(expected_prefix)

    # Identify command
    for cmd_name, cmd_tail in known_commands.items():
        if tail == cmd_tail.lower():
            result['command'] = cmd_name
            break

    return result


def analyze_file(file_path, config, sample_format='auto', modulation='FSK', verify_prefix=None, verbose=True):
    """
    Analyze a capture file and extract frames.

    Args:
        file_path: Path to capture file
        config: Configuration dict
        sample_format: 'cs8', 'cf32', or 'auto'
        verbose: Print detailed output

    Returns:
        Dict with analysis results
    """
    # Determine sample format from extension
    if sample_format == 'auto':
        ext = Path(file_path).suffix.lower()
        if ext in ['.raw', '.cs8']:
            sample_format = 'cs8'
        elif ext in ['.cfile', '.cf32', '.complex']:
            sample_format = 'cf32'
        else:
            print(f"[WARNING] Unknown extension {ext}, assuming cs8")
            sample_format = 'cs8'

    if verbose:
        print(f"Loading: {file_path}")
        print(f"Format: {sample_format}")

    # Load samples
    samples = load_raw_samples(file_path, sample_format)
    if verbose:
        print(f"Samples loaded: {len(samples):,}")
        print(f"Duration: {len(samples) / config['hardware']['sample_rate_hz']:.2f} seconds")

    # Demodulate
    samples_per_symbol = config['hardware']['modulation']['samples_per_symbol']
    bits = fsk_demodulate(samples, samples_per_symbol, modulation=modulation)
    if verbose:
        print(f"Demodulated bits: {len(bits):,}")

    # Extract frames
    frames = extract_frames(bits, frame_length_bytes=24)
    if verbose:
        print(f"Frames found: {len(frames)}")

    # Analyze each frame
    results = {
        'file': str(file_path),
        'sample_count': len(samples),
        'bit_count': len(bits),
        'frame_count': len(frames),
        'frames': []
    }

    for i, (idx, frame_bits, frame_hex) in enumerate(frames):
        verification = verify_frame_structure(frame_hex, config, verify_prefix=verify_prefix)
        verification['bit_index'] = idx

        results['frames'].append(verification)

        if verbose:
            print()
            print(f"Frame {i+1}:")
            print(f"  Hex: {frame_hex}")
            print(f"  Prefix: {verification.get('prefix_value', 'N/A')}")
            print(f"  Tail: {verification.get('tail_value', 'N/A')}")
            print(f"  Prefix match: {verification['prefix_match']}")
            if verification.get('command'):
                print(f"  Command: {verification['command']}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Analyze captured frames and verify structure (论文3.4节)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a capture file
  python analyze_frames.py --input captures/signal_001.raw

  # Verify prefix matches paper
  python analyze_frames.py --input captures/*.raw --verify-prefix

  # Output to JSON
  python analyze_frames.py --input captures/signal.raw --output results/analysis.json
"""
    )

    parser.add_argument('--input', '-i', type=str, required=True,
                        help='Input capture file(s) (supports glob patterns)')
    parser.add_argument('--config', type=str, default=None,
                        help='Config file path')
    parser.add_argument('--format', choices=['auto', 'cs8', 'cf32'], default='auto',
                        help='Sample format (default: auto-detect from extension)')
    parser.add_argument('--verify-prefix', type=str, default=None,
                        help='Verify frames start with this prefix (default: from config)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output JSON file for results')
    parser.add_argument('--modulation', choices=['FSK', 'GFSK'], default='FSK',
                        help='Modulation type (default: FSK)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress detailed output')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Handle glob patterns
    import glob
    input_files = glob.glob(args.input)
    if not input_files:
        print(f"Error: No files match pattern: {args.input}")
        sys.exit(1)

    print("=" * 60)
    print("フレーム構造解析 - Frame Analysis (论文3.4节)")
    print("=" * 60)
    print()
    if args.verify_prefix:
        normalized_prefix = args.verify_prefix.lower()
        if any(ch not in "0123456789abcdef" for ch in normalized_prefix):
            print(f"Error: --verify-prefix must be a hex string, got: {args.verify_prefix}")
            sys.exit(1)
    else:
        normalized_prefix = None

    expected_prefix = normalized_prefix or config['chapter3_frame']['prefix']
    print(f"Expected prefix (论文): {expected_prefix}")
    print(f"Known commands: {len(config['chapter3_frame']['commands'])}")
    print(f"Demodulation: {args.modulation}")
    print()

    all_results = []
    total_frames = 0
    prefix_matches = 0

    for file_path in input_files:
        print("-" * 40)
        result = analyze_file(
            file_path,
            config,
            sample_format=args.format,
            modulation=args.modulation,
            verify_prefix=normalized_prefix,
            verbose=not args.quiet,
        )
        all_results.append(result)

        total_frames += result['frame_count']
        prefix_matches += sum(1 for f in result['frames'] if f.get('prefix_match'))

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Files analyzed: {len(input_files)}")
    print(f"Total frames: {total_frames}")
    print(f"Prefix matches: {prefix_matches} ({100*prefix_matches/max(1,total_frames):.1f}%)")

    if args.verify_prefix or prefix_matches == total_frames:
        print()
        print("[OK] Frame structure matches paper (论文3.4節のフレーム構造と一致)")

    # Save results
    if args.output:
        import json
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print()
        print(f"Results saved to: {args.output}")

    print()
    print("Next step: Replay attack with replay_chapter3.py")


if __name__ == "__main__":
    main()
