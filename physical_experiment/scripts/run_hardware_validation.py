#!/usr/bin/env python3
"""
一键硬件验证编排器 - Hardware Validation Orchestrator

一键启动 TX/RX flowgraph + 实验运行器，自动化硬件验证流程。

功能:
  1. Preflight 检查：设备、端口、衰减器参数
  2. 自动启动 tx_flowgraph.py 和 rx_flowgraph.py 子进程
  3. 等待就绪后运行验证实验
  4. 自动清理子进程

安全特性:
  - 强制要求 --attenuation-db 参数（同轴直连模式）
  - 估算 RX 输入功率并拒绝不安全配置
  - 默认使用最低 TX 增益

用法:
    # 列出可用设备
    python run_hardware_validation.py --list-devices

    # 指定设备和衰减（最小 40 dB）
    python run_hardware_validation.py --tx-serial XXX --rx-serial YYY --attenuation-db 50

    # 跳过安全检查（仅供专家使用）
    python run_hardware_validation.py --tx-serial XXX --rx-serial YYY --attenuation-db 30 --i-know-what-im-doing

    # 快速测试
    python run_hardware_validation.py --tx-serial XXX --rx-serial YYY --attenuation-db 50 --quick
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from physical_experiment.runtime import (
    load_experiment_config,
    resolve_config_path,
    resolve_output_path,
)

from physical_experiment.scripts.doctor import (
    get_hackrf_devices,
    check_dual_hackrf_available,
    EnvironmentDoctor,
    Status
)

# =============================================================================
# 安全常量 (基于 HackRF 官方文档)
# =============================================================================

# HackRF RX 最大输入功率: -5 dBm (超过可能永久损坏)
# https://hackrf.readthedocs.io/en/latest/hackrf_one.html
RX_MAX_INPUT_DBM = -5

# HackRF TX 在 2170-2740 MHz 典型功率: 13-15 dBm
TX_MAX_POWER_DBM = 15

# 建议的最小衰减 (工程裕量)
MIN_RECOMMENDED_ATTENUATION_DB = 40

# 默认 TX 增益 (最低值，安全起见)
DEFAULT_TX_GAIN_DB = 10

# ZMQ 端口
DEFAULT_TX_PORT = 5555
DEFAULT_RX_PORT = 5556


@dataclass
class SafetyCheckResult:
    """安全检查结果"""
    safe: bool
    estimated_rx_dbm: float
    message: str
    warning: Optional[str] = None


def estimate_rx_power(
    tx_power_dbm: float,
    attenuation_db: float,
    cable_loss_db: float = 1.0
) -> SafetyCheckResult:
    """
    估算 RX 输入功率

    Args:
        tx_power_dbm: TX 输出功率 (dBm)
        attenuation_db: 衰减器衰减量 (dB)
        cable_loss_db: 同轴线损耗 (dB), 默认 1 dB

    Returns:
        SafetyCheckResult
    """
    estimated_rx = tx_power_dbm - attenuation_db - cable_loss_db

    if estimated_rx > RX_MAX_INPUT_DBM:
        return SafetyCheckResult(
            safe=False,
            estimated_rx_dbm=estimated_rx,
            message=(
                f"危险！预估 RX 输入功率 {estimated_rx:.1f} dBm 超过 HackRF 最大允许值 "
                f"{RX_MAX_INPUT_DBM} dBm。\n"
                f"这可能永久损坏 RX 设备！\n\n"
                f"计算: TX {tx_power_dbm} dBm - 衰减 {attenuation_db} dB - 线损 {cable_loss_db} dB "
                f"= {estimated_rx:.1f} dBm\n\n"
                f"解决方案: 增加衰减器 (建议至少 {MIN_RECOMMENDED_ATTENUATION_DB} dB)"
            )
        )

    if estimated_rx > -10:  # 留 5 dB 裕量
        return SafetyCheckResult(
            safe=True,
            estimated_rx_dbm=estimated_rx,
            message=f"预估 RX 输入功率: {estimated_rx:.1f} dBm",
            warning=(
                f"警告: 预估 RX 输入功率 {estimated_rx:.1f} dBm 接近安全边界 "
                f"({RX_MAX_INPUT_DBM} dBm)。\n"
                f"建议增加衰减以留出裕量。"
            )
        )

    return SafetyCheckResult(
        safe=True,
        estimated_rx_dbm=estimated_rx,
        message=f"预估 RX 输入功率: {estimated_rx:.1f} dBm (安全)"
    )


def check_port_available(port: int) -> Tuple[bool, str]:
    """检查端口是否可用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.close()
        return True, f"端口 {port} 可用"
    except OSError as e:
        return False, f"端口 {port} 被占用: {e}"


def list_devices() -> None:
    """列出所有可用的 HackRF 设备"""
    print("\n" + "=" * 60)
    print("HackRF 设备检测")
    print("=" * 60 + "\n")

    devices = get_hackrf_devices()

    if not devices:
        print("未检测到 HackRF 设备。")
        print("\n排查步骤:")
        print("  1. 检查 USB 连接")
        print("  2. 运行: hackrf_info")
        print("  3. 如果权限错误: sudo usermod -aG plugdev $USER && 重新登录")
        return

    print(f"检测到 {len(devices)} 台设备:\n")
    for i, dev in enumerate(devices, 1):
        print(f"  设备 {i}:")
        print(f"    序列号:     {dev['serial']}")
        print(f"    固件版本:   {dev['firmware']}")
        if dev.get('part_id'):
            print(f"    Part ID:    {dev['part_id']}")
        print()

    if len(devices) >= 2:
        print("提示: 可以使用以下命令启动硬件验证:")
        print(f"  python run_hardware_validation.py \\")
        print(f"    --tx-serial {devices[0]['serial']} \\")
        print(f"    --rx-serial {devices[1]['serial']} \\")
        print(f"    --attenuation-db 50")
    else:
        print("注意: 硬件验证需要 2 台 HackRF (TX + RX)。")
        print("      当前仅有 1 台设备，建议使用 --loopback 模式。")


class HardwareOrchestrator:
    """硬件验证编排器"""

    def __init__(
        self,
        config: dict,
        config_path: Path,
        tx_serial: str,
        rx_serial: str,
        attenuation_db: float,
        tx_gain_db: int = DEFAULT_TX_GAIN_DB,
        tx_port: int = DEFAULT_TX_PORT,
        rx_port: int = DEFAULT_RX_PORT,
        skip_safety_check: bool = False
    ):
        self.config = config
        self.config_path = Path(config_path)
        self.tx_serial = tx_serial
        self.rx_serial = rx_serial
        self.attenuation_db = attenuation_db
        self.tx_gain_db = tx_gain_db
        self.tx_port = tx_port
        self.rx_port = rx_port
        self.skip_safety_check = skip_safety_check

        self.tx_process: Optional[subprocess.Popen] = None
        self.rx_process: Optional[subprocess.Popen] = None
        self.tx_log_handle = None
        self.rx_log_handle = None
        self.tx_log_path: Optional[Path] = None
        self.rx_log_path: Optional[Path] = None
        self.startup_timeout = self.config.get("flowgraph", {}).get("startup_timeout_s", 10)
        self.logs_dir = resolve_output_path(self.config, "logs_dir", "physical_experiment/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def preflight_check(self) -> bool:
        """执行 preflight 检查"""
        print("\n" + "=" * 60)
        print("Preflight 检查")
        print("=" * 60 + "\n")

        all_ok = True

        # 1. 检查设备
        print("[1/4] 检查 HackRF 设备...")
        devices = get_hackrf_devices()
        device_serials = [d["serial"] for d in devices]

        if self.tx_serial not in device_serials:
            print(f"  ❌ TX 设备 {self.tx_serial} 未找到")
            print(f"     可用设备: {device_serials}")
            all_ok = False
        else:
            print(f"  ✓ TX 设备 {self.tx_serial}")

        if self.rx_serial not in device_serials:
            print(f"  ❌ RX 设备 {self.rx_serial} 未找到")
            print(f"     可用设备: {device_serials}")
            all_ok = False
        else:
            print(f"  ✓ RX 设备 {self.rx_serial}")

        if self.tx_serial == self.rx_serial:
            print(f"  ❌ TX 和 RX 不能使用同一台设备")
            all_ok = False

        # 2. 检查端口
        print("\n[2/4] 检查 ZMQ 端口...")
        tx_ok, tx_msg = check_port_available(self.tx_port)
        rx_ok, rx_msg = check_port_available(self.rx_port)

        if tx_ok:
            print(f"  ✓ {tx_msg}")
        else:
            print(f"  ❌ {tx_msg}")
            all_ok = False

        if rx_ok:
            print(f"  ✓ {rx_msg}")
        else:
            print(f"  ❌ {rx_msg}")
            all_ok = False

        # 3. 安全检查
        print("\n[3/4] 安全检查...")
        safety = estimate_rx_power(TX_MAX_POWER_DBM, self.attenuation_db)

        if not safety.safe:
            print(f"  ❌ {safety.message}")
            if not self.skip_safety_check:
                all_ok = False
            else:
                print("  ⚠️  --i-know-what-im-doing 已启用，跳过安全检查")
        else:
            print(f"  ✓ {safety.message}")
            if safety.warning:
                print(f"  ⚠️  {safety.warning}")

        print(f"\n  配置:")
        print(f"    TX 增益: {self.tx_gain_db} dB")
        print(f"    衰减器: {self.attenuation_db} dB")
        print(f"    预估 RX 输入: {safety.estimated_rx_dbm:.1f} dBm")

        # 4. 环境检查
        print("\n[4/4] 环境检查...")
        doctor = EnvironmentDoctor()
        doctor.check_gnuradio()
        doctor.check_gr_osmosdr()

        for check in doctor.report.checks:
            if check.status == Status.OK:
                print(f"  ✓ {check.name}: {check.message}")
            elif check.status == Status.WARNING:
                print(f"  ⚠️  {check.name}: {check.message}")
            else:
                print(f"  ❌ {check.name}: {check.message}")
                all_ok = False

        print()
        if all_ok:
            print("✓ 所有 preflight 检查通过")
        else:
            print("❌ Preflight 检查失败，请修复上述问题")

        return all_ok

    def start_flowgraphs(self) -> bool:
        """启动 TX 和 RX flowgraphs"""
        print("\n" + "=" * 60)
        print("启动 Flowgraphs")
        print("=" * 60 + "\n")

        flowgraph_dir = PROJECT_ROOT / "physical_experiment" / "flowgraphs"
        tx_script = flowgraph_dir / "tx_flowgraph.py"
        rx_script = flowgraph_dir / "rx_flowgraph.py"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.rx_log_path = self.logs_dir / f"rx_flowgraph_{timestamp}.log"
        self.tx_log_path = self.logs_dir / f"tx_flowgraph_{timestamp}.log"
        self.rx_log_handle = open(self.rx_log_path, "w", encoding="utf-8", buffering=1)
        self.tx_log_handle = open(self.tx_log_path, "w", encoding="utf-8", buffering=1)

        # 启动 RX (先启动接收端)
        print(f"启动 RX flowgraph (serial: {self.rx_serial})...")
        self.rx_process = subprocess.Popen(
            [
                sys.executable, str(rx_script),
                "--config", str(self.config_path),
                "--hackrf-serial", self.rx_serial,
                "--zmq-port", str(self.rx_port)
            ],
            stdout=self.rx_log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True
        )

        # 等待 RX 初始化
        if not self._wait_for_process(self.rx_process, self.startup_timeout):
            print(f"  ❌ RX flowgraph 启动失败:")
            print(f"  详情请查看: {self.rx_log_path}")
            return False
        print("  ✓ RX flowgraph 已启动")
        print(f"    日志: {self.rx_log_path}")

        # 启动 TX
        print(f"启动 TX flowgraph (serial: {self.tx_serial})...")
        self.tx_process = subprocess.Popen(
            [
                sys.executable, str(tx_script),
                "--config", str(self.config_path),
                "--hackrf-serial", self.tx_serial,
                "--zmq-port", str(self.tx_port),
                "--tx-gain", str(self.tx_gain_db)
            ],
            stdout=self.tx_log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True
        )

        # 等待 TX 初始化
        if not self._wait_for_process(self.tx_process, self.startup_timeout):
            print(f"  ❌ TX flowgraph 启动失败:")
            print(f"  详情请查看: {self.tx_log_path}")
            self.cleanup()
            return False
        print("  ✓ TX flowgraph 已启动")
        print(f"    日志: {self.tx_log_path}")

        print("\n等待 flowgraphs 稳定...")
        time.sleep(3)

        return True

    def _wait_for_process(self, proc: subprocess.Popen, timeout_s: float) -> bool:
        """Wait until a flowgraph stays alive for the configured startup window."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return False
            time.sleep(0.2)
        return proc.poll() is None

    def run_link_selftest(self, selftest_frames: int = 200) -> bool:
        """运行链路自检，确保 FSK 物理链路闭环可用。"""
        print("\n" + "=" * 60)
        print("运行链路自检 (FSK/A2)")
        print("=" * 60 + "\n")

        validation_script = PROJECT_ROOT / "physical_experiment" / "scripts" / "run_validation.py"
        cmd = [
            sys.executable, str(validation_script),
            "--config", str(self.config_path),
            "--link-selftest",
            "--selftest-frames", str(selftest_frames),
            "--tx-port", str(self.tx_port),
            "--rx-port", str(self.rx_port),
        ]

        print(f"命令: {' '.join(cmd)}")
        print()
        result = subprocess.run(cmd)
        return result.returncode == 0

    def run_validation(self, quick: bool = False, loss_samples: str = "0", goal_check: bool = True) -> int:
        """运行验证实验"""
        print("\n" + "=" * 60)
        print("运行验证实验")
        print("=" * 60 + "\n")

        validation_script = PROJECT_ROOT / "physical_experiment" / "scripts" / "run_validation.py"

        cmd = [
            sys.executable, str(validation_script),
            "--config", str(self.config_path),
            "--loss-samples", loss_samples,
            "--tx-port", str(self.tx_port),
            "--rx-port", str(self.rx_port),
        ]

        if quick:
            cmd.append("--quick")
        if goal_check:
            cmd.append("--goal-check")

        print(f"命令: {' '.join(cmd)}")
        print()

        result = subprocess.run(cmd)
        return result.returncode

    def cleanup(self):
        """清理子进程"""
        print("\n清理 flowgraphs...")

        if self.tx_process and self.tx_process.poll() is None:
            try:
                os.killpg(self.tx_process.pid, signal.SIGTERM)
            except Exception:
                self.tx_process.terminate()
            try:
                self.tx_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.tx_process.pid, signal.SIGKILL)
                except Exception:
                    self.tx_process.kill()
            print("  TX flowgraph 已停止")

        if self.rx_process and self.rx_process.poll() is None:
            try:
                os.killpg(self.rx_process.pid, signal.SIGTERM)
            except Exception:
                self.rx_process.terminate()
            try:
                self.rx_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.rx_process.pid, signal.SIGKILL)
                except Exception:
                    self.rx_process.kill()
            print("  RX flowgraph 已停止")

        if self.tx_log_handle:
            self.tx_log_handle.close()
            self.tx_log_handle = None
        if self.rx_log_handle:
            self.rx_log_handle.close()
            self.rx_log_handle = None


def main():
    parser = argparse.ArgumentParser(
        description="一键硬件验证编排器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
安全说明:
  HackRF RX 最大输入功率为 -5 dBm，超过可能永久损坏设备。
  同轴直连时必须使用衰减器（建议 ≥40 dB）。

示例:
  # 列出可用设备
  python run_hardware_validation.py --list-devices

  # 运行硬件验证
  python run_hardware_validation.py --tx-serial XXX --rx-serial YYY --attenuation-db 50

  # 快速测试
  python run_hardware_validation.py --tx-serial XXX --rx-serial YYY --attenuation-db 50 --quick

  # 带受控丢包采样
  python run_hardware_validation.py --tx-serial XXX --rx-serial YYY --attenuation-db 50 --loss-samples 0,0.1,0.2
"""
    )

    # 设备参数
    parser.add_argument("--list-devices", action="store_true",
                        help="列出可用的 HackRF 设备")
    parser.add_argument("--config", type=str, default=None,
                        help="配置文件路径")
    parser.add_argument("--tx-serial", type=str,
                        help="TX HackRF 设备序列号")
    parser.add_argument("--rx-serial", type=str,
                        help="RX HackRF 设备序列号")

    # 安全参数
    parser.add_argument("--attenuation-db", type=float,
                        help="同轴直连衰减器总衰减量 (dB) - 必填")
    parser.add_argument("--tx-gain", type=int, default=DEFAULT_TX_GAIN_DB,
                        help=f"TX 增益 (dB), 默认 {DEFAULT_TX_GAIN_DB} (最低)")
    parser.add_argument("--i-know-what-im-doing", action="store_true",
                        help="跳过安全检查 (危险!)")

    # 实验参数
    parser.add_argument("--quick", action="store_true",
                        help="快速测试模式")
    parser.add_argument("--loss-samples", type=str, default="0",
                        help="受控丢包采样点 (逗号分隔)")
    parser.add_argument("--skip-selftest", action="store_true",
                        help="跳过链路自检（不推荐）")
    parser.add_argument("--selftest-frames", type=int, default=200,
                        help="链路自检帧数 (默认 200)")
    parser.add_argument("--skip-goal-check", action="store_true",
                        help="跳过三目标验收门槛（不推荐）")

    # 端口参数
    parser.add_argument("--tx-port", type=int, default=DEFAULT_TX_PORT,
                        help=f"TX ZMQ 端口 (默认 {DEFAULT_TX_PORT})")
    parser.add_argument("--rx-port", type=int, default=DEFAULT_RX_PORT,
                        help=f"RX ZMQ 端口 (默认 {DEFAULT_RX_PORT})")

    args = parser.parse_args()

    # 列出设备
    if args.list_devices:
        list_devices()
        return

    try:
        config_path = resolve_config_path(args.config)
        config = load_experiment_config(config_path)
    except FileNotFoundError as exc:
        print(f"错误: {exc}")
        sys.exit(1)

    # 验证必填参数
    if not args.tx_serial or not args.rx_serial:
        print("错误: 必须指定 --tx-serial 和 --rx-serial")
        print("使用 --list-devices 查看可用设备")
        sys.exit(1)

    if args.attenuation_db is None:
        print("错误: 必须指定 --attenuation-db")
        print("")
        print("安全说明:")
        print("  同轴直连时必须使用衰减器以保护 RX 设备。")
        print("  HackRF RX 最大输入功率: -5 dBm")
        print("  HackRF TX 最大功率 (2.4 GHz): ~15 dBm")
        print("  建议衰减: ≥40 dB")
        print("")
        print("示例: --attenuation-db 50")
        sys.exit(1)

    # 创建编排器
    orchestrator = HardwareOrchestrator(
        config=config,
        config_path=config_path,
        tx_serial=args.tx_serial,
        rx_serial=args.rx_serial,
        attenuation_db=args.attenuation_db,
        tx_gain_db=args.tx_gain,
        tx_port=args.tx_port,
        rx_port=args.rx_port,
        skip_safety_check=args.i_know_what_im_doing
    )

    # 注册信号处理器
    def signal_handler(sig, frame):
        print("\n收到中断信号，正在清理...")
        orchestrator.cleanup()
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Preflight 检查
        if not orchestrator.preflight_check():
            sys.exit(1)

        # 启动 flowgraphs
        if not orchestrator.start_flowgraphs():
            sys.exit(1)

        # 链路自检 (A2)
        if not args.skip_selftest:
            if not orchestrator.run_link_selftest(selftest_frames=args.selftest_frames):
                print("\n❌ 链路自检失败，终止后续验证。")
                sys.exit(2)

        # 运行验证
        exit_code = orchestrator.run_validation(
            quick=args.quick,
            loss_samples=args.loss_samples,
            goal_check=not args.skip_goal_check
        )

    finally:
        orchestrator.cleanup()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
