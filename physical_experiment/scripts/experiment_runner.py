#!/usr/bin/env python3
"""
Unified Hardware Experiment Runner - 完全复现模拟实验

This script runs replay attack defense experiments using real hardware (HackRF + GNU Radio)
while reusing the EXACT same logic from the simulation package (sim/).

核心架构:
    experiment_runner.py (本脚本)
         |
         v
    protocol.py (Frame <-> RF 字节流转换)
         |
         v
    tx_flowgraph.py / rx_flowgraph.py (GNU Radio 流图)
         |
         v
    HackRF One (2.475 GHz FSK 调制)

对应论文参数:
- 频率: 2.475 GHz (论文3.3节)
- 调制: 2値FSK
- Samples/Symbol: 2
- 频偏: ~101.5 kHz

Usage:
    python experiment_runner.py --config ../configs/experiment_config.yaml
    python experiment_runner.py --mode window --runs 10
    python experiment_runner.py --loopback  # Test without hardware
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import statistics
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Sequence

import numpy as np
import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import zmq
except ImportError:
    print("Error: pyzmq not installed. Run: pip install pyzmq")
    sys.exit(1)

# Import simulation components - SAME as sim/experiment.py
from sim.sender import Sender
from sim.receiver import Receiver
from sim.attacker import Attacker
from sim.channel import Channel
from sim.rng import DeterministicRNG, RandomLike
from sim.types import Mode, Frame, AttackMode, SimulationConfig

# Import protocol layer for Frame <-> RF conversion
from physical_experiment.flowgraphs.protocol import (
    FrameEncoder, FrameDecoder, ZMQProtocol,
    RF_FREQUENCY_HZ, RF_SAMPLE_RATE_HZ, DEVIATION_HZ, SAMPLES_PER_SYMBOL
)


# =============================================================================
# 元数据采集（与 run_full_experiment.py 保持一致）
# =============================================================================

def get_environment_info() -> Dict[str, str]:
    """采集环境信息"""
    info = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    try:
        os_release = Path("/etc/os-release")
        if os_release.exists():
            content = os_release.read_text()
            pretty_match = re.search(r'^PRETTY_NAME="?([^"]+)"?$', content, re.MULTILINE)
            if pretty_match:
                info["os"] = pretty_match.group(1)
        else:
            import platform
            info["os"] = f"{platform.system()} {platform.release()}"
    except Exception:
        info["os"] = "unknown"

    try:
        result = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["kernel"] = result.stdout.strip()
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["gnuradio-companion", "--version"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        version_match = re.search(r'(\d+\.\d+\.\d+)', output)
        if version_match:
            info["gnuradio_version"] = version_match.group(1)
    except Exception:
        pass

    return info


def get_git_info() -> Dict[str, Any]:
    """采集 Git 信息"""
    info = {}
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            info["commit_hash"] = result.stdout.strip()

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            info["is_dirty"] = len(result.stdout.strip()) > 0
    except Exception:
        pass
    return info


def get_hackrf_info() -> Dict[str, Any]:
    """采集 HackRF 设备信息"""
    info = {"hackrf_count": 0, "devices": []}
    try:
        result = subprocess.run(["hackrf_info"], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        serial_matches = re.findall(r'Serial number:\s*(\S+)', output)
        firmware_matches = re.findall(r'Firmware Version:\s*(\S+)', output)
        info["hackrf_count"] = len(serial_matches)
        for i, (serial, fw) in enumerate(zip(serial_matches, firmware_matches)):
            role = "tx" if i == 0 else "rx" if i == 1 else f"device_{i}"
            info["devices"].append({"serial": serial, "role": role, "firmware": fw})
    except Exception:
        pass
    return info


def collect_metadata() -> Dict[str, Any]:
    """采集完整元数据"""
    return {
        "experiment_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": get_environment_info(),
        "git": get_git_info(),
        "hardware": get_hackrf_info()
    }


# =============================================================================
# Data Classes (aligned with sim/types.py)
# =============================================================================

@dataclass
class FrameRecord:
    """Record of a single frame transmission/reception."""
    timestamp: float
    frame_type: str          # "LEGIT" or "ATTACK"
    counter: Optional[int]
    command: str
    result: str              # "ACCEPT", "REJECT", "TIMEOUT", "DROPPED"
    reason: str
    latency_ms: float = 0.0


@dataclass
class RunResult:
    """Result of a single experiment run - mirrors sim.SimulationRunResult."""
    run_id: int
    mode: str
    window_size: int

    legit_sent: int = 0
    legit_accepted: int = 0
    legit_rejected: int = 0
    legit_timeout: int = 0

    attack_sent: int = 0
    attack_success: int = 0
    attack_rejected: int = 0
    attack_timeout: int = 0

    frames: List[FrameRecord] = field(default_factory=list)

    @property
    def legit_accept_rate(self) -> float:
        if self.legit_sent == 0:
            return 0.0
        return self.legit_accepted / self.legit_sent

    @property
    def attack_success_rate(self) -> float:
        if self.attack_sent == 0:
            return 0.0
        return self.attack_success / self.attack_sent


@dataclass
class ExperimentResult:
    """Aggregated result - mirrors sim.AggregateStats."""
    config_name: str
    mode: str
    window_size: int
    num_runs: int

    avg_legit_accept_rate: float
    std_legit_accept_rate: float
    avg_attack_success_rate: float
    std_attack_success_rate: float

    total_timeouts: int = 0
    p_loss_measured: float = 0.0
    p_reorder_measured: float = 0.0

    runs: List[RunResult] = field(default_factory=list)

    @property
    def avg_legit_rate(self) -> float:
        return self.avg_legit_accept_rate

    @property
    def std_legit_rate(self) -> float:
        return self.std_legit_accept_rate

    @property
    def avg_attack_rate(self) -> float:
        return self.avg_attack_success_rate

    @property
    def std_attack_rate(self) -> float:
        return self.std_attack_success_rate

    def as_dict(self) -> Dict[str, Any]:
        """
        Return a schema-compatible aggregate payload.
        Includes canonical sim keys and legacy physical keys.
        """
        return {
            "config_name": self.config_name,
            "mode": self.mode,
            "window_size": self.window_size,
            "num_runs": self.num_runs,
            "avg_legit_rate": self.avg_legit_rate,
            "std_legit_rate": self.std_legit_rate,
            "avg_attack_rate": self.avg_attack_rate,
            "std_attack_rate": self.std_attack_rate,
            "avg_legit_accept_rate": self.avg_legit_accept_rate,
            "std_legit_accept_rate": self.std_legit_accept_rate,
            "avg_attack_success_rate": self.avg_attack_success_rate,
            "std_attack_success_rate": self.std_attack_success_rate,
            "total_timeouts": self.total_timeouts,
            "p_loss_measured": self.p_loss_measured,
            "p_reorder_measured": self.p_reorder_measured,
        }


# =============================================================================
# Hardware Transport Layer - 使用 protocol.py 进行 Frame <-> RF 转换
# =============================================================================

class HardwareTransport:
    """
    Handles ZMQ communication with GNU Radio flowgraphs.

    架构:
        send_frame(): Frame -> FrameEncoder -> IQ samples -> ZMQ -> tx_flowgraph -> HackRF TX
        receive_frame(): HackRF RX -> rx_flowgraph -> ZMQ -> RF bytes -> FrameDecoder -> Frame
    """

    def __init__(self, config: Dict[str, Any]):
        """从配置初始化"""
        zmq_config = config["zmq"]
        self.tx_port = zmq_config["tx_port"]
        self.rx_port = zmq_config["rx_port"]
        self.host = zmq_config["host"]
        self.bind_all = bool(zmq_config.get("bind_all", False))
        self.bind_host = "*" if self.bind_all else "127.0.0.1"
        self.timeout_ms = zmq_config["timeout_ms"]
        self.hwm = zmq_config.get("hwm", 1000)
        self.is_loopback = False

        # 协议层
        protocol_config = config.get("protocol", {})
        shared_key = protocol_config.get("shared_key", "hardware_experiment_key_2024")
        nonce_bits = protocol_config.get("nonce_bits", 32)
        self.encoder = FrameEncoder(shared_key, nonce_bits=nonce_bits)
        self.decoder = FrameDecoder(shared_key, nonce_bits=nonce_bits)

        self.context: Optional[zmq.Context] = None
        self.tx_socket: Optional[zmq.Socket] = None
        self.rx_socket: Optional[zmq.Socket] = None
        self.connected = False

    def connect(self) -> bool:
        try:
            self.context = zmq.Context()

            # TX: PUSH socket 发送 IQ 样本到 tx_flowgraph
            # 重要: Python 端 bind，GNU Radio tx_flowgraph 端 connect
            self.tx_socket = self.context.socket(zmq.PUSH)
            self.tx_socket.setsockopt(zmq.LINGER, 0)
            self.tx_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
            self.tx_socket.setsockopt(zmq.SNDHWM, self.hwm)
            if hasattr(zmq, "REUSEADDR"):
                self.tx_socket.setsockopt(zmq.REUSEADDR, 1)
            self.tx_socket.bind(f"tcp://{self.bind_host}:{self.tx_port}")

            # RX: PULL socket 从 rx_flowgraph 接收帧
            self.rx_socket = self.context.socket(zmq.PULL)
            self.rx_socket.setsockopt(zmq.LINGER, 0)
            self.rx_socket.setsockopt(zmq.RCVHWM, self.hwm)
            if hasattr(zmq, "REUSEADDR"):
                self.rx_socket.setsockopt(zmq.REUSEADDR, 1)
            self.rx_socket.bind(f"tcp://{self.bind_host}:{self.rx_port}")
            self.rx_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)

            self.connected = True
            time.sleep(0.5)
            print(f"[HardwareTransport] Connected")
            print(f"  TX -> tcp://{self.bind_host}:{self.tx_port} (IQ samples)")
            print(f"  RX <- tcp://{self.bind_host}:{self.rx_port} (RF bytes)")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        if self.tx_socket:
            self.tx_socket.close(0)
            self.tx_socket = None
        if self.rx_socket:
            self.rx_socket.close(0)
            self.rx_socket = None
        if self.context:
            self.context.term()
            self.context = None
        self.connected = False

    def send_frame(self, frame: Frame) -> None:
        """
        将 Frame 编码为 IQ 样本并发送。

        流程:
            Frame -> FrameEncoder.encode_to_iq() -> complex64 array -> ZMQ -> tx_flowgraph
        """
        if not self.connected or self.tx_socket is None:
            raise RuntimeError("Transport is not connected")

        # 编码为 IQ 样本
        iq_samples = self.encoder.encode_to_iq(frame)
        payload = iq_samples.tobytes()

        # 发送 IQ 样本（直接发送 complex64 数据）
        # 若 GNU Radio 端暂未就绪，短暂重试后给出清晰错误信息。
        deadline = time.monotonic() + (self.timeout_ms / 1000.0)
        while True:
            try:
                self.tx_socket.send(payload, zmq.NOBLOCK)
                return
            except zmq.Again:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"TX socket not ready at tcp://{self.host}:{self.tx_port}. "
                        "请先启动并连接 TX flowgraph。"
                    )
                time.sleep(0.01)

    def _receive_frame_with_timeout(self, poll_timeout_ms: int) -> Optional[tuple[Frame, float]]:
        """Receive one frame with an explicit poll timeout."""
        try:
            if self.rx_socket.poll(poll_timeout_ms):
                rx_time = time.time()
                msg = self.rx_socket.recv()

                # 解析 ZMQ 消息格式: [msg_type(1)] [length(2)] [rf_bytes(var)] [timestamp(8)]
                if len(msg) < 3:
                    return None

                msg_type, length = struct.unpack(">BH", msg[:3])

                if msg_type != 0x01:  # MSG_TYPE_FRAME
                    return None

                if len(msg) < 3 + length:
                    return None

                rf_bytes = msg[3:3+length]

                # 解码 RF 字节为 Frame
                frame = self.decoder.decode_frame(rf_bytes)

                if frame is None:
                    return None

                # 提取时间戳（如果有）
                tx_time = rx_time
                if len(msg) >= 3 + length + 8:
                    try:
                        tx_time = struct.unpack(">d", msg[3+length:3+length+8])[0]
                    except struct.error:
                        pass

                latency_ms = (rx_time - tx_time) * 1000
                return frame, latency_ms

        except zmq.Again:
            # Timeout
            pass
        except Exception as e:
            print(f"[HardwareTransport] Receive error: {e}")

        return None

    def receive_frame(self) -> Optional[tuple[Frame, float]]:
        """
        从 ZMQ 接收 RF 字节并解码为 Frame。

        流程:
            rx_flowgraph -> ZMQ -> RF bytes -> FrameDecoder.decode_frame() -> Frame
        """
        return self._receive_frame_with_timeout(self.timeout_ms)

    def receive_frame_nowait(self) -> Optional[tuple[Frame, float]]:
        """Non-blocking receive used to drain stale frames before a run starts."""
        return self._receive_frame_with_timeout(0)


class LoopbackTransport:
    """Loopback transport for testing without hardware."""

    def __init__(self, p_loss: float, p_reorder: float, rng: Optional[RandomLike] = None):
        self._p_loss = p_loss
        self._p_reorder = p_reorder
        self._rng = rng
        self.channel = Channel(p_loss=p_loss, p_reorder=p_reorder, rng=rng or DeterministicRNG())
        self.pending_frames: List[Frame] = []
        self.connected = True
        self.is_loopback = True

    def set_rng(self, rng: RandomLike) -> None:
        """Update the RNG used by the channel."""
        self._rng = rng
        self.channel = Channel(p_loss=self._p_loss, p_reorder=self._p_reorder, rng=rng)
        self.pending_frames.clear()

    def connect(self) -> bool:
        return True

    def disconnect(self):
        pass

    def send_frame(self, frame: Frame) -> None:
        arrived = self.channel.send(frame)
        self.pending_frames.extend(arrived)

    def receive_frame(self) -> Optional[tuple[Frame, float]]:
        if self.pending_frames:
            frame = self.pending_frames.pop(0)
            return frame, 0.0
        return None

    def receive_all_pending(self) -> List[tuple[Frame, float]]:
        result = [(f, 0.0) for f in self.pending_frames]
        self.pending_frames.clear()
        return result

    def has_pending(self) -> bool:
        return len(self.pending_frames) > 0

    def flush(self) -> List[Frame]:
        remaining = self.channel.flush()
        self.pending_frames.extend(remaining)
        result = self.pending_frames.copy()
        self.pending_frames.clear()
        return result


# =============================================================================
# Hardware Experiment Runner
# =============================================================================

class HardwareExperiment:
    """Hardware experiment runner - 所有参数从配置读取"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metadata = collect_metadata()
        self.logger = self._setup_logger()
        self.transport = None

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("HardwareExperiment")
        if logger.handlers:
            return logger

        logger.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
        logger.addHandler(ch)

        logs_dir = PROJECT_ROOT / self.config["output"]["logs_dir"]
        logs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fh = logging.FileHandler(logs_dir / f"experiment_{timestamp}.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logger.addHandler(fh)

        return logger

    def connect(self, loopback: bool = False, p_loss: float = 0.0,
                p_reorder: float = 0.0, rng: Optional[RandomLike] = None) -> bool:
        """Connect to hardware or use loopback for testing."""
        if loopback:
            self.transport = LoopbackTransport(p_loss=p_loss, p_reorder=p_reorder, rng=rng)
            self.logger.info(f"Loopback mode: p_loss={p_loss}, p_reorder={p_reorder}")
        else:
            self.transport = HardwareTransport(self.config)
            self.logger.info("Hardware mode: connecting to GNU Radio...")

        return self.transport.connect()

    def disconnect(self):
        if self.transport:
            self.transport.disconnect()
        self.logger.info("Disconnected")

    def run_single_experiment(
        self,
        mode: Mode,
        window_size: int,
        run_id: int,
        rng: Optional[RandomLike] = None,
        num_legit_override: Optional[int] = None,
        num_attack_override: Optional[int] = None,
    ) -> RunResult:
        """Run single experiment - 参数从 self.config 读取，可通过 override 覆盖"""
        if rng is None:
            rng = DeterministicRNG()

        if hasattr(self.transport, "set_rng"):
            self.transport.set_rng(rng)

        # 从配置读取所有参数（支持 override）
        traffic_config = self.config["traffic"]
        num_legit = num_legit_override if num_legit_override is not None else traffic_config["num_legit_frames"]
        num_replay = num_attack_override if num_attack_override is not None else traffic_config["num_replay_attempts"]
        frame_interval = traffic_config["frame_interval_ms"] / 1000.0
        commands = traffic_config["commands"]

        protocol_config = self.config["protocol"]
        shared_key = protocol_config["shared_key"]
        mac_length = protocol_config["mac_length"]
        challenge_nonce_bits = protocol_config["nonce_bits"]

        attack_config = self.config["attack"]
        attack_mode_str = attack_config["mode"]
        attack_mode = AttackMode.POST_RUN if attack_mode_str == "post" else AttackMode.INLINE
        inline_attack_probability = attack_config["inline_probability"]
        inline_attack_burst = attack_config["inline_burst"]

        attacker_config = self.config["attacker"]
        attacker_record_loss = attacker_config["record_loss"]
        attacker_target_commands = attacker_config["target_commands"]

        # Initialize components
        sender = Sender(mode=mode, shared_key=shared_key, mac_length=mac_length)
        receiver = Receiver(
            mode=mode, shared_key=shared_key, mac_length=mac_length,
            window_size=window_size if window_size else 1
        )
        attacker = Attacker(record_loss=attacker_record_loss, target_commands=attacker_target_commands)
        is_loopback = getattr(self.transport, "is_loopback", False)

        result = RunResult(run_id=run_id, mode=mode.value, window_size=window_size)
        remaining_replays = num_replay

        if not is_loopback and hasattr(self.transport, "receive_frame_nowait"):
            drained = 0
            while True:
                stale = self.transport.receive_frame_nowait()
                if stale is None:
                    break
                drained += 1
                if drained >= 1000:
                    break
            if drained > 0:
                self.logger.warning(
                    f"Run {run_id}: cleared {drained} stale frame(s) from RX queue before start"
                )

        def process_frame(frame: Frame) -> bool:
            verification = receiver.process(frame)
            is_attack = bool(frame.is_attack)
            if verification.accepted:
                if is_attack:
                    result.attack_success += 1
                else:
                    result.legit_accepted += 1
            else:
                if is_attack:
                    result.attack_rejected += 1
                else:
                    result.legit_rejected += 1
            return verification.accepted

        self.logger.info(f"Run {run_id}: mode={mode.value}, window={window_size}, "
                         f"legit={num_legit}, replay={num_replay}, attack_mode={attack_mode.value}")

        # PHASE 1: Legitimate traffic
        for i in range(num_legit):
            command = rng.choice(list(commands))

            nonce = None
            if mode is Mode.CHALLENGE:
                nonce = receiver.issue_nonce(rng, bits=challenge_nonce_bits)

            frame = sender.next_frame(command, nonce=nonce)
            result.legit_sent += 1

            attacker.observe(frame, rng)

            tx_time = time.time()
            self.transport.send_frame(frame)

            if is_loopback:
                for rx_frame, latency_ms in self.transport.receive_all_pending():
                    process_frame(rx_frame)
            else:
                rx_result = self.transport.receive_frame()
                if rx_result:
                    rx_frame, latency_ms = rx_result
                    accepted = process_frame(rx_frame)
                    result.frames.append(FrameRecord(
                        timestamp=tx_time,
                        frame_type="ATTACK" if rx_frame.is_attack else "LEGIT",
                        counter=rx_frame.counter,
                        command=rx_frame.command,
                        result="ACCEPT" if accepted else "REJECT",
                        reason="processed", latency_ms=latency_ms
                    ))
                else:
                    result.legit_timeout += 1
                    result.frames.append(FrameRecord(
                        timestamp=tx_time, frame_type="LEGIT", counter=frame.counter,
                        command=frame.command, result="TIMEOUT", reason="no_response", latency_ms=0
                    ))

            # Inline attacks
            if attack_mode is AttackMode.INLINE:
                for _ in range(max(1, inline_attack_burst)):
                    if remaining_replays <= 0:
                        break
                    if rng.random() >= inline_attack_probability:
                        break

                    attack_frame = attacker.pick_frame(rng)
                    if attack_frame is None:
                        break

                    result.attack_sent += 1
                    remaining_replays -= 1
                    attack_frame.is_attack = True

                    attack_tx_time = time.time()
                    self.transport.send_frame(attack_frame)

                    if is_loopback:
                        for rx_frame, latency_ms in self.transport.receive_all_pending():
                            process_frame(rx_frame)
                    else:
                        rx_result = self.transport.receive_frame()
                        if rx_result:
                            rx_frame, latency_ms = rx_result
                            accepted = process_frame(rx_frame)
                            result.frames.append(FrameRecord(
                                timestamp=attack_tx_time,
                                frame_type="ATTACK" if rx_frame.is_attack else "LEGIT",
                                counter=rx_frame.counter,
                                command=rx_frame.command,
                                result="ACCEPT" if accepted else "REJECT",
                                reason="processed",
                                latency_ms=latency_ms
                            ))
                        else:
                            result.attack_timeout += 1
                            result.frames.append(FrameRecord(
                                timestamp=attack_tx_time,
                                frame_type="ATTACK",
                                counter=attack_frame.counter,
                                command=attack_frame.command,
                                result="TIMEOUT",
                                reason="no_response",
                                latency_ms=0
                            ))

            time.sleep(frame_interval)

        # PHASE 2: Post-run attacks
        if attack_mode is AttackMode.POST_RUN:
            if is_loopback:
                for frame in self.transport.flush():
                    process_frame(frame)

            for _ in range(remaining_replays):
                attack_frame = attacker.pick_frame(rng)
                if attack_frame is None:
                    break

                result.attack_sent += 1
                attack_frame.is_attack = True

                tx_time = time.time()
                self.transport.send_frame(attack_frame)

                if is_loopback:
                    for rx_frame, latency_ms in self.transport.receive_all_pending():
                        process_frame(rx_frame)
                else:
                    rx_result = self.transport.receive_frame()
                    if rx_result:
                        rx_frame, latency_ms = rx_result
                        accepted = process_frame(rx_frame)
                        result.frames.append(FrameRecord(
                            timestamp=tx_time,
                            frame_type="ATTACK" if rx_frame.is_attack else "LEGIT",
                            counter=rx_frame.counter,
                            command=rx_frame.command,
                            result="ACCEPT" if accepted else "REJECT",
                            reason="processed", latency_ms=latency_ms
                        ))
                    else:
                        result.attack_timeout += 1

                time.sleep(frame_interval)

        # Final flush
        if is_loopback:
            for frame in self.transport.flush():
                process_frame(frame)

        self.logger.info(
            f"  Result: Legit={result.legit_accepted}/{result.legit_sent} "
            f"({result.legit_accept_rate:.1%}), "
            f"Attack={result.attack_success}/{result.attack_sent} "
            f"({result.attack_success_rate:.1%}), "
            f"Timeouts={result.legit_timeout + result.attack_timeout}"
        )

        return result

    def run_experiment_sweep(
        self,
        modes: List[str],
        window_sizes: List[int],
        num_runs: int,
    ) -> List[ExperimentResult]:
        """Run sweep across modes and window sizes - 参数从配置读取"""
        seed = self.config["experiment"]["random_seed"]
        results: List[ExperimentResult] = []

        for mode_str in modes:
            mode = Mode(mode_str)
            test_window_sizes = window_sizes if mode == Mode.WINDOW else [0]

            for ws in test_window_sizes:
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"Testing: mode={mode_str}, window_size={ws}")
                self.logger.info(f"{'='*60}")

                run_results: List[RunResult] = []
                rng = DeterministicRNG(seed)

                for run_id in range(1, num_runs + 1):
                    run_result = self.run_single_experiment(
                        mode=mode, window_size=ws, run_id=run_id, rng=rng
                    )
                    run_results.append(run_result)

                legit_rates = [r.legit_accept_rate for r in run_results]
                attack_rates = [r.attack_success_rate for r in run_results]

                exp_result = ExperimentResult(
                    config_name=f"{mode_str}_w{ws}",
                    mode=mode_str,
                    window_size=ws,
                    num_runs=num_runs,
                    avg_legit_accept_rate=statistics.mean(legit_rates),
                    std_legit_accept_rate=statistics.pstdev(legit_rates) if len(legit_rates) > 1 else 0.0,
                    avg_attack_success_rate=statistics.mean(attack_rates),
                    std_attack_success_rate=statistics.pstdev(attack_rates) if len(attack_rates) > 1 else 0.0,
                    total_timeouts=sum(r.legit_timeout + r.attack_timeout for r in run_results),
                    runs=run_results
                )
                results.append(exp_result)

                self.logger.info(f"Aggregate: Legit={exp_result.avg_legit_accept_rate:.1%}, "
                                f"Attack={exp_result.avg_attack_success_rate:.1%}")

        return results

    def save_results(self, results: List[ExperimentResult], prefix: str = "experiment"):
        """Save results with full metadata."""
        results_dir = PROJECT_ROOT / self.config["output"]["results_dir"]
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON with full metadata
        json_file = results_dir / f"{prefix}_{timestamp}.json"
        json_data = {
            "metadata": self.metadata,
            "config": self.config,
            "results": [
                {
                    **exp.as_dict(),
                    "runs": [
                        {
                            "run_id": r.run_id,
                            "legit_sent": r.legit_sent,
                            "legit_accepted": r.legit_accepted,
                            "attack_sent": r.attack_sent,
                            "attack_success": r.attack_success
                        }
                        for r in exp.runs
                    ]
                }
                for exp in results
            ]
        }

        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Saved: {json_file}")

        # CSV
        csv_file = results_dir / f"{prefix}_{timestamp}.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "mode", "window_size", "num_runs",
                "avg_legit_rate", "std_legit_rate",
                "avg_attack_rate", "std_attack_rate",
                "total_timeouts"
            ])
            for exp in results:
                writer.writerow([
                    exp.mode, exp.window_size, exp.num_runs,
                    f"{exp.avg_legit_accept_rate:.4f}",
                    f"{exp.std_legit_accept_rate:.4f}",
                    f"{exp.avg_attack_success_rate:.4f}",
                    f"{exp.std_attack_success_rate:.4f}",
                    exp.total_timeouts
                ])
        self.logger.info(f"Saved: {csv_file}")

        return json_file, csv_file


# =============================================================================
# CLI
# =============================================================================

def load_config(config_path: Optional[str]) -> Dict[str, Any]:
    """加载配置文件 - 必须指定配置文件"""
    if config_path is None:
        # 使用默认配置文件路径
        config_path = PROJECT_ROOT / "physical_experiment/configs/experiment_config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {config_path}\n"
            f"请确保 experiment_config.yaml 存在，所有参数必须在配置文件中定义。"
        )

    with open(config_path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Hardware Experiment Runner - 从 YAML 配置读取所有参数",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置运行
  python experiment_runner.py

  # 指定配置文件
  python experiment_runner.py --config ../configs/experiment_config.yaml

  # 覆盖模式和窗口大小
  python experiment_runner.py --mode window --window-size 5

  # Loopback 测试（无需硬件）
  python experiment_runner.py --loopback --p-loss 0.1

  # 快速测试
  python experiment_runner.py --quick --loopback
"""
    )

    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--mode", type=str, help="单一模式测试")
    parser.add_argument("--modes", type=str, nargs="+", help="多模式测试")
    parser.add_argument("--window-size", type=int, help="窗口大小（覆盖配置）")
    parser.add_argument("--window-sizes", type=int, nargs="+", help="多窗口大小测试")
    parser.add_argument("--runs", type=int, help="运行次数（覆盖配置）")
    parser.add_argument("--loopback", action="store_true", help="Loopback 模式（无需硬件）")
    parser.add_argument("--p-loss", type=float, help="Loopback 丢包率")
    parser.add_argument("--p-reorder", type=float, help="Loopback 重排率")
    parser.add_argument(
        "--bind-all",
        action="store_true",
        help="Bind ZMQ sockets to all interfaces. Default: localhost only.",
    )
    parser.add_argument("--quick", action="store_true", help="快速测试模式")
    parser.add_argument("--dry-run", action="store_true", help="只显示配置")

    args = parser.parse_args()

    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # CLI 参数覆盖配置（不提供默认值，只在指定时覆盖）
    if args.quick:
        config["experiment"]["runs_per_config"] = 2
        config["traffic"]["num_legit_frames"] = 10
        config["traffic"]["num_replay_attempts"] = 20

    config.setdefault("zmq", {})["bind_all"] = args.bind_all

    # 确定测试参数
    if args.modes:
        modes = args.modes
    elif args.mode:
        modes = [args.mode]
    else:
        # 从配置中读取启用的模式
        modes = [m["name"] for m in config.get("modes", []) if m.get("enabled", True)]
        if not modes:
            modes = ["window"]

    if args.window_sizes:
        window_sizes = args.window_sizes
    elif args.window_size is not None:
        window_sizes = [args.window_size]
    else:
        # 从配置中读取 window 模式的窗口大小
        for m in config.get("modes", []):
            if m["name"] == "window" and "window_sizes" in m:
                window_sizes = m["window_sizes"]
                break
        else:
            window_sizes = [5]

    num_runs = args.runs if args.runs is not None else config["experiment"]["runs_per_config"]

    # Loopback 参数
    p_loss = args.p_loss if args.p_loss is not None else config.get("channel", {}).get("p_loss", 0.0)
    p_reorder = args.p_reorder if args.p_reorder is not None else config.get("channel", {}).get("p_reorder", 0.0)

    if args.dry_run:
        print("配置:")
        print(yaml.dump(config, default_flow_style=False, allow_unicode=True))
        print(f"\n模式: {modes}")
        print(f"窗口大小: {window_sizes}")
        print(f"运行次数: {num_runs}")
        if args.loopback:
            print(f"Loopback: p_loss={p_loss}, p_reorder={p_reorder}")
        return

    experiment = HardwareExperiment(config)

    try:
        seed = config["experiment"]["random_seed"]
        rng = DeterministicRNG(seed)

        if not experiment.connect(loopback=args.loopback, p_loss=p_loss, p_reorder=p_reorder, rng=rng):
            print("连接失败")
            sys.exit(1)

        results = experiment.run_experiment_sweep(
            modes=modes,
            window_sizes=window_sizes,
            num_runs=num_runs,
        )

        experiment.save_results(results)

        print("\n" + "="*60)
        print("总结")
        print("="*60)
        for exp in results:
            print(f"{exp.config_name}: Legit={exp.avg_legit_accept_rate:.1%}, "
                  f"Attack={exp.avg_attack_success_rate:.1%}")

    except KeyboardInterrupt:
        print("\n中断")
    except RuntimeError as e:
        print(f"运行失败: {e}")
        sys.exit(1)
    finally:
        experiment.disconnect()


if __name__ == "__main__":
    main()
