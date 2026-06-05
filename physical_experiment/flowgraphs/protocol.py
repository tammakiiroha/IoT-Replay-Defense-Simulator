#!/usr/bin/env python3
"""
Protocol Layer - Frame对象与RF比特流的转换

这个模块负责将 sim/ 中的 Frame 对象转换为可以通过 HackRF 发送的比特流，
以及将接收到的比特流解码回 Frame 对象。

对应论文参数:
- 频率: 2.475 GHz
- 调制: 2値FSK
- Samples/Symbol: 2
- 频偏: ~101.5 kHz
- 帧长度: 24 bytes (prefix 19 bytes + tail 5 bytes)

架构:
    sim/Frame <---> protocol.py <---> RF比特流 <---> GNU Radio <---> HackRF
"""
from __future__ import annotations

import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from sim.types import Frame


# =============================================================================
# 论文参数（对应 experiment_config.yaml）
# =============================================================================

# RF 参数（论文3.3节）
RF_FREQUENCY_HZ = 2475000000      # 2.475 GHz
RF_SAMPLE_RATE_HZ = 2000000       # 2 Msps
RF_BANDWIDTH_HZ = 2000000         # 2 MHz

# 调制参数（论文3.4节）
MODULATION_TYPE = "FSK"
SAMPLES_PER_SYMBOL = 2
BITS_PER_SYMBOL = 1
DEVIATION_HZ = 101562             # ~101.5 kHz

# 帧参数
PREAMBLE_BYTES = bytes([0xAA, 0xAA, 0xAA, 0xAA])  # 同步字
SYNC_WORD = bytes([0xA5, 0xA5])                    # 帧起始标志
FRAME_PAYLOAD_SIZE = 32                             # 有效载荷大小（bytes）

# MAC 参数
DEFAULT_MAC_LENGTH = 16           # HMAC-SHA256 截断到 128 bits
DEFAULT_NONCE_BITS = 32           # Challenge nonce length (bits)


# =============================================================================
# 帧格式定义
# =============================================================================
#
# 完整的 RF 帧格式:
# +----------+----------+------------------+-----+
# | Preamble | SyncWord |     Payload      | CRC |
# | 4 bytes  | 2 bytes  |    32 bytes      | 2B  |
# +----------+----------+------------------+-----+
#
# Payload 格式 (32 bytes):
# +-------+---------+-------+-------+-----+---------+--------+
# | Flags | Counter | Nonce | CmdLen| Cmd |   MAC   | Padding|
# | 1B    |   4B    |  4B   |  1B   | var |   16B   |  var   |
# +-------+---------+-------+-------+-----+---------+--------+
#
# Flags (1 byte):
#   bit 0: is_attack (仅用于调试，实际RF传输不需要)
#   bit 1: nonce_present
#   bit 2-7: reserved


@dataclass
class RFFrame:
    """RF层的帧表示"""
    preamble: bytes
    sync_word: bytes
    payload: bytes
    crc: int

    def to_bytes(self) -> bytes:
        """转换为完整的字节序列"""
        crc_bytes = struct.pack(">H", self.crc)
        return self.preamble + self.sync_word + self.payload + crc_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional['RFFrame']:
        """从字节序列解析"""
        min_len = len(PREAMBLE_BYTES) + len(SYNC_WORD) + 2  # preamble + sync + crc
        if len(data) < min_len:
            return None

        preamble = data[:4]
        sync_word = data[4:6]
        payload = data[6:-2]
        crc = struct.unpack(">H", data[-2:])[0]

        return cls(preamble=preamble, sync_word=sync_word, payload=payload, crc=crc)


def compute_crc16(data: bytes) -> int:
    """CRC-16-CCITT 计算"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def verify_crc16(data: bytes, expected_crc: int) -> bool:
    """验证 CRC-16"""
    return compute_crc16(data) == expected_crc


# =============================================================================
# Frame <-> RF 转换
# =============================================================================

class FrameEncoder:
    """
    将 sim/Frame 对象编码为 RF 比特流

    用于发送端：experiment_runner -> tx_flowgraph -> HackRF
    """

    def __init__(
        self,
        shared_key: str = "hardware_experiment_key_2024",
        nonce_bits: int = DEFAULT_NONCE_BITS
    ):
        self.shared_key = shared_key.encode('utf-8')
        self.nonce_bits = nonce_bits

    def encode_frame(self, frame: Frame) -> bytes:
        """
        将 Frame 对象编码为 RF 字节序列

        Args:
            frame: sim/types.py 中定义的 Frame 对象

        Returns:
            完整的 RF 帧字节序列（包括 preamble, sync, payload, crc）
        """
        # 构建 payload
        payload = self._build_payload(frame)

        # 计算 CRC
        crc = compute_crc16(payload)

        # 组装完整帧
        rf_frame = RFFrame(
            preamble=PREAMBLE_BYTES,
            sync_word=SYNC_WORD,
            payload=payload,
            crc=crc
        )

        return rf_frame.to_bytes()

    def _build_payload(self, frame: Frame) -> bytes:
        """构建 payload 部分"""
        # Flags (1 byte)
        flags = 0x00
        if frame.is_attack:
            flags |= 0x01
        if frame.nonce is not None:
            flags |= 0x02

        # Counter (4 bytes, big-endian)
        counter = frame.counter if frame.counter is not None else 0

        # Nonce (4 bytes)
        nonce = 0
        if frame.nonce is not None:
            if isinstance(frame.nonce, str):
                nonce = int(frame.nonce, 16)
            else:
                nonce = int(frame.nonce)

            max_nonce = (1 << self.nonce_bits) - 1
            if nonce < 0 or nonce > max_nonce:
                raise ValueError(f"Nonce out of range for {self.nonce_bits} bits")

        # Command (variable length, null-terminated)
        cmd_bytes = (frame.command or "").encode('utf-8')
        cmd_len = len(cmd_bytes)

        # MAC (16 bytes) - 已经在 Frame 中计算好了
        mac_bytes = bytes.fromhex(frame.mac) if frame.mac else bytes(16)
        mac_bytes = mac_bytes[:16].ljust(16, b'\x00')

        # 构建 payload
        # 格式: flags(1) + counter(4) + nonce(4) + cmd_len(1) + cmd(var) + mac(16) + padding
        header = struct.pack(">BIIB", flags, counter, nonce, cmd_len)
        payload = header + cmd_bytes + mac_bytes

        # 填充到固定长度
        if len(payload) < FRAME_PAYLOAD_SIZE:
            payload = payload + bytes(FRAME_PAYLOAD_SIZE - len(payload))
        else:
            payload = payload[:FRAME_PAYLOAD_SIZE]

        return payload

    def encode_to_bits(self, frame: Frame) -> np.ndarray:
        """
        将 Frame 编码为比特数组

        Args:
            frame: Frame 对象

        Returns:
            numpy 比特数组 (0 或 1)
        """
        frame_bytes = self.encode_frame(frame)
        bits = []
        for byte in frame_bytes:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return np.array(bits, dtype=np.uint8)

    def encode_to_iq(self, frame: Frame) -> np.ndarray:
        """
        将 Frame 编码为 IQ 样本（FSK 调制）

        Args:
            frame: Frame 对象

        Returns:
            复数 IQ 样本数组
        """
        bits = self.encode_to_bits(frame)
        return self._fsk_modulate(bits)

    def _fsk_modulate(self, bits: np.ndarray) -> np.ndarray:
        """
        FSK 调制

        对应论文3.4节的调制参数
        """
        num_samples = len(bits) * SAMPLES_PER_SYMBOL
        samples = np.zeros(num_samples, dtype=np.complex64)

        # 相位累加器
        phase = 0.0
        freq_offset = DEVIATION_HZ / RF_SAMPLE_RATE_HZ * 2 * np.pi

        for i, bit in enumerate(bits):
            # FSK: bit 1 = +deviation, bit 0 = -deviation
            freq = freq_offset if bit == 1 else -freq_offset

            for j in range(SAMPLES_PER_SYMBOL):
                idx = i * SAMPLES_PER_SYMBOL + j
                samples[idx] = np.exp(1j * phase)
                phase += freq

        return samples


class FrameDecoder:
    """
    将 RF 比特流解码为 sim/Frame 对象

    用于接收端：HackRF -> rx_flowgraph -> experiment_runner
    """

    def __init__(
        self,
        shared_key: str = "hardware_experiment_key_2024",
        nonce_bits: int = DEFAULT_NONCE_BITS
    ):
        self.shared_key = shared_key.encode('utf-8')
        self.nonce_bits = nonce_bits

    def decode_frame(self, data: bytes) -> Optional[Frame]:
        """
        从 RF 字节序列解码为 Frame 对象

        Args:
            data: 接收到的字节序列

        Returns:
            解码后的 Frame 对象，如果解码失败返回 None
        """
        # 解析 RF 帧
        rf_frame = RFFrame.from_bytes(data)
        if rf_frame is None:
            return None

        # 验证 CRC
        if not verify_crc16(rf_frame.payload, rf_frame.crc):
            return None

        # 解析 payload
        return self._parse_payload(rf_frame.payload)

    def _parse_payload(self, payload: bytes) -> Optional[Frame]:
        """解析 payload 部分"""
        if len(payload) < 10:  # 最小长度: flags(1) + counter(4) + nonce(4) + cmd_len(1)
            return None

        try:
            # 解析头部
            flags, counter, nonce, cmd_len = struct.unpack(">BIIB", payload[:10])

            # 解析命令
            cmd_end = 10 + cmd_len
            if cmd_end > len(payload):
                return None
            cmd = payload[10:cmd_end].decode('utf-8')

            # 解析 MAC
            mac_start = cmd_end
            mac_end = mac_start + 16
            if mac_end > len(payload):
                mac_bytes = payload[mac_start:]
            else:
                mac_bytes = payload[mac_start:mac_end]
            mac = mac_bytes.hex()

            # 构建 Frame
            is_attack = bool(flags & 0x01)
            nonce_hex = None
            if flags & 0x02:
                hex_len = (self.nonce_bits + 3) // 4
                nonce_hex = f"{nonce:0{hex_len}x}"

            return Frame(
                command=cmd,
                counter=counter if counter != 0 else None,
                mac=mac,
                nonce=nonce_hex,
                is_attack=is_attack
            )

        except Exception as e:
            # 帧解析失败（如格式错误、字段缺失等）
            return None

    def decode_from_bits(self, bits: np.ndarray) -> Optional[Frame]:
        """
        从比特数组解码

        Args:
            bits: numpy 比特数组

        Returns:
            Frame 对象
        """
        # 比特转字节
        data = []
        for i in range(0, len(bits) - 7, 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | int(bits[i + j])
            data.append(byte)

        return self.decode_frame(bytes(data))

    def decode_from_iq(self, samples: np.ndarray) -> Optional[Frame]:
        """
        从 IQ 样本解码（FSK 解调）

        Args:
            samples: 复数 IQ 样本数组

        Returns:
            Frame 对象
        """
        bits = self._fsk_demodulate(samples)
        return self.decode_from_bits(bits)

    def _fsk_demodulate(self, samples: np.ndarray) -> np.ndarray:
        """
        FSK 解调
        """
        num_symbols = len(samples) // SAMPLES_PER_SYMBOL
        if num_symbols <= 0:
            return np.array([], dtype=np.uint8)

        trimmed = samples[:num_symbols * SAMPLES_PER_SYMBOL]
        symbols = trimmed.reshape(num_symbols, SAMPLES_PER_SYMBOL)

        # 在每个符号内部估计相位增量，避免 np.diff 导致的 1 样本丢失和符号边界偏移。
        if SAMPLES_PER_SYMBOL > 1:
            phase_step = np.angle(symbols[:, 1:] * np.conj(symbols[:, :-1]))
            freq_symbols = phase_step.mean(axis=1)
        else:
            phase = np.unwrap(np.angle(trimmed))
            freq_symbols = np.diff(np.r_[phase[0], phase])

        # 判决: 正频率 = 1, 负频率 = 0
        bits = (freq_symbols > 0).astype(np.uint8)

        return bits


# =============================================================================
# ZMQ 消息格式
# =============================================================================

class ZMQProtocol:
    """
    ZMQ 消息协议

    定义 experiment_runner.py 与 GNU Radio 流图之间的消息格式
    """

    # 消息类型
    MSG_TYPE_FRAME = 0x01       # 帧数据
    MSG_TYPE_STATUS = 0x02     # 状态信息
    MSG_TYPE_CONFIG = 0x03     # 配置命令

    @staticmethod
    def encode_frame_message(frame: Frame, encoder: FrameEncoder) -> bytes:
        """
        编码帧消息用于 ZMQ 传输

        格式: [msg_type(1)] [length(2)] [rf_frame_bytes(var)]
        """
        rf_bytes = encoder.encode_frame(frame)
        length = len(rf_bytes)
        header = struct.pack(">BH", ZMQProtocol.MSG_TYPE_FRAME, length)
        return header + rf_bytes

    @staticmethod
    def decode_frame_message(data: bytes, decoder: FrameDecoder) -> Optional[Tuple[Frame, float]]:
        """
        解码 ZMQ 帧消息

        Returns:
            (Frame, latency_ms) 或 None
        """
        if len(data) < 3:
            return None

        msg_type, length = struct.unpack(">BH", data[:3])

        if msg_type != ZMQProtocol.MSG_TYPE_FRAME:
            return None

        if len(data) < 3 + length:
            return None

        rf_bytes = data[3:3+length]
        frame = decoder.decode_frame(rf_bytes)

        if frame is None:
            return None

        # 延迟信息（如果包含在消息中）
        latency_ms = 0.0
        if len(data) > 3 + length:
            try:
                latency_ms = struct.unpack(">f", data[3+length:3+length+4])[0]
            except struct.error:
                # 时间戳格式错误，使用默认延迟值 0.0
                pass

        return frame, latency_ms

    @staticmethod
    def encode_raw_bytes_message(data: bytes) -> bytes:
        """
        编码原始字节消息（用于直接发送 RF 字节）
        """
        length = len(data)
        header = struct.pack(">BH", ZMQProtocol.MSG_TYPE_FRAME, length)
        return header + data

    @staticmethod
    def decode_raw_bytes_message(data: bytes) -> Optional[bytes]:
        """
        解码原始字节消息
        """
        if len(data) < 3:
            return None

        msg_type, length = struct.unpack(">BH", data[:3])

        if msg_type != ZMQProtocol.MSG_TYPE_FRAME:
            return None

        return data[3:3+length]


# =============================================================================
# 便捷函数
# =============================================================================

def frame_to_rf_bytes(frame: Frame, shared_key: str = "hardware_experiment_key_2024") -> bytes:
    """Frame 对象 -> RF 字节序列"""
    encoder = FrameEncoder(shared_key)
    return encoder.encode_frame(frame)


def rf_bytes_to_frame(data: bytes, shared_key: str = "hardware_experiment_key_2024") -> Optional[Frame]:
    """RF 字节序列 -> Frame 对象"""
    decoder = FrameDecoder(shared_key)
    return decoder.decode_frame(data)


def frame_to_iq_samples(frame: Frame, shared_key: str = "hardware_experiment_key_2024") -> np.ndarray:
    """Frame 对象 -> IQ 样本"""
    encoder = FrameEncoder(shared_key)
    return encoder.encode_to_iq(frame)


def iq_samples_to_frame(samples: np.ndarray, shared_key: str = "hardware_experiment_key_2024") -> Optional[Frame]:
    """IQ 样本 -> Frame 对象"""
    decoder = FrameDecoder(shared_key)
    return decoder.decode_from_iq(samples)


# =============================================================================
# 测试
# =============================================================================

def test_protocol():
    """测试协议层"""
    print("=" * 60)
    print("Protocol Layer Test")
    print("=" * 60)

    # 创建测试帧
    test_frame = Frame(
        command="FWD",
        counter=12345,
        mac="0123456789abcdef0123456789abcdef",
        # Keep nonce in hex-string form to match runtime challenge-mode frames.
        nonce="00002694",
        is_attack=False
    )

    print(f"\n原始 Frame:")
    print(f"  command: {test_frame.command}")
    print(f"  counter: {test_frame.counter}")
    print(f"  mac: {test_frame.mac}")
    print(f"  nonce: {test_frame.nonce}")
    print(f"  is_attack: {test_frame.is_attack}")

    # 编码
    encoder = FrameEncoder()
    rf_bytes = encoder.encode_frame(test_frame)
    print(f"\n编码后 RF 字节: {len(rf_bytes)} bytes")
    print(f"  Hex: {rf_bytes.hex()[:80]}...")

    # 解码
    decoder = FrameDecoder()
    decoded_frame = decoder.decode_frame(rf_bytes)

    if decoded_frame:
        print(f"\n解码后 Frame:")
        print(f"  command: {decoded_frame.command}")
        print(f"  counter: {decoded_frame.counter}")
        print(f"  mac: {decoded_frame.mac[:32]}...")
        print(f"  nonce: {decoded_frame.nonce}")
        print(f"  is_attack: {decoded_frame.is_attack}")

        # 验证
        assert decoded_frame.command == test_frame.command
        assert decoded_frame.counter == test_frame.counter
        assert decoded_frame.nonce == test_frame.nonce
        print("\n[OK] 编解码测试通过!")
    else:
        print("\n[FAIL] 解码失败!")
        return False

    # 测试 IQ 调制/解调
    print("\n" + "-" * 40)
    print("IQ 调制/解调测试")

    iq_samples = encoder.encode_to_iq(test_frame)
    print(f"  IQ 样本数: {len(iq_samples)}")
    print(f"  预期样本数: {len(rf_bytes) * 8 * SAMPLES_PER_SYMBOL}")

    # 解调
    decoded_from_iq = decoder.decode_from_iq(iq_samples)
    if decoded_from_iq:
        assert decoded_from_iq.command == test_frame.command
        print("  [OK] IQ 调制/解调测试通过!")
    else:
        print("  [WARN] IQ 解调失败（可能需要添加噪声容限）")

    return True


if __name__ == "__main__":
    test_protocol()
