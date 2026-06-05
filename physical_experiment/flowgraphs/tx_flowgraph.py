#!/usr/bin/env python3
"""
GNU Radio TX Flowgraph - 帧发送器

对应论文参数:
- 频率: 2.475 GHz (论文3.3节)
- 采样率: 2 Msps
- 调制: 2値FSK
- 频偏: ~101.5 kHz (论文3.4节)
- Samples/Symbol: 2

架构:
    [ZMQ PULL] --> [协议解码] --> [FSK调制] --> [HackRF Sink]
         ^
         |
    Python Script (experiment_runner.py)

ZMQ 消息格式:
    [msg_type(1)] [length(2)] [rf_frame_bytes(var)]
"""
from __future__ import annotations

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
DEFAULT_TX_GAIN_DB = 20
DEFAULT_IF_GAIN_DB = 30
DEFAULT_ZMQ_TX_PORT = 5555


def load_config(config_path: Optional[str] = None) -> dict:
    """从配置文件加载参数"""
    return load_experiment_config(config_path)


class FrameToIQ(gr.sync_block):
    """
    自定义 GNU Radio 块：将接收到的帧字节转换为 FSK IQ 样本

    输入: 帧字节流 (uint8)
    输出: 复数 IQ 样本 (complex64)
    """

    def __init__(
        self,
        samples_per_symbol: int = DEFAULT_SAMPLES_PER_SYMBOL,
        deviation_hz: float = DEFAULT_DEVIATION_HZ,
        sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ
    ):
        gr.sync_block.__init__(
            self,
            name="Frame to IQ (FSK)",
            in_sig=[np.uint8],
            out_sig=[np.complex64]
        )

        self.samples_per_symbol = samples_per_symbol
        self.deviation_hz = deviation_hz
        self.sample_rate_hz = sample_rate_hz

        # FSK 调制参数
        self.freq_offset = deviation_hz / sample_rate_hz * 2 * np.pi
        self.phase = 0.0

        # 设置输出比例（每个输入字节产生 8 * samples_per_symbol 个样本）
        self.set_output_multiple(8 * samples_per_symbol)

    def work(self, input_items, output_items):
        in_data = input_items[0]
        out_data = output_items[0]

        # 字节转比特
        bits = []
        for byte in in_data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)

        # FSK 调制
        out_idx = 0
        for bit in bits:
            freq = self.freq_offset if bit == 1 else -self.freq_offset

            for _ in range(self.samples_per_symbol):
                if out_idx < len(out_data):
                    out_data[out_idx] = np.exp(1j * self.phase)
                    self.phase += freq
                    out_idx += 1

        return out_idx


class ZMQFrameSource(gr.sync_block):
    """
    ZMQ 帧源块

    从 ZMQ 接收帧数据，解析协议头，输出原始帧字节
    """

    def __init__(
        self,
        zmq_port: int = DEFAULT_ZMQ_TX_PORT,
        bind_host: str = "127.0.0.1",
    ):
        gr.sync_block.__init__(
            self,
            name="ZMQ Frame Source",
            in_sig=None,
            out_sig=[np.uint8]
        )

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PULL)
        self.socket.bind(f"tcp://{bind_host}:{zmq_port}")
        self.socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout

        self.pending_bytes = b""
        print(f"[ZMQFrameSource] Listening on tcp://{bind_host}:{zmq_port}")

    def work(self, input_items, output_items):
        out_data = output_items[0]

        # 如果有待处理的字节
        if self.pending_bytes:
            n = min(len(self.pending_bytes), len(out_data))
            out_data[:n] = np.frombuffer(self.pending_bytes[:n], dtype=np.uint8)
            self.pending_bytes = self.pending_bytes[n:]
            return n

        # 尝试接收新消息
        try:
            msg = self.socket.recv(zmq.NOBLOCK)

            # 解析协议头
            if len(msg) >= 3:
                msg_type, length = struct.unpack(">BH", msg[:3])

                if msg_type == 0x01:  # MSG_TYPE_FRAME
                    rf_bytes = msg[3:3+length]
                    self.pending_bytes = rf_bytes

                    n = min(len(self.pending_bytes), len(out_data))
                    out_data[:n] = np.frombuffer(self.pending_bytes[:n], dtype=np.uint8)
                    self.pending_bytes = self.pending_bytes[n:]
                    return n

        except Exception:
            pass

        return 0

    def stop(self):
        self.socket.close()
        self.context.term()
        return True


class TxFlowgraph(gr.top_block):
    """
    发送端流图

    架构:
        [ZMQ Frame Source] --> [Frame to IQ] --> [HackRF Sink]
    """

    def __init__(
        self,
        frequency: float = DEFAULT_FREQUENCY_HZ,
        sample_rate: float = DEFAULT_SAMPLE_RATE_HZ,
        deviation: float = DEFAULT_DEVIATION_HZ,
        samples_per_symbol: int = DEFAULT_SAMPLES_PER_SYMBOL,
        tx_gain: int = DEFAULT_TX_GAIN_DB,
        if_gain: int = DEFAULT_IF_GAIN_DB,
        zmq_port: int = DEFAULT_ZMQ_TX_PORT,
        device_args: str = ""
    ):
        gr.top_block.__init__(self, "IoT Replay Defense TX (论文参数)")

        ##################################################
        # 变量
        ##################################################
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.deviation = deviation
        self.samples_per_symbol = samples_per_symbol
        self.tx_gain = tx_gain
        self.if_gain = if_gain

        ##################################################
        # Blocks
        ##################################################

        # 方法1: 使用自定义块（更灵活但可能有性能问题）
        # self.zmq_source = ZMQFrameSource(zmq_port)
        # self.frame_to_iq = FrameToIQ(samples_per_symbol, deviation, sample_rate)

        # 方法2: 使用标准 GNU Radio 块
        # ZMQ PULL Source - 接收原始 IQ 样本
        self.zmq_pull_source = blocks.zeromq_pull_source(
            gr.sizeof_gr_complex, 1,
            f"tcp://127.0.0.1:{zmq_port}",
            100,   # timeout ms
            True,  # pass_tags
            -1     # hwm
        )

        # HackRF Sink
        hackrf_args = f"numchan=1 {device_args}".strip()
        self.hackrf_sink = osmosdr.sink(args=hackrf_args)
        self.hackrf_sink.set_sample_rate(sample_rate)
        self.hackrf_sink.set_center_freq(frequency, 0)
        self.hackrf_sink.set_freq_corr(0, 0)
        self.hackrf_sink.set_gain(tx_gain, 0)
        self.hackrf_sink.set_if_gain(if_gain, 0)
        self.hackrf_sink.set_bb_gain(20, 0)
        self.hackrf_sink.set_antenna("", 0)
        self.hackrf_sink.set_bandwidth(0, 0)

        ##################################################
        # Connections
        ##################################################

        # 方法2: 直接连接 ZMQ -> HackRF（发送端在 Python 中做 FSK 调制）
        self.connect(self.zmq_pull_source, self.hackrf_sink)

        print(f"TX Flowgraph initialized (论文参数):")
        print(f"  频率: {frequency/1e9:.4f} GHz")
        print(f"  采样率: {sample_rate/1e6:.1f} Msps")
        print(f"  频偏: {deviation/1e3:.1f} kHz")
        print(f"  Samples/Symbol: {samples_per_symbol}")
        print(f"  TX Gain: {tx_gain} dB")
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
    tx_config = hw_config.get("tx", {})

    parser = argparse.ArgumentParser(
        description="TX Flowgraph - 帧发送器 (论文参数)",
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
    parser.add_argument("--tx-gain", type=int,
                        default=tx_config.get("gain_db", DEFAULT_TX_GAIN_DB),
                        help="TX 增益 (dB)")
    parser.add_argument("--if-gain", type=int,
                        default=tx_config.get("if_gain_db", DEFAULT_IF_GAIN_DB),
                        help="IF 增益 (dB)")
    parser.add_argument("--zmq-port", type=int,
                        default=zmq_config.get("tx_port", DEFAULT_ZMQ_TX_PORT),
                        help="ZMQ 端口")
    parser.add_argument("--device", type=str,
                        default=tx_config.get("device_args", ""),
                        help="HackRF 设备参数 (完整的 device_args 字符串)")
    parser.add_argument("--hackrf-serial", type=str,
                        default="",
                        help="HackRF 设备序列号 (用于指定特定设备，如有多台)")

    args = parser.parse_args()

    # 构建 device_args
    device_args = resolve_hackrf_device_args(
        config,
        "tx",
        device_args_override=args.device,
        serial_override=args.hackrf_serial,
    )
    if device_args:
        print(f"使用设备参数: {device_args}")

    tb = TxFlowgraph(
        frequency=args.freq,
        sample_rate=args.rate,
        deviation=args.deviation,
        samples_per_symbol=args.sps,
        tx_gain=args.tx_gain,
        if_gain=args.if_gain,
        zmq_port=args.zmq_port,
        device_args=device_args
    )

    print("\n启动 TX 流图... 按 Ctrl+C 停止")
    tb.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    tb.stop()
    tb.wait()
    print("TX 流图已停止")


if __name__ == "__main__":
    main()
