#!/usr/bin/env python3
"""
Environment Doctor - 环境自检脚本

一键检查物理实验所需的所有环境依赖，输出红/黄/绿状态报告。

Usage:
    python physical_experiment/scripts/doctor.py
    python physical_experiment/scripts/doctor.py --json  # JSON 输出
    python physical_experiment/scripts/doctor.py --fix   # 显示修复命令
"""
from __future__ import annotations

import importlib
import json
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Status(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


# =============================================================================
# 环境快照工具函数 (供结果 JSON 使用)
# =============================================================================

def get_environment_snapshot() -> Dict[str, Any]:
    """
    获取完整的环境快照，用于写入结果 JSON 确保可复现性。

    Returns:
        包含以下字段的字典:
        - git_commit: 项目 git commit hash
        - os_info: 操作系统信息
        - kernel: 内核版本
        - python_version: Python 版本
        - gnuradio_version: GNU Radio 版本
        - gr_osmosdr_version: gr-osmosdr 版本
        - hackrf_info: HackRF 驱动和固件信息
        - timestamp: 快照时间戳

    用途:
        - 写入 results/*.json 的 environment 字段
        - 确保实验结果可复现、可审查
    """
    import platform
    from datetime import datetime

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "git_commit": _get_git_commit(),
        "os_info": _get_os_info(),
        "kernel": platform.release(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "gnuradio_version": _get_gnuradio_version(),
        "gr_osmosdr_version": _get_gr_osmosdr_version(),
        "hackrf_info": _get_hackrf_driver_info(),
    }
    return snapshot


def _get_git_commit() -> str:
    """获取当前 git commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]  # 短 hash
    except Exception:
        pass
    return "unknown"


def _get_os_info() -> Dict[str, str]:
    """获取操作系统信息"""
    info = {"name": "unknown", "version": "unknown"}
    try:
        os_release = Path("/etc/os-release")
        if os_release.exists():
            content = os_release.read_text()
            id_match = re.search(r'^ID=(.+)$', content, re.MULTILINE)
            version_match = re.search(r'^VERSION_ID="?([^"]+)"?$', content, re.MULTILINE)
            if id_match:
                info["name"] = id_match.group(1).strip('"')
            if version_match:
                info["version"] = version_match.group(1)
    except Exception:
        pass
    return info


def _get_gnuradio_version() -> str:
    """获取 GNU Radio 版本"""
    try:
        # 方法1: 尝试从 gnuradio 包获取
        try:
            from gnuradio import gr
            if hasattr(gr, 'version'):
                return gr.version()
        except ImportError:
            pass

        # 方法2: 从命令行获取
        result = subprocess.run(
            ["gnuradio-companion", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout + result.stderr
        version_match = re.search(r'(\d+\.\d+\.\d+)', output)
        if version_match:
            return version_match.group(1)
    except Exception:
        pass
    return "unknown"


def _get_gr_osmosdr_version() -> str:
    """获取 gr-osmosdr 版本"""
    try:
        # 方法1: 尝试导入并获取版本
        try:
            import osmosdr
            if hasattr(osmosdr, 'version'):
                return osmosdr.version()
        except (ImportError, AttributeError):
            pass

        # 方法2: 从 dpkg 获取
        result = subprocess.run(
            ["dpkg", "-l", "gr-osmosdr"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # 解析 dpkg -l 输出
            for line in result.stdout.split('\n'):
                if 'gr-osmosdr' in line and line.startswith('ii'):
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]  # 版本号
    except Exception:
        pass
    return "unknown"


def _get_hackrf_driver_info() -> Dict[str, str]:
    """获取 HackRF 驱动和固件信息"""
    info = {
        "driver_installed": False,
        "driver_version": "unknown",
        "devices": []
    }

    try:
        hackrf_info_path = shutil.which("hackrf_info")
        if hackrf_info_path:
            info["driver_installed"] = True

            # 获取 libhackrf 版本
            result = subprocess.run(
                ["hackrf_info", "-v"],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout + result.stderr
            version_match = re.search(r'libhackrf.*?(\d+\.\d+\.\d+|\d{4}\.\d+\.\d+)', output, re.IGNORECASE)
            if version_match:
                info["driver_version"] = version_match.group(1)

            # 获取已连接设备信息
            devices = get_hackrf_devices()
            for dev in devices:
                info["devices"].append({
                    "serial": dev.get("serial", "unknown"),
                    "firmware": dev.get("firmware", "unknown")
                })
    except Exception:
        pass

    return info


# =============================================================================
# HackRF 设备检测工具函数 (供其他模块复用)
# =============================================================================

@dataclass
class HackRFDevice:
    """HackRF 设备信息"""
    serial: str
    firmware: str
    part_id: str = ""
    board_id: str = ""


def get_hackrf_devices(timeout: int = 10) -> List[Dict[str, str]]:
    """
    获取所有已连接的 HackRF 设备信息

    Returns:
        设备列表，每个设备包含 serial, firmware, part_id 等信息
        如果没有设备或检测失败，返回空列表

    用途:
        - doctor.py 环境检测
        - run_hardware_validation.py 设备选择
        - tx/rx_flowgraph.py 设备指定
    """
    hackrf_info_path = shutil.which("hackrf_info")
    if not hackrf_info_path:
        return []

    try:
        proc = subprocess.run(
            ["hackrf_info"],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = proc.stdout + proc.stderr

        # 检查是否找到设备
        if "No HackRF boards found" in output or "hackrf_open() failed" in output:
            return []

        # 解析设备信息
        devices = []
        serial_matches = re.findall(r'Serial number:\s*(\S+)', output)
        firmware_matches = re.findall(r'Firmware Version:\s*(\S+)', output)
        part_id_matches = re.findall(r'Part ID Number:\s*(\S+)', output)
        board_id_matches = re.findall(r'Board ID Number:\s*(\S+)', output)

        for i, serial in enumerate(serial_matches):
            device = {
                "serial": serial,
                "firmware": firmware_matches[i] if i < len(firmware_matches) else "unknown",
                "part_id": part_id_matches[i] if i < len(part_id_matches) else "",
                "board_id": board_id_matches[i] if i < len(board_id_matches) else "",
            }
            devices.append(device)

        return devices

    except (subprocess.TimeoutExpired, Exception):
        return []


def check_dual_hackrf_available() -> Tuple[bool, List[str], str]:
    """
    检查是否有两台 HackRF 可用（hardware 模式必需）

    Returns:
        (is_available, serial_list, message)
        - is_available: True 如果至少有 2 台设备
        - serial_list: 可用设备的序列号列表
        - message: 状态描述信息

    用法:
        ok, serials, msg = check_dual_hackrf_available()
        if not ok:
            print(f"Hardware 模式不可用: {msg}")
            sys.exit(1)
        tx_serial, rx_serial = serials[0], serials[1]
    """
    devices = get_hackrf_devices()

    if len(devices) == 0:
        return False, [], "未检测到 HackRF 设备。请检查 USB 连接。"
    elif len(devices) == 1:
        return False, [devices[0]["serial"]], (
            f"仅检测到 1 台 HackRF (serial: {devices[0]['serial']})。"
            f"Hardware 模式需要 2 台设备（TX + RX 分开）。"
            f"可选方案: 使用两台主机各连接一台 HackRF，或使用 --loopback 模式。"
        )
    else:
        serials = [d["serial"] for d in devices]
        return True, serials, f"检测到 {len(devices)} 台 HackRF: {', '.join(serials)}"


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str
    details: Optional[str] = None
    fix_hint: Optional[str] = None


@dataclass
class DoctorReport:
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def overall_status(self) -> Status:
        if any(c.status == Status.ERROR for c in self.checks):
            return Status.ERROR
        if any(c.status == Status.WARNING for c in self.checks):
            return Status.WARNING
        return Status.OK

    @property
    def passed(self) -> bool:
        return self.overall_status != Status.ERROR


class EnvironmentDoctor:
    """环境自检器"""

    # Ubuntu 版本要求
    SUPPORTED_UBUNTU_VERSIONS = ["22.04", "24.04"]

    # Python 版本要求
    MIN_PYTHON_VERSION = (3, 9)

    # 必需的 Python 包
    REQUIRED_PACKAGES = [
        "zmq",      # pyzmq
        "yaml",     # pyyaml
        "numpy",
        "matplotlib",
    ]

    # 可选的 Python 包
    OPTIONAL_PACKAGES = [
        "scipy",
    ]

    # ZMQ 端口
    ZMQ_PORTS = [5555, 5556]

    def __init__(self):
        self.report = DoctorReport()

    def run_all_checks(self) -> DoctorReport:
        """运行所有检查"""
        self.check_os()
        self.check_python_version()
        self.check_gnuradio()
        self.check_gr_osmosdr()
        self.check_hackrf_driver()
        self.check_udev_rules()
        self.check_plugdev_group()
        self.check_hackrf_devices()
        self.check_python_packages()
        self.check_zmq_ports()
        return self.report

    def check_os(self) -> CheckResult:
        """检查操作系统"""
        result = CheckResult(
            name="操作系统",
            status=Status.OK,
            message=""
        )

        try:
            # 读取 /etc/os-release
            os_release = Path("/etc/os-release")
            if os_release.exists():
                content = os_release.read_text()

                # 解析 ID 和 VERSION_ID
                id_match = re.search(r'^ID=(.+)$', content, re.MULTILINE)
                version_match = re.search(r'^VERSION_ID="?([^"]+)"?$', content, re.MULTILINE)
                pretty_match = re.search(r'^PRETTY_NAME="?([^"]+)"?$', content, re.MULTILINE)

                os_id = id_match.group(1).strip('"') if id_match else "unknown"
                version_id = version_match.group(1) if version_match else "unknown"
                pretty_name = pretty_match.group(1) if pretty_match else f"{os_id} {version_id}"

                if os_id == "ubuntu":
                    if version_id in self.SUPPORTED_UBUNTU_VERSIONS:
                        result.status = Status.OK
                        result.message = f"{pretty_name}"
                    else:
                        result.status = Status.WARNING
                        result.message = f"{pretty_name} (推荐 {'/'.join(self.SUPPORTED_UBUNTU_VERSIONS)})"
                        result.fix_hint = f"推荐使用 Ubuntu {' 或 '.join(self.SUPPORTED_UBUNTU_VERSIONS)}"
                else:
                    result.status = Status.WARNING
                    result.message = f"{pretty_name} (仅支持 Ubuntu)"
                    result.fix_hint = "本项目仅支持 Ubuntu 22.04/24.04"
            else:
                # 可能是 macOS 或其他系统
                import platform
                system = platform.system()
                result.status = Status.WARNING
                result.message = f"{system} (仅支持 Ubuntu)"
                result.fix_hint = "本项目仅支持 Ubuntu 22.04/24.04"

        except Exception as e:
            result.status = Status.WARNING
            result.message = f"无法检测操作系统: {e}"

        self.report.checks.append(result)
        return result

    def check_python_version(self) -> CheckResult:
        """检查 Python 版本"""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"

        if version >= self.MIN_PYTHON_VERSION:
            result = CheckResult(
                name="Python 版本",
                status=Status.OK,
                message=f"Python {version_str}"
            )
        else:
            min_ver_str = f"{self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]}"
            result = CheckResult(
                name="Python 版本",
                status=Status.ERROR,
                message=f"Python {version_str} (需要 >= {min_ver_str})",
                fix_hint=f"请升级到 Python {min_ver_str} 或更高版本"
            )

        self.report.checks.append(result)
        return result

    def check_gnuradio(self) -> CheckResult:
        """检查 GNU Radio 安装"""
        result = CheckResult(
            name="GNU Radio",
            status=Status.OK,
            message=""
        )

        # 检查 gnuradio-companion 命令
        grc_path = shutil.which("gnuradio-companion")
        if not grc_path:
            result.status = Status.ERROR
            result.message = "未安装"
            result.fix_hint = "sudo apt-get install gnuradio"
            self.report.checks.append(result)
            return result

        # 获取版本
        try:
            proc = subprocess.run(
                ["gnuradio-companion", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # 版本信息可能在 stdout 或 stderr
            output = proc.stdout + proc.stderr
            version_match = re.search(r'(\d+\.\d+\.\d+)', output)
            if version_match:
                result.message = f"GNU Radio {version_match.group(1)}"
            else:
                result.message = "GNU Radio (版本未知)"
        except Exception as e:
            result.status = Status.WARNING
            result.message = f"已安装，但无法获取版本: {e}"

        self.report.checks.append(result)
        return result

    def check_gr_osmosdr(self) -> CheckResult:
        """检查 gr-osmosdr 安装"""
        result = CheckResult(
            name="gr-osmosdr",
            status=Status.OK,
            message=""
        )

        try:
            # 尝试导入 osmosdr
            import osmosdr
            result.message = "已安装"

            # 尝试获取版本
            if hasattr(osmosdr, 'version'):
                result.message = f"gr-osmosdr {osmosdr.version()}"
        except ImportError:
            result.status = Status.ERROR
            result.message = "未安装"
            result.fix_hint = "sudo apt-get install gr-osmosdr"
        except Exception as e:
            result.status = Status.WARNING
            result.message = f"已安装，但导入失败: {e}"

        self.report.checks.append(result)
        return result

    def check_hackrf_driver(self) -> CheckResult:
        """检查 HackRF 驱动"""
        result = CheckResult(
            name="HackRF 驱动",
            status=Status.OK,
            message=""
        )

        hackrf_info_path = shutil.which("hackrf_info")
        if not hackrf_info_path:
            result.status = Status.ERROR
            result.message = "未安装"
            result.fix_hint = "sudo apt-get install hackrf"
            self.report.checks.append(result)
            return result

        result.message = "已安装"
        self.report.checks.append(result)
        return result

    def check_udev_rules(self) -> CheckResult:
        """检查 HackRF udev 规则"""
        result = CheckResult(
            name="udev 规则",
            status=Status.OK,
            message=""
        )

        # 搜索 HackRF udev 规则文件
        udev_paths = [
            Path("/etc/udev/rules.d"),
            Path("/lib/udev/rules.d"),
            Path("/usr/lib/udev/rules.d"),
        ]

        hackrf_rules = []
        for udev_dir in udev_paths:
            if udev_dir.exists():
                for rule_file in udev_dir.glob("*hackrf*"):
                    hackrf_rules.append(rule_file)
                # 也检查通用的 SDR 规则
                for rule_file in udev_dir.glob("*rtl-sdr*"):
                    hackrf_rules.append(rule_file)

        if not hackrf_rules:
            result.status = Status.WARNING
            result.message = "未找到 HackRF udev 规则"
            result.fix_hint = (
                "sudo apt-get install --reinstall hackrf\n"
                "   或手动下载: https://github.com/greatscottgadgets/hackrf/blob/master/host/libhackrf/53-hackrf.rules"
            )
        else:
            # 检查规则内容是否包含 plugdev
            has_plugdev = False
            for rule_file in hackrf_rules:
                try:
                    content = rule_file.read_text()
                    if "plugdev" in content.lower():
                        has_plugdev = True
                        break
                except Exception:
                    pass

            if has_plugdev:
                result.message = f"已配置 ({len(hackrf_rules)} 个规则文件)"
                result.details = "\n".join(str(f) for f in hackrf_rules[:3])
            else:
                result.status = Status.WARNING
                result.message = "规则文件存在但未使用 plugdev 组"
                result.fix_hint = "确认 udev 规则包含 GROUP=\"plugdev\""

        self.report.checks.append(result)
        return result

    def check_plugdev_group(self) -> CheckResult:
        """检查用户是否在 plugdev 组"""
        result = CheckResult(
            name="plugdev 用户组",
            status=Status.OK,
            message=""
        )

        import grp
        import os

        username = os.environ.get("SUDO_USER")
        if not username:
            try:
                import pwd
                username = pwd.getpwuid(os.getuid()).pw_name
            except Exception:
                try:
                    username = os.getlogin()
                except Exception:
                    username = os.environ.get("USER", "unknown")

        try:
            # 获取用户所属的所有组
            user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
            # 也检查主组
            try:
                import pwd
                primary_gid = pwd.getpwnam(username).pw_gid
                primary_group = grp.getgrgid(primary_gid).gr_name
                user_groups.append(primary_group)
            except Exception:
                pass

            if "plugdev" in user_groups:
                result.message = f"用户 {username} 在 plugdev 组中"
            else:
                result.status = Status.ERROR
                result.message = f"用户 {username} 不在 plugdev 组"
                result.fix_hint = f"sudo usermod -aG plugdev {username} && 重新登录"

        except Exception as e:
            result.status = Status.WARNING
            result.message = f"无法检查用户组: {e}"

        self.report.checks.append(result)
        return result

    def check_hackrf_devices(self) -> CheckResult:
        """检查 HackRF 设备"""
        result = CheckResult(
            name="HackRF 设备",
            status=Status.OK,
            message=""
        )

        hackrf_info_path = shutil.which("hackrf_info")
        if not hackrf_info_path:
            result.status = Status.ERROR
            result.message = "无法检测（hackrf_info 未安装）"
            self.report.checks.append(result)
            return result

        try:
            devices = get_hackrf_devices()

            if not devices:
                result.status = Status.ERROR
                result.message = "未检测到设备"
                result.fix_hint = (
                    "1. 检查 USB 连接\n"
                    "   2. 运行: sudo udevadm trigger\n"
                    "   3. 确认用户在 plugdev 组: groups $USER\n"
                    "   4. 如果不在，运行: sudo usermod -aG plugdev $USER && 重新登录"
                )
                self.report.checks.append(result)
                return result

            device_count = len(devices)

            if device_count == 1:
                result.status = Status.WARNING
                result.message = f"检测到 1 台设备 (推荐 2 台)"
                result.details = f"序列号: {devices[0]['serial']}"
                result.fix_hint = "推荐使用 2 台 HackRF（TX + RX 分开）"
            else:
                result.status = Status.OK
                result.message = f"检测到 {device_count} 台设备"
                details = []
                for i, dev in enumerate(devices, 1):
                    details.append(f"设备 {i}: {dev['serial']} (固件 {dev['firmware']})")
                result.details = "\n".join(details)

        except subprocess.TimeoutExpired:
            result.status = Status.ERROR
            result.message = "检测超时"
            result.fix_hint = "hackrf_info 命令超时，请检查设备状态"
        except Exception as e:
            result.status = Status.ERROR
            result.message = f"检测失败: {e}"

        self.report.checks.append(result)
        return result

    def check_python_packages(self) -> CheckResult:
        """检查 Python 依赖包"""
        result = CheckResult(
            name="Python 依赖包",
            status=Status.OK,
            message=""
        )

        missing = []
        installed = []

        for pkg in self.REQUIRED_PACKAGES:
            try:
                importlib.import_module(pkg)
                installed.append(pkg)
            except ImportError:
                missing.append(pkg)

        if missing:
            result.status = Status.ERROR
            result.message = f"缺少: {', '.join(missing)}"
            # 映射包名到 pip 包名
            pip_names = {
                "zmq": "pyzmq",
                "yaml": "pyyaml",
            }
            pip_packages = [pip_names.get(p, p) for p in missing]
            result.fix_hint = f"pip install {' '.join(pip_packages)}"
        else:
            result.message = f"全部已安装 ({len(installed)} 个包)"

        self.report.checks.append(result)
        return result

    def check_zmq_ports(self) -> CheckResult:
        """检查 ZMQ 端口可用性"""
        result = CheckResult(
            name="ZMQ 端口",
            status=Status.OK,
            message=""
        )

        available = []
        occupied = []

        for port in self.ZMQ_PORTS:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
                sock.close()
                available.append(port)
            except OSError:
                occupied.append(port)

        if occupied:
            result.status = Status.ERROR
            result.message = f"端口被占用: {', '.join(map(str, occupied))}"
            result.fix_hint = f"lsof -i :{occupied[0]} 查看占用进程，然后 kill 掉"
        else:
            result.message = f"端口 {', '.join(map(str, available))} 可用"

        self.report.checks.append(result)
        return result


def print_report(report: DoctorReport, show_fix: bool = False):
    """打印格式化报告"""

    # 状态图标
    icons = {
        Status.OK: "\u2705",      # ✅
        Status.WARNING: "\u26a0\ufe0f",  # ⚠️
        Status.ERROR: "\u274c",    # ❌
    }

    # 边框宽度
    width = 70

    print()
    print("\u2554" + "\u2550" * width + "\u2557")
    print("\u2551" + "环境自检报告".center(width - 6) + "\u2551")
    print("\u2560" + "\u2550" * width + "\u2563")

    for check in report.checks:
        icon = icons[check.status]
        line = f" {icon} {check.name}: {check.message}"
        # 截断过长的行
        if len(line) > width - 2:
            line = line[:width - 5] + "..."
        print("\u2551" + line.ljust(width) + "\u2551")

        # 显示详情
        if check.details:
            for detail_line in check.details.split("\n"):
                detail = f"    {detail_line}"
                if len(detail) > width - 2:
                    detail = detail[:width - 5] + "..."
                print("\u2551" + detail.ljust(width) + "\u2551")

        # 显示修复建议
        if show_fix and check.fix_hint and check.status != Status.OK:
            for hint_line in check.fix_hint.split("\n"):
                hint = f"    \u2192 {hint_line}"
                if len(hint) > width - 2:
                    hint = hint[:width - 5] + "..."
                print("\u2551" + hint.ljust(width) + "\u2551")

    print("\u2560" + "\u2550" * width + "\u2563")

    # 总体状态
    overall_icon = icons[report.overall_status]
    if report.overall_status == Status.OK:
        status_msg = f" {overall_icon} 状态: 全部通过  可以开始实验"
    elif report.overall_status == Status.WARNING:
        status_msg = f" {overall_icon} 状态: 有警告  可以尝试运行"
    else:
        status_msg = f" {overall_icon} 状态: 有错误  请先修复上述问题"

    print("\u2551" + status_msg.ljust(width) + "\u2551")
    print("\u255a" + "\u2550" * width + "\u255d")
    print()


def print_json_report(report: DoctorReport):
    """打印 JSON 格式报告"""
    # 获取环境快照
    env_snapshot = get_environment_snapshot()

    data = {
        "overall_status": report.overall_status.value,
        "passed": report.passed,
        "environment": env_snapshot,
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
                "details": c.details,
                "fix_hint": c.fix_hint,
            }
            for c in report.checks
        ]
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="环境自检 - 检查物理实验所需的所有依赖"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="显示修复建议"
    )

    args = parser.parse_args()

    doctor = EnvironmentDoctor()
    report = doctor.run_all_checks()

    if args.json:
        print_json_report(report)
    else:
        print_report(report, show_fix=args.fix or not report.passed)

    # 返回退出码
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
