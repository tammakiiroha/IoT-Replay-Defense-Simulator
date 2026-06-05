#!/usr/bin/env python3
"""
GNU Radio RX Flowgraph - 帧接收器

对应论文参数:
- 频率: 2.475 GHz (论文3.3节)
- 采样率: 2 Msps
- 调制: 2値FSK
- 频偏: ~101.5 kHz (论文3.4节)
- Samples/Symbol: 2

架构:
    [HackRF Source] --> [FSK解调] --> [帧检测] --> [ZMQ PUSH]
                                                        |
                                                        v
                                        Python Script (experiment_runner.py)

ZMQ 消息格式:
    [msg_type(1)] [length(2)] [rf_frame_bytes(var)] [rssi(4)] [timestamp(8)]
"""
from __future__ import annotations

import struct
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import zmq
except ImportError as exc:
    message = "pyzmq not installed. Run: pip install pyzmq"
    if __name__ == "__main__":
        print(f"Error: {message}")
        sys.exit(1)
    raise ImportError(message) from exc

try:
    from gnuradio import gr, blocks, digital, filter as gr_filter, analog
    from gnuradio.filter import firdes
    import osmosdr
except ImportError as exc:
    message = "GNU Radio not installed. Run: sudo apt-get install gnuradio gr-osmosdr"
    if __name__ == "__main__":
        print(f"Error: {message}")
        sys.exit(1)
    raise ImportError(message) from exc

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from physical_experiment.runtime import load_experiment_config, resolve_hackrf_device_args


# =============================================================================
# 论文参数（默认值，实际从配置文件读取）
# =============================================================================

DEFAULT_FREQUENCY_HZ = 2475000000      # 2.475 GHz (论文3.3节)
DEFAULT_SAMPLE_RATE_HZ = 2000000       # 2 Msps
DEFAULT_DEVIATION_HZ = 101562          # ~101.5 kHz (论文3.4节)
DEFAULT_SAMPLES_PER_SYMBOL = 2         # 论文3.4节
DEFAULT_LNA_GAIN_DB = 24
DEFAULT_VGA_GAIN_DB = 20
DEFAULT_ZMQ_RX_PORT = 5556

# 帧参数
PREAMBLE_BYTES = bytes([0xAA, 0xAA, 0xAA, 0xAA])  # 同步字
SYNC_WORD = bytes([0xA5, 0xA5])                    # 帧起始标志
FRAME_LENGTH_BYTES = 40                             # 完整帧长度（preamble + sync + payload + crc）


def load_config(config_path: Optional[str] = None) -> dict:
    """从配置文件加载参数"""
    return load_experiment_config(config_path)


class FrameDetector(gr.sync_block):
    """
    自定义 GNU Radio 块：检测并提取帧

    输入: 解调后的比特流 (uint8)
    输出: 通过 ZMQ 发送完整帧

    帧格式:
        [Preamble(4B)] [SyncWord(2B)] [Payload(32B)] [CRC(2B)]
    """

    def __init__(
        self,
        zmq_port: int = DEFAULT_ZMQ_RX_PORT,
        frame_length: int = FRAME_LENGTH_BYTES
    ):
        gr.sync_block.__init__(
            self,
            name="Frame Detector",
            in_sig=[np.uint8],
            out_sig=None
        )

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect(f"tcp://127.0.0.1:{zmq_port}")

        self.frame_length = frame_length
        self.frame_length_bits = frame_length * 8

        # 同步字模式 (0xA5A5 in bits)
        self.sync_pattern = np.array([
            1, 0, 1, 0, 0, 1, 0, 1,  # 0xA5
            1, 0, 1, 0, 0, 1, 0, 1   # 0xA5
        ], dtype=np.uint8)

        # 比特缓冲区
        self.bit_buffer = np.array([], dtype=np.uint8)
        self.max_buffer = self.frame_length_bits * 4  # 最多缓存4个帧

        # 统计
        self.frames_detected = 0

        print(f"[FrameDetector] Initialized")
        print(f"  ZMQ Port: {zmq_port}")
        print(f"  Frame length: {frame_length} bytes")

    def work(self, input_items, output_items):
        in_data = input_items[0]

        # 添加到缓冲区
        self.bit_buffer = np.concatenate([self.bit_buffer, in_data])

        # 限制缓冲区大小
        if len(self.bit_buffer) > self.max_buffer:
            self.bit_buffer = self.bit_buffer[-self.max_buffer:]

        # 查找同步字
        while len(self.bit_buffer) >= self.frame_length_bits:
            sync_idx = self._find_sync()

            if sync_idx is None:
                # 没找到同步字，保留可能的部分同步字
                if len(self.bit_buffer) > len(self.sync_pattern):
                    self.bit_buffer = self.bit_buffer[-(len(self.sync_pattern) - 1):]
                break

            # 检查是否有完整帧
            # 同步字前面应该有 preamble (32 bits)
            preamble_start = sync_idx - 32

            if preamble_start < 0:
                # preamble 不完整，等待更多数据
                break

            frame_end = preamble_start + self.frame_length_bits

            if frame_end > len(self.bit_buffer):
                # 帧不完整，等待更多数据
                break

            # 提取完整帧
            frame_bits = self.bit_buffer[preamble_start:frame_end]
            frame_bytes = self._bits_to_bytes(frame_bits)

            # 验证 preamble
            if self._verify_preamble(frame_bytes[:4]):
                # 发送帧
                self._send_frame(frame_bytes)
                self.frames_detected += 1

            # 移除已处理的数据
            self.bit_buffer = self.bit_buffer[frame_end:]

        return len(in_data)

    def _find_sync(self) -> Optional[int]:
        """查找同步字位置"""
        for i in range(len(self.bit_buffer) - len(self.sync_pattern) + 1):
            if np.array_equal(self.bit_buffer[i:i+len(self.sync_pattern)], self.sync_pattern):
                return i
        return None

    def _bits_to_bytes(self, bits: np.ndarray) -> bytes:
        """比特数组转字节"""
        byte_list = []
        for i in range(0, len(bits) - 7, 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | int(bits[i + j])
            byte_list.append(byte)
        return bytes(byte_list)

    def _verify_preamble(self, preamble: bytes) -> bool:
        """验证 preamble"""
        # 允许一定的误码率
        expected = PREAMBLE_BYTES
        errors = sum(bin(a ^ b).count('1') for a, b in zip(preamble, expected))
        return errors <= 4  # 最多 4 位错误

    def _send_frame(self, frame_bytes: bytes):
        """通过 ZMQ 发送帧"""
        # 消息格式: [msg_type(1)] [length(2)] [frame_bytes(var)] [timestamp(8)]
        msg_type = 0x01  # MSG_TYPE_FRAME
        length = len(frame_bytes)
        timestamp = time.time()

        header = struct.pack(">BH", msg_type, length)
        trailer = struct.pack(">d", timestamp)

        self.socket.send(header + frame_bytes + trailer, zmq.NOBLOCK)

    def stop(self):
        print(f"[FrameDetector] Detected {self.frames_detected} frames")
        self.socket.close()
        self.context.term()
        return True


class IQFrameDetector(gr.sync_block):
    """
    自定义 GNU Radio 块：从 IQ 样本中检测帧

    输入: 复数 IQ 样本 (complex64)
    输出: 通过 ZMQ 发送完整帧

    这个块集成了 FSK 解调和帧检测
    """

    def __init__(
        self,
        zmq_port: int = DEFAULT_ZMQ_RX_PORT,
        samples_per_symbol: int = DEFAULT_SAMPLES_PER_SYMBOL,
        deviation_hz: float = DEFAULT_DEVIATION_HZ,
        sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
        frame_length: int = FRAME_LENGTH_BYTES
    ):
        gr.sync_block.__init__(
            self,
            name="IQ Frame Detector",
            in_sig=[np.complex64],
            out_sig=None
        )

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect(f"tcp://127.0.0.1:{zmq_port}")

        self.samples_per_symbol = samples_per_symbol
        self.deviation_hz = deviation_hz
        self.sample_rate_hz = sample_rate_hz
        self.frame_length = frame_length
        self.frame_length_bits = frame_length * 8
        self.frame_length_samples = self.frame_length_bits * samples_per_symbol

        # FSK 解调参数
        self.freq_offset = deviation_hz / sample_rate_hz * 2 * np.pi

        # 同步字模式 (0xA5A5)
        self.sync_pattern = np.array([
            1, 0, 1, 0, 0, 1, 0, 1,  # 0xA5
            1, 0, 1, 0, 0, 1, 0, 1   # 0xA5
        ], dtype=np.uint8)

        # 样本缓冲区
        self.sample_buffer = np.array([], dtype=np.complex64)
        self.max_buffer = self.frame_length_samples * 4

        # 上一个相位（用于相位连续性）
        self.last_phase = 0.0

        # 统计
        self.frames_detected = 0

        print(f"[IQFrameDetector] Initialized (论文参数)")
        print(f"  采样率: {sample_rate_hz/1e6:.1f} Msps")
        print(f"  频偏: {deviation_hz/1e3:.1f} kHz")
        print(f"  Samples/Symbol: {samples_per_symbol}")

    def work(self, input_items, output_items):
        in_data = input_items[0]

        # 添加到缓冲区
        self.sample_buffer = np.concatenate([self.sample_buffer, in_data])

        # 限制缓冲区大小
        if len(self.sample_buffer) > self.max_buffer:
            self.sample_buffer = self.sample_buffer[-self.max_buffer:]

        # 需要足够样本才能处理
        min_samples = self.frame_length_samples + 100
        if len(self.sample_buffer) < min_samples:
            return len(in_data)

        # FSK 解调
        bits = self._fsk_demodulate(self.sample_buffer)

        # 查找帧
        frame_bytes = self._detect_frame(bits)

        if frame_bytes is not None:
            self._send_frame(frame_bytes)
            self.frames_detected += 1
            # 移除已处理的样本
            consumed = self.frame_length_samples
            self.sample_buffer = self.sample_buffer[consumed:]

        return len(in_data)

    def _fsk_demodulate(self, samples: np.ndarray) -> np.ndarray:
        """FSK 解调"""
        # 计算瞬时频率
        phase = np.angle(samples)
        freq = np.diff(np.unwrap(phase))

        # 按符号周期平均
        num_symbols = len(freq) // self.samples_per_symbol
        if num_symbols == 0:
            return np.array([], dtype=np.uint8)

        freq_trimmed = freq[:num_symbols * self.samples_per_symbol]
        freq_symbols = freq_trimmed.reshape(-1, self.samples_per_symbol).mean(axis=1)

        # 判决
        bits = (freq_symbols > 0).astype(np.uint8)

        return bits

    def _detect_frame(self, bits: np.ndarray) -> Optional[bytes]:
        """检测帧"""
        if len(bits) < self.frame_length_bits:
            return None

        # 查找同步字
        for i in range(len(bits) - len(self.sync_pattern) - self.frame_length_bits + 32):
            if np.array_equal(bits[i:i+len(self.sync_pattern)], self.sync_pattern):
                # 找到同步字
                preamble_start = i - 32  # preamble 在同步字前面

                if preamble_start < 0:
                    continue

                frame_end = preamble_start + self.frame_length_bits

                if frame_end > len(bits):
                    continue

                # 提取帧
                frame_bits = bits[preamble_start:frame_end]
                frame_bytes = self._bits_to_bytes(frame_bits)

                # 验证
                if self._verify_frame(frame_bytes):
                    return frame_bytes

        return None

    def _bits_to_bytes(self, bits: np.ndarray) -> bytes:
        """比特转字节"""
        byte_list = []
        for i in range(0, len(bits) - 7, 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | int(bits[i + j])
            byte_list.append(byte)
        return bytes(byte_list)

    def _verify_frame(self, frame_bytes: bytes) -> bool:
        """验证帧"""
        if len(frame_bytes) < 6:
            return False

        # 验证 preamble
        preamble = frame_bytes[:4]
        errors = sum(bin(a ^ b).count('1') for a, b in zip(preamble, PREAMBLE_BYTES))
        if errors > 4:
            return False

        # 验证 sync word
        sync = frame_bytes[4:6]
        errors = sum(bin(a ^ b).count('1') for a, b in zip(sync, SYNC_WORD))
        if errors > 2:
            return False

        return True

    def _send_frame(self, frame_bytes: bytes):
        """发送帧"""
        msg_type = 0x01
        length = len(frame_bytes)
        timestamp = time.time()

        header = struct.pack(">BH", msg_type, length)
        trailer = struct.pack(">d", timestamp)

        try:
            self.socket.send(header + frame_bytes + trailer, zmq.NOBLOCK)
        except Exception:
            pass

    def stop(self):
        print(f"[IQFrameDetector] Detected {self.frames_detected} frames")
        self.socket.close()
        self.context.term()
        return True


class RxFlowgraph(gr.top_block):
    """
    接收端流图

    架构:
        [HackRF Source] --> [IQ Frame Detector] --> [ZMQ PUSH]
    """

    def __init__(
        self,
        frequency: float = DEFAULT_FREQUENCY_HZ,
        sample_rate: float = DEFAULT_SAMPLE_RATE_HZ,
        deviation: float = DEFAULT_DEVIATION_HZ,
        samples_per_symbol: int = DEFAULT_SAMPLES_PER_SYMBOL,
        lna_gain: int = DEFAULT_LNA_GAIN_DB,
        vga_gain: int = DEFAULT_VGA_GAIN_DB,
        zmq_port: int = DEFAULT_ZMQ_RX_PORT,
        device_args: str = ""
    ):
        gr.top_block.__init__(self, "IoT Replay Defense RX (论文参数)")

        ##################################################
        # 变量
        ##################################################
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.deviation = deviation
        self.samples_per_symbol = samples_per_symbol
        self.lna_gain = lna_gain
        self.vga_gain = vga_gain

        ##################################################
        # Blocks
        ##################################################

        # HackRF Source
        hackrf_args = f"numchan=1 {device_args}".strip()
        self.hackrf_source = osmosdr.source(args=hackrf_args)
        self.hackrf_source.set_sample_rate(sample_rate)
        self.hackrf_source.set_center_freq(frequency, 0)
        self.hackrf_source.set_freq_corr(0, 0)
        self.hackrf_source.set_dc_offset_mode(0, 0)
        self.hackrf_source.set_iq_balance_mode(0, 0)
        self.hackrf_source.set_gain_mode(False, 0)
        self.hackrf_source.set_gain(lna_gain, 0)
        self.hackrf_source.set_if_gain(vga_gain, 0)
        self.hackrf_source.set_bb_gain(20, 0)
        self.hackrf_source.set_antenna("", 0)
        self.hackrf_source.set_bandwidth(0, 0)

        # 自定义帧检测器
        self.frame_detector = IQFrameDetector(
            zmq_port=zmq_port,
            samples_per_symbol=samples_per_symbol,
            deviation_hz=deviation,
            sample_rate_hz=sample_rate
        )

        ##################################################
        # Connections
        ##################################################

        self.connect(self.hackrf_source, self.frame_detector)

        print(f"RX Flowgraph initialized (论文参数):")
        print(f"  频率: {frequency/1e9:.4f} GHz")
        print(f"  采样率: {sample_rate/1e6:.1f} Msps")
        print(f"  频偏: {deviation/1e3:.1f} kHz")
        print(f"  Samples/Symbol: {samples_per_symbol}")
        print(f"  LNA Gain: {lna_gain} dB")
        print(f"  VGA Gain: {vga_gain} dB")
        print(f"  ZMQ Port: {zmq_port}")


def main():
    import argparse

    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    config_args, _ = config_parser.parse_known_args()

    # 加载配置
    try:
        config = load_config(config_args.config)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    hw_config = config.get("hardware", {})
    zmq_config = config.get("zmq", {})
    mod_config = hw_config.get("modulation", {})
    rx_config = hw_config.get("rx", {})

    parser = argparse.ArgumentParser(
        description="RX Flowgraph - 帧接收器 (论文参数)",
        parents=[config_parser],
    )
    parser.add_argument("--freq", type=float,
                        default=hw_config.get("frequency_hz", DEFAULT_FREQUENCY_HZ),
                        help="中心频率 (Hz)")
    parser.add_argument("--rate", type=float,
                        default=hw_config.get("sample_rate_hz", DEFAULT_SAMPLE_RATE_HZ),
                        help="采样率 (Hz)")
    parser.add_argument("--deviation", type=float,
                        default=mod_config.get("deviation_hz", DEFAULT_DEVIATION_HZ),
                        help="FSK 频偏 (Hz)")
    parser.add_argument("--sps", type=int,
                        default=mod_config.get("samples_per_symbol", DEFAULT_SAMPLES_PER_SYMBOL),
                        help="Samples per symbol")
    parser.add_argument("--lna-gain", type=int,
                        default=rx_config.get("lna_gain_db", DEFAULT_LNA_GAIN_DB),
                        help="LNA 增益 (dB)")
    parser.add_argument("--vga-gain", type=int,
                        default=rx_config.get("vga_gain_db", DEFAULT_VGA_GAIN_DB),
                        help="VGA 增益 (dB)")
    parser.add_argument("--zmq-port", type=int,
                        default=zmq_config.get("rx_port", DEFAULT_ZMQ_RX_PORT),
                        help="ZMQ 端口")
    parser.add_argument("--device", type=str,
                        default=rx_config.get("device_args", ""),
                        help="HackRF 设备参数 (完整的 device_args 字符串)")
    parser.add_argument("--hackrf-serial", type=str,
                        default="",
                        help="HackRF 设备序列号 (用于指定特定设备，如有多台)")

    args = parser.parse_args()

    # 构建 device_args
    device_args = resolve_hackrf_device_args(
        config,
        "rx",
        device_args_override=args.device,
        serial_override=args.hackrf_serial,
    )
    if device_args:
        print(f"使用设备参数: {device_args}")

    tb = RxFlowgraph(
        frequency=args.freq,
        sample_rate=args.rate,
        deviation=args.deviation,
        samples_per_symbol=args.sps,
        lna_gain=args.lna_gain,
        vga_gain=args.vga_gain,
        zmq_port=args.zmq_port,
        device_args=device_args
    )

    print("\n启动 RX 流图... 按 Ctrl+C 停止")
    tb.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    tb.stop()
    tb.wait()
    print("RX 流图已停止")


if __name__ == "__main__":
    main()
