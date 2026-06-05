#!/usr/bin/env python3
"""
Channel Calibration Tool

Measures actual packet loss rate and reordering characteristics
of the physical wireless channel to calibrate simulation parameters.

This tool:
1. Sends known sequence of numbered packets
2. Measures which packets are received
3. Calculates actual p_loss and p_reorder
4. Exports results for simulation parameter tuning

Usage:
    # Run calibration with 1000 packets
    python calibration.py --packets 1000

    # Run calibration at different distances
    python calibration.py --packets 500 --label "distance_5m"

    # Generate calibration report
    python calibration.py --report
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import yaml

from sim.types import Frame


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PacketRecord:
    """Record of a single calibration packet."""
    seq_num: int
    tx_time: float
    rx_time: Optional[float] = None
    received: bool = False
    latency_ms: float = 0.0


@dataclass
class ReorderEvent:
    """Record of a reordering event."""
    expected_seq: int
    received_seq: int
    offset: int  # How many positions out of order


@dataclass
class CalibrationResult:
    """Results of a calibration run."""
    label: str
    timestamp: str
    num_sent: int
    num_received: int
    num_lost: int
    num_reordered: int

    # Computed metrics
    packet_loss_rate: float
    reorder_rate: float

    # Latency statistics (ms)
    latency_mean: float
    latency_std: float
    latency_min: float
    latency_max: float
    latency_p50: float
    latency_p95: float
    latency_p99: float

    # Reorder statistics
    max_reorder_offset: int
    reorder_offsets: List[int] = field(default_factory=list)

    # Raw data
    packets: List[PacketRecord] = field(default_factory=list)
    reorder_events: List[ReorderEvent] = field(default_factory=list)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load experiment configuration."""
    if config_path is None:
        config_path = PROJECT_ROOT / "physical_experiment/configs/experiment_config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# =============================================================================
# Calibration Runner
# =============================================================================

class ChannelCalibrator:
    """
    Measures channel characteristics by sending numbered packets
    and analyzing reception patterns.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        tx_port: int = 5555,
        rx_port: int = 5556,
        timeout_ms: int = 2000,
        loopback: bool = False,
        p_loss: float = 0.0,
        p_reorder: float = 0.0,
        seed: int = 42,
        command_tag: str = "CAL"
    ):
        self.config = config
        self.timeout_ms = timeout_ms
        self.loopback = loopback
        self.p_loss = p_loss
        self.p_reorder = p_reorder
        self.seed = seed
        self.command_tag = command_tag
        self.rng = random.Random(seed)

        self.transport = None

        # Override ZMQ ports in config for hardware mode.
        zmq_config = self.config.setdefault("zmq", {})
        zmq_config["tx_port"] = tx_port
        zmq_config["rx_port"] = rx_port
        zmq_config["timeout_ms"] = timeout_ms

    def connect(self) -> bool:
        """Establish transport connections."""
        if self.loopback:
            from physical_experiment.scripts.experiment_runner import LoopbackTransport
            self.transport = LoopbackTransport(
                p_loss=self.p_loss,
                p_reorder=self.p_reorder,
                rng=self.rng
            )
            return True

        from physical_experiment.scripts.experiment_runner import HardwareTransport
        self.transport = HardwareTransport(self.config)
        return self.transport.connect()

    def disconnect(self):
        """Close connections."""
        if self.transport:
            self.transport.disconnect()

    def run_calibration(
        self,
        num_packets: int = 1000,
        interval_ms: float = 50,
        label: str = "default"
    ) -> CalibrationResult:
        """
        Send numbered packets and measure channel characteristics.

        Args:
            num_packets: Number of packets to send
            interval_ms: Interval between packets in milliseconds
            label: Label for this calibration run

        Returns:
            CalibrationResult with measured statistics
        """
        print(f"\n{'='*60}")
        print(f"Channel Calibration: {label}")
        print(f"Sending {num_packets} packets with {interval_ms}ms interval")
        print(f"{'='*60}\n")

        packets: List[PacketRecord] = []
        received_order: List[int] = []
        interval_s = interval_ms / 1000.0

        # Phase 1: Send all packets
        print("Phase 1: Sending packets...")
        for idx in range(num_packets):
            seq = idx + 1  # Avoid 0 (decoded as None)
            tx_time = time.time()

            frame = Frame(command=self.command_tag, counter=seq)
            self.transport.send_frame(frame)

            packets.append(PacketRecord(
                seq_num=seq,
                tx_time=tx_time
            ))

            # Progress indicator
            if (idx + 1) % 100 == 0:
                print(f"  Sent: {idx + 1}/{num_packets}")

            time.sleep(interval_s)

        # Phase 2: Receive responses (with extended timeout)
        print("\nPhase 2: Receiving responses...")
        receive_timeout = self.timeout_ms + (num_packets * interval_ms * 0.1)

        start_receive = time.time()
        received_count = 0

        while (time.time() - start_receive) < (receive_timeout / 1000.0):
            result = self.transport.receive_frame()
            if result is None:
                if hasattr(self.transport, "has_pending") and not self.transport.has_pending():
                    time.sleep(0.01)
                continue

            frame, _ = result
            if frame.command != self.command_tag:
                continue
            if frame.counter is None:
                continue

            seq = frame.counter
            if not (1 <= seq <= num_packets):
                continue

            idx = seq - 1
            if not packets[idx].received:
                rx_time = time.time()
                packets[idx].received = True
                packets[idx].rx_time = rx_time
                packets[idx].latency_ms = (rx_time - packets[idx].tx_time) * 1000
                received_order.append(seq)
                received_count += 1

                if received_count % 100 == 0:
                    print(f"  Received: {received_count}")

            # Early exit if all received
            if received_count >= num_packets:
                break

        print(f"\nReceived {received_count}/{num_packets} packets")

        # Analyze results
        return self._analyze_results(packets, received_order, label)

    def _analyze_results(
        self,
        packets: List[PacketRecord],
        received_order: List[int],
        label: str
    ) -> CalibrationResult:
        """Analyze calibration data and compute statistics."""

        num_sent = len(packets)
        num_received = sum(1 for p in packets if p.received)
        num_lost = num_sent - num_received

        # Packet loss rate
        packet_loss_rate = num_lost / num_sent if num_sent > 0 else 0.0

        # Latency statistics
        latencies = [p.latency_ms for p in packets if p.received and p.latency_ms > 0]

        if latencies:
            latency_mean = statistics.mean(latencies)
            latency_std = statistics.pstdev(latencies) if len(latencies) > 1 else 0.0
            latency_min = min(latencies)
            latency_max = max(latencies)

            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)
            latency_p50 = sorted_latencies[int(n * 0.50)]
            latency_p95 = sorted_latencies[int(n * 0.95)]
            latency_p99 = sorted_latencies[int(n * 0.99)]
        else:
            latency_mean = latency_std = latency_min = latency_max = 0.0
            latency_p50 = latency_p95 = latency_p99 = 0.0

        # Reorder analysis
        reorder_events: List[ReorderEvent] = []
        expected_seq = 1

        for seq in received_order:
            if seq < expected_seq:
                # Out of order (received a packet we expected earlier)
                offset = expected_seq - seq
                reorder_events.append(ReorderEvent(
                    expected_seq=expected_seq,
                    received_seq=seq,
                    offset=offset
                ))
            else:
                expected_seq = seq + 1

        num_reordered = len(reorder_events)
        reorder_rate = num_reordered / num_received if num_received > 0 else 0.0
        reorder_offsets = [e.offset for e in reorder_events]
        max_reorder_offset = max(reorder_offsets) if reorder_offsets else 0

        result = CalibrationResult(
            label=label,
            timestamp=datetime.now().isoformat(),
            num_sent=num_sent,
            num_received=num_received,
            num_lost=num_lost,
            num_reordered=num_reordered,
            packet_loss_rate=packet_loss_rate,
            reorder_rate=reorder_rate,
            latency_mean=latency_mean,
            latency_std=latency_std,
            latency_min=latency_min,
            latency_max=latency_max,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            max_reorder_offset=max_reorder_offset,
            reorder_offsets=reorder_offsets,
            packets=packets,
            reorder_events=reorder_events
        )

        self._print_summary(result)
        return result

    def _print_summary(self, result: CalibrationResult):
        """Print calibration summary."""
        print(f"\n{'='*60}")
        print("CALIBRATION RESULTS")
        print(f"{'='*60}")

        print(f"\nPacket Statistics:")
        print(f"  Sent:     {result.num_sent}")
        print(f"  Received: {result.num_received}")
        print(f"  Lost:     {result.num_lost}")
        print(f"  Loss Rate: {result.packet_loss_rate:.2%}")

        print(f"\nReorder Statistics:")
        print(f"  Reordered Packets: {result.num_reordered}")
        print(f"  Reorder Rate: {result.reorder_rate:.2%}")
        print(f"  Max Reorder Offset: {result.max_reorder_offset}")

        print(f"\nLatency Statistics (ms):")
        print(f"  Mean:   {result.latency_mean:.2f}")
        print(f"  Std:    {result.latency_std:.2f}")
        print(f"  Min:    {result.latency_min:.2f}")
        print(f"  Max:    {result.latency_max:.2f}")
        print(f"  P50:    {result.latency_p50:.2f}")
        print(f"  P95:    {result.latency_p95:.2f}")
        print(f"  P99:    {result.latency_p99:.2f}")

        print(f"\n{'='*60}")
        print("SIMULATION PARAMETER RECOMMENDATIONS")
        print(f"{'='*60}")
        print(f"  p_loss:    {result.packet_loss_rate:.3f}")
        print(f"  p_reorder: {result.reorder_rate:.3f}")

        # Recommend window size based on max reorder offset
        if result.max_reorder_offset > 0:
            recommended_window = max(result.max_reorder_offset + 2, 5)
            print(f"  window_size: >= {recommended_window} (based on max offset {result.max_reorder_offset})")
        else:
            print(f"  window_size: >= 3 (minimal reordering observed)")


def save_calibration_result(
    result: CalibrationResult,
    output_dir: Path
):
    """Save calibration result to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create simplified dict (without raw packet data for smaller file)
    summary = {
        "label": result.label,
        "timestamp": result.timestamp,
        "num_sent": result.num_sent,
        "num_received": result.num_received,
        "num_lost": result.num_lost,
        "num_reordered": result.num_reordered,
        "packet_loss_rate": result.packet_loss_rate,
        "reorder_rate": result.reorder_rate,
        "latency_mean": result.latency_mean,
        "latency_std": result.latency_std,
        "latency_min": result.latency_min,
        "latency_max": result.latency_max,
        "latency_p50": result.latency_p50,
        "latency_p95": result.latency_p95,
        "latency_p99": result.latency_p99,
        "max_reorder_offset": result.max_reorder_offset,
        "reorder_offsets": result.reorder_offsets,
        "recommended_params": {
            "p_loss": result.packet_loss_rate,
            "p_reorder": result.reorder_rate,
            "min_window_size": max(result.max_reorder_offset + 2, 3)
        }
    }

    filename = f"calibration_{result.label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = output_dir / filename

    with open(filepath, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved: {filepath}")
    return filepath


def generate_calibration_report(results_dir: Path) -> str:
    """Generate a summary report from all calibration runs."""
    from glob import glob

    files = list(results_dir.glob("calibration_*.json"))
    if not files:
        return "No calibration results found."

    report = []
    report.append("# Channel Calibration Report")
    report.append(f"\nGenerated: {datetime.now().isoformat()}")
    report.append(f"Results directory: {results_dir}")
    report.append(f"\n## Summary\n")

    report.append("| Label | Loss Rate | Reorder Rate | Latency (ms) | Max Offset |")
    report.append("|-------|-----------|--------------|--------------|------------|")

    for filepath in sorted(files):
        with open(filepath) as f:
            data = json.load(f)

        label = data.get("label", "unknown")
        loss = data.get("packet_loss_rate", 0) * 100
        reorder = data.get("reorder_rate", 0) * 100
        latency = data.get("latency_mean", 0)
        offset = data.get("max_reorder_offset", 0)

        report.append(f"| {label} | {loss:.1f}% | {reorder:.1f}% | {latency:.1f} | {offset} |")

    report.append("\n## Recommended Simulation Parameters\n")
    report.append("Based on the calibration results, use these parameters in simulation:")
    report.append("```python")
    report.append("config = SimulationConfig(")
    report.append("    p_loss=<average from calibration>,")
    report.append("    p_reorder=<average from calibration>,")
    report.append("    window_size=<max_offset + 2>")
    report.append(")")
    report.append("```")

    report_text = "\n".join(report)

    # Save report
    report_file = results_dir / "calibration_report.md"
    with open(report_file, 'w') as f:
        f.write(report_text)

    print(f"Report saved: {report_file}")
    return report_text


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Channel Calibration Tool for Hardware Experiments"
    )

    parser.add_argument("--packets", type=int, default=1000,
                        help="Number of calibration packets to send")
    parser.add_argument("--interval", type=float, default=50,
                        help="Interval between packets in ms")
    parser.add_argument("--label", type=str, default="default",
                        help="Label for this calibration run")
    parser.add_argument("--config", type=str, default=None,
                        help="Config file path")
    parser.add_argument("--tx-port", type=int, default=5555,
                        help="ZMQ TX port")
    parser.add_argument("--rx-port", type=int, default=5556,
                        help="ZMQ RX port")
    parser.add_argument("--timeout-ms", type=int, default=2000,
                        help="Receive timeout in ms")
    parser.add_argument("--loopback", action="store_true",
                        help="Use loopback transport (no hardware required)")
    parser.add_argument("--p-loss", type=float, default=0.0,
                        help="Loopback loss rate")
    parser.add_argument("--p-reorder", type=float, default=0.0,
                        help="Loopback reorder rate")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for loopback channel")
    parser.add_argument("--output-dir", type=str,
                        default="physical_experiment/results",
                        help="Output directory for results")
    parser.add_argument("--report", action="store_true",
                        help="Generate summary report from existing results")

    args = parser.parse_args()

    output_dir = PROJECT_ROOT / args.output_dir

    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.report:
        report = generate_calibration_report(output_dir)
        print(report)
        return

    calibrator = ChannelCalibrator(
        config=config,
        tx_port=args.tx_port,
        rx_port=args.rx_port,
        timeout_ms=args.timeout_ms,
        loopback=args.loopback,
        p_loss=args.p_loss,
        p_reorder=args.p_reorder,
        seed=args.seed
    )

    try:
        if not calibrator.connect():
            print("Failed to connect. Is GNU Radio running?")
            sys.exit(1)

        result = calibrator.run_calibration(
            num_packets=args.packets,
            interval_ms=args.interval,
            label=args.label
        )

        save_calibration_result(result, output_dir)

    except KeyboardInterrupt:
        print("\nCalibration interrupted")
    except RuntimeError as e:
        print(f"Calibration failed: {e}")
        sys.exit(1)
    finally:
        calibrator.disconnect()


if __name__ == "__main__":
    main()
