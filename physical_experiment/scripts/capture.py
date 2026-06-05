#!/usr/bin/env python3
"""
Signal Capture Script - 对应论文3.3节 信号キャプチャ

使用 HackRF One 捕获 2.4 GHz 无线遥控信号。
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from physical_experiment.runtime import load_experiment_config, resolve_hackrf_device_args

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


def check_hackrf():
    """Check if HackRF is available."""
    try:
        import subprocess
        result = subprocess.run(['hackrf_info'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("[OK] HackRF detected")
            return True
        else:
            print("[ERROR] HackRF not detected")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("[ERROR] hackrf_info command not found. Install HackRF tools.")
        return False
    except subprocess.TimeoutExpired:
        print("[ERROR] hackrf_info timed out")
        return False


def capture_signal_hackrf(freq_hz, sample_rate_hz, duration_s, output_path, gain_db=24, device_serial=""):
    """
    Capture signal using hackrf_transfer command.

    Args:
        freq_hz: Center frequency in Hz
        sample_rate_hz: Sample rate in Hz
        duration_s: Duration in seconds
        output_path: Output file path (.raw or .cs8)
        gain_db: LNA gain in dB
    """
    import subprocess

    # Calculate number of samples
    num_samples = int(sample_rate_hz * duration_s)

    cmd = [
        'hackrf_transfer',
        '-r', str(output_path),
        '-f', str(int(freq_hz)),
        '-s', str(int(sample_rate_hz)),
        '-l', str(gain_db),  # LNA gain
        '-g', '20',          # VGA gain
        '-n', str(num_samples)
    ]
    if device_serial:
        cmd.extend(['-d', device_serial])

    print(f"Capturing signal:")
    print(f"  Frequency: {freq_hz/1e9:.4f} GHz")
    print(f"  Sample rate: {sample_rate_hz/1e6:.1f} Msps")
    print(f"  Duration: {duration_s} seconds")
    print(f"  Output: {output_path}")
    print()
    print("Running:", ' '.join(cmd))
    print()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_s + 10)
        if result.returncode == 0:
            print("[OK] Capture completed successfully")
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"  File size: {file_size / 1e6:.2f} MB")
            return True
        else:
            print("[ERROR] Capture failed")
            print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("[ERROR] Capture timed out")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def capture_signal_gnuradio(freq_hz, sample_rate_hz, duration_s, output_path, device_args=""):
    """
    Capture signal using GNU Radio (requires gr-osmosdr).

    This is an alternative method if hackrf_transfer is not available.
    """
    try:
        from gnuradio import gr
        from gnuradio import blocks
        import osmosdr
    except ImportError:
        print("[ERROR] GNU Radio or gr-osmosdr not installed")
        return False

    print(f"Capturing signal using GNU Radio:")
    print(f"  Frequency: {freq_hz/1e9:.4f} GHz")
    print(f"  Sample rate: {sample_rate_hz/1e6:.1f} Msps")
    print(f"  Duration: {duration_s} seconds")
    print(f"  Output: {output_path}")

    class CaptureFlowgraph(gr.top_block):
        def __init__(self, freq, samp_rate, duration, output_file, device_args):
            gr.top_block.__init__(self, "Signal Capture")

            # HackRF Source
            hackrf_args = f"numchan=1 {device_args}".strip()
            self.source = osmosdr.source(args=hackrf_args)
            self.source.set_sample_rate(samp_rate)
            self.source.set_center_freq(freq)
            self.source.set_freq_corr(0)
            self.source.set_gain(24)  # LNA gain
            self.source.set_if_gain(20)  # VGA gain
            self.source.set_bb_gain(20)

            # Head block to limit samples
            num_samples = int(samp_rate * duration)
            self.head = blocks.head(gr.sizeof_gr_complex, num_samples)

            # File sink
            self.sink = blocks.file_sink(gr.sizeof_gr_complex, output_file)

            # Connect
            self.connect(self.source, self.head, self.sink)

    try:
        fg = CaptureFlowgraph(freq_hz, sample_rate_hz, duration_s, output_path, device_args)
        fg.start()
        fg.wait()
        print("[OK] Capture completed")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Capture 2.4 GHz wireless remote control signals (论文3.3节)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture with default settings (from config)
  python capture.py --duration 10 --output captures/signal_001.raw

  # Capture at specific frequency
  python capture.py --freq 2475000000 --duration 5 --output captures/test.raw

  # Use GNU Radio instead of hackrf_transfer
  python capture.py --duration 10 --output captures/signal.cfile --method gnuradio
"""
    )

    parser.add_argument('--freq', type=int, default=None,
                        help='Center frequency in Hz (default: from config)')
    parser.add_argument('--rate', type=int, default=None,
                        help='Sample rate in Hz (default: from config)')
    parser.add_argument('--config', type=str, default=None,
                        help='Config file path')
    parser.add_argument('--duration', type=float, default=10,
                        help='Capture duration in seconds (default: 10)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file path (default: auto-generated)')
    parser.add_argument('--gain', type=int, default=24,
                        help='LNA gain in dB (default: 24)')
    parser.add_argument('--method', choices=['hackrf', 'gnuradio'], default='hackrf',
                        help='Capture method (default: hackrf)')
    parser.add_argument('--device', type=str, default='',
                        help='HackRF device args for GNU Radio capture')
    parser.add_argument('--hackrf-serial', type=str, default='',
                        help='HackRF serial for capture')
    parser.add_argument('--skip-check', action='store_true',
                        help='Skip HackRF availability check')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Get parameters
    freq_hz = args.freq or config['hardware']['frequency_hz']
    sample_rate_hz = args.rate or config['hardware']['sample_rate_hz']
    device_args = resolve_hackrf_device_args(
        config,
        "rx",
        device_args_override=args.device,
        serial_override=args.hackrf_serial,
    )
    device_serial = args.hackrf_serial or config.get('hardware', {}).get('rx', {}).get('device_serial') or ""

    # Generate output path if not specified
    if args.output:
        output_path = args.output
    else:
        captures_dir = Path(__file__).parent.parent / "captures"
        captures_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".cfile" if args.method == 'gnuradio' else ".raw"
        output_path = str(captures_dir / f"capture_{timestamp}{ext}")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("信号キャプチャ - Signal Capture (论文3.3节)")
    print("=" * 60)
    print()

    # Check HackRF
    if not args.skip_check:
        if not check_hackrf():
            print("\nHackRF not available. Use --skip-check to bypass this check.")
            sys.exit(1)
        print()

    # Capture
    if args.method == 'hackrf':
        success = capture_signal_hackrf(
            freq_hz, sample_rate_hz, args.duration, output_path, args.gain, device_serial
        )
    else:
        success = capture_signal_gnuradio(
            freq_hz, sample_rate_hz, args.duration, output_path, device_args
        )

    if success:
        print()
        print("Next step: Analyze frames with analyze_frames.py")
        print(f"  python analyze_frames.py --input {output_path}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
