#!/usr/bin/env python3
"""
Full Experiment Automation Script - 一键实验编排

自动化完整的物理实验流程：
1. 环境自检 (doctor.py)
2. 自动启动 TX/RX 流图
3. 校准：测量真实信道特性
4. 防御模式对比：测试所有防御模式
5. 窗口大小扫描：找到最优窗口大小
6. 分析：与仿真对比
7. 报告生成：生成可发表的输出

Usage:
    # 运行完整实验流程
    python run_full_experiment.py

    # 快速测试
    python run_full_experiment.py --quick

    # 跳过自检
    python run_full_experiment.py --skip-doctor

    # 只启动流图（调试用）
    python run_full_experiment.py --flowgraphs-only

    # 手动模式（不自动启动流图）
    python run_full_experiment.py --no-auto-flowgraph
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from physical_experiment.runtime import resolve_output_path, save_runtime_config


# =============================================================================
# 元数据采集
# =============================================================================

def get_environment_info() -> Dict[str, str]:
    """采集环境信息"""
    info = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    # 操作系统信息
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

    # 内核版本
    try:
        result = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["kernel"] = result.stdout.strip()
    except Exception:
        pass

    # GNU Radio 版本
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

    # gr-osmosdr 版本
    try:
        import osmosdr
        if hasattr(osmosdr, 'version'):
            info["gr_osmosdr_version"] = osmosdr.version()
        else:
            info["gr_osmosdr_version"] = "installed"
    except Exception:
        pass

    return info


def get_git_info() -> Dict[str, Any]:
    """采集 Git 信息"""
    info = {}

    try:
        # Commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            info["commit_hash"] = result.stdout.strip()

        # Branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()

        # Is dirty
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
    info = {
        "hackrf_count": 0,
        "devices": []
    }

    try:
        result = subprocess.run(
            ["hackrf_info"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr

        # 解析设备信息
        serial_matches = re.findall(r'Serial number:\s*(\S+)', output)
        firmware_matches = re.findall(r'Firmware Version:\s*(\S+)', output)

        info["hackrf_count"] = len(serial_matches)

        for i, (serial, fw) in enumerate(zip(serial_matches, firmware_matches)):
            role = "tx" if i == 0 else "rx" if i == 1 else f"device_{i}"
            info["devices"].append({
                "serial": serial,
                "role": role,
                "firmware": fw
            })

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
# 流图管理器
# =============================================================================

class FlowgraphManager:
    """管理 GNU Radio 流图子进程"""

    def __init__(self, config: Dict, config_path: Path, verbose: bool = True):
        self.config = config
        self.config_path = Path(config_path)
        self.verbose = verbose
        self.processes: List[subprocess.Popen] = []
        self.process_logs = []

        # 从配置读取参数
        flowgraph_config = config.get("flowgraph", {})
        self.tx_script = PROJECT_ROOT / flowgraph_config.get(
            "tx_script", "physical_experiment/flowgraphs/tx_flowgraph.py"
        )
        self.rx_script = PROJECT_ROOT / flowgraph_config.get(
            "rx_script", "physical_experiment/flowgraphs/rx_flowgraph.py"
        )
        self.startup_timeout = flowgraph_config.get("startup_timeout_s", 10)
        self.shutdown_timeout = flowgraph_config.get("shutdown_timeout_s", 5)
        self.logs_dir = resolve_output_path(config, "logs_dir", "physical_experiment/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        hardware_config = config.get("hardware", {})
        self.tx_serial = hardware_config.get("tx", {}).get("device_serial")
        self.rx_serial = hardware_config.get("rx", {}).get("device_serial")

    def log(self, message: str):
        if self.verbose:
            print(f"[FlowgraphManager] {message}")

    def _wait_for_process_ready(self, proc: subprocess.Popen, timeout: float) -> bool:
        """等待进程稳定运行（避免 RX 端误判）"""
        start = time.time()
        while time.time() - start < timeout:
            if proc.poll() is not None:
                return False
            time.sleep(0.5)
        return True

    def _read_log_tail(self, log_path: Path, lines: int = 40) -> str:
        """Read the tail of a flowgraph log for diagnostics."""
        try:
            content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return ""
        return "\n".join(content[-lines:])

    def _build_flowgraph_command(self, kind: str) -> List[str]:
        """Build a flowgraph command with the resolved runtime config."""
        if kind == "rx":
            cmd = [sys.executable, str(self.rx_script), "--config", str(self.config_path)]
            if self.rx_serial:
                cmd.extend(["--hackrf-serial", self.rx_serial])
            return cmd

        if kind == "tx":
            cmd = [sys.executable, str(self.tx_script), "--config", str(self.config_path)]
            if self.tx_serial:
                cmd.extend(["--hackrf-serial", self.tx_serial])
            return cmd

        raise ValueError(f"Unknown flowgraph kind: {kind}")

    def start_rx(self) -> Optional[subprocess.Popen]:
        """启动接收端流图"""
        if not self.rx_script.exists():
            self.log(f"RX 流图脚本不存在: {self.rx_script}")
            return None

        self.log(f"启动 RX 流图: {self.rx_script}")
        log_path = self.logs_dir / f"run_full_rx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_handle = open(log_path, "w", encoding="utf-8", buffering=1)
        self.process_logs.append(log_handle)

        proc = subprocess.Popen(
            self._build_flowgraph_command("rx"),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            start_new_session=True
        )
        self.processes.append(proc)
        self.log(f"RX 日志: {log_path}")

        self.log("等待 RX 流图进程稳定...")
        if not self._wait_for_process_ready(proc, self.startup_timeout):
            self.log("RX 流图启动异常或提前退出", "ERROR")
            tail = self._read_log_tail(log_path)
            if tail:
                self.log(tail[-1000:], "ERROR")
            return None

        self.log(f"RX 流图已就绪 (PID: {proc.pid})")
        return proc

    def start_tx(self) -> Optional[subprocess.Popen]:
        """启动发送端流图"""
        if not self.tx_script.exists():
            self.log(f"TX 流图脚本不存在: {self.tx_script}")
            return None

        self.log(f"启动 TX 流图: {self.tx_script}")
        log_path = self.logs_dir / f"run_full_tx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_handle = open(log_path, "w", encoding="utf-8", buffering=1)
        self.process_logs.append(log_handle)

        proc = subprocess.Popen(
            self._build_flowgraph_command("tx"),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            start_new_session=True
        )
        self.processes.append(proc)
        self.log(f"TX 日志: {log_path}")

        self.log("等待 TX 流图进程稳定...")
        if not self._wait_for_process_ready(proc, self.startup_timeout):
            self.log("TX 流图启动异常或提前退出", "ERROR")
            tail = self._read_log_tail(log_path)
            if tail:
                self.log(tail[-1000:], "ERROR")
            return None

        self.log(f"TX 流图已就绪 (PID: {proc.pid})")
        return proc

    def start_all(self) -> bool:
        """启动所有流图"""
        self.log("启动所有流图...")

        # 先启动 RX，再启动 TX
        rx_proc = self.start_rx()
        if rx_proc is None:
            return False

        tx_proc = self.start_tx()
        if tx_proc is None:
            self.shutdown_all()
            return False

        self.log("所有流图已启动")
        return True

    def shutdown_all(self):
        """优雅关闭所有流图"""
        self.log("关闭所有流图...")

        for proc in self.processes:
            if proc.poll() is None:  # 进程仍在运行
                self.log(f"发送 SIGTERM 到 PID {proc.pid}")
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except Exception:
                    proc.terminate()

        # 等待进程退出
        for proc in self.processes:
            try:
                proc.wait(timeout=self.shutdown_timeout)
                self.log(f"进程 {proc.pid} 已退出")
            except subprocess.TimeoutExpired:
                self.log(f"进程 {proc.pid} 未响应，强制终止")
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    proc.kill()
                proc.wait()

        self.processes.clear()
        for log_handle in self.process_logs:
            try:
                log_handle.close()
            except Exception:
                pass
        self.process_logs.clear()
        self.log("所有流图已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown_all()
        return False


# =============================================================================
# 实验编排器
# =============================================================================

class ExperimentOrchestrator:
    """编排完整实验流程"""

    def __init__(self, config: Dict, verbose: bool = True):
        self.config = config
        self.verbose = verbose

        # 输出目录
        output_config = config.get("output", {})
        self.results_dir = resolve_output_path(config, "results_dir", "physical_experiment/results")
        self.logs_dir = resolve_output_path(config, "logs_dir", "physical_experiment/logs")
        self.figures_dir = resolve_output_path(config, "figures_dir", "figures")
        self.reports_dir = resolve_output_path(config, "reports_dir", "physical_experiment/reports")

        # 确保目录存在
        for d in [self.results_dir, self.logs_dir, self.figures_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 实验 ID 和元数据
        self.metadata = collect_metadata()
        self.experiment_id = self.metadata["experiment_id"]
        self.log_file = self.logs_dir / f"experiment_{self.experiment_id}.log"
        self.runtime_config_path = save_runtime_config(
            self.config,
            self.logs_dir / f"runtime_config_{self.experiment_id}.yaml",
        )

        # 流图管理器
        self.flowgraph_manager: Optional[FlowgraphManager] = None

    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"

        if self.verbose:
            print(log_line)

        with open(self.log_file, 'a') as f:
            f.write(log_line + "\n")

    def run_doctor(self) -> bool:
        """运行环境自检"""
        self.log("=" * 60)
        self.log("环境自检")
        self.log("=" * 60)

        doctor_script = PROJECT_ROOT / "physical_experiment/scripts/doctor.py"
        if not doctor_script.exists():
            self.log("doctor.py 不存在，跳过自检", "WARNING")
            return True

        try:
            result = subprocess.run(
                [sys.executable, str(doctor_script)],
                capture_output=False,
                timeout=60,
                cwd=str(PROJECT_ROOT)
            )

            if result.returncode == 0:
                self.log("环境自检通过")
                return True
            else:
                self.log("环境自检失败", "ERROR")
                return False

        except Exception as e:
            self.log(f"环境自检异常: {e}", "ERROR")
            return False

    def run_command(self, cmd: List[str], description: str) -> bool:
        """运行命令"""
        self.log(f"运行: {description}")
        self.log(f"命令: {' '.join(cmd)}", "DEBUG")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=3600
            )

            if result.returncode == 0:
                self.log(f"成功: {description}")
                return True
            else:
                self.log(f"失败: {description}", "ERROR")
                err_text = (result.stderr or "").strip()
                out_text = (result.stdout or "").strip()
                if err_text and out_text:
                    detail = f"[stderr]\n{err_text}\n[stdout]\n{out_text}"
                else:
                    detail = err_text if err_text else out_text
                if detail:
                    self.log(detail[-500:], "ERROR")
                return False

        except subprocess.TimeoutExpired:
            self.log(f"超时: {description}", "ERROR")
            return False
        except Exception as e:
            self.log(f"异常: {e}", "ERROR")
            return False

    def phase_calibration(self) -> bool:
        """校准阶段"""
        phase_config = self.config.get("phases", {}).get("calibration", {})
        if not phase_config.get("enabled", True):
            self.log("校准阶段已禁用，跳过")
            return True

        self.log("\n" + "=" * 60)
        self.log("阶段 1: 信道校准")
        self.log("=" * 60)

        packets = phase_config.get("packets", self.config.get("calibration", {}).get("packets", 1000))
        distances = phase_config.get("distances", ["default"])

        all_ok = True
        for label in distances:
            self.log(f"\n校准条件: {label}")

            cmd = [
                sys.executable,
                "physical_experiment/scripts/calibration.py",
                "--config", str(self.runtime_config_path),
                "--packets", str(packets),
                "--label", label,
                "--output-dir", str(self.results_dir)
            ]

            ok = self.run_command(cmd, f"校准 ({label})")
            all_ok = all_ok and ok

        return all_ok

    def phase_defense_comparison(self) -> bool:
        """防御模式对比阶段"""
        phase_config = self.config.get("phases", {}).get("defense_comparison", {})
        if not phase_config.get("enabled", True):
            self.log("防御对比阶段已禁用，跳过")
            return True

        self.log("\n" + "=" * 60)
        self.log("阶段 2: 防御模式对比")
        self.log("=" * 60)

        modes = phase_config.get("modes", ["window"])
        runs = phase_config.get("runs_per_mode", self.config.get("experiment", {}).get("runs_per_config", 10))

        cmd = [
            sys.executable,
            "physical_experiment/scripts/experiment_runner.py",
            "--modes", *modes,
            "--runs", str(runs),
            "--config", str(self.runtime_config_path),
        ]

        return self.run_command(cmd, "防御模式对比")

    def phase_window_sweep(self) -> bool:
        """窗口大小扫描阶段"""
        phase_config = self.config.get("phases", {}).get("window_sweep", {})
        if not phase_config.get("enabled", True):
            self.log("窗口扫描阶段已禁用，跳过")
            return True

        self.log("\n" + "=" * 60)
        self.log("阶段 3: 窗口大小扫描")
        self.log("=" * 60)

        window_sizes = phase_config.get("window_sizes", [3, 5, 8])
        runs = phase_config.get("runs_per_size", 5)

        all_ok = True
        for ws in window_sizes:
            self.log(f"\n测试窗口大小: {ws}")

            cmd = [
                sys.executable,
                "physical_experiment/scripts/experiment_runner.py",
                "--mode", "window",
                "--window-size", str(ws),
                "--runs", str(runs),
                "--config", str(self.runtime_config_path),
            ]

            ok = self.run_command(cmd, f"窗口大小 {ws}")
            all_ok = all_ok and ok

        return all_ok

    def phase_analysis(self) -> bool:
        """分析阶段"""
        phase_config = self.config.get("phases", {}).get("analysis", {})
        if not phase_config.get("enabled", True):
            self.log("分析阶段已禁用，跳过")
            return True

        self.log("\n" + "=" * 60)
        self.log("阶段 4: 分析与对比")
        self.log("=" * 60)

        cmd = [
            sys.executable,
            "physical_experiment/analysis/compare_sim_vs_hw.py",
            "--hw-pattern", f"{self.results_dir}/experiment_*.json",
            "--output-dir", str(self.figures_dir)
        ]

        success = self.run_command(cmd, "仿真 vs 硬件对比")

        # 生成总结报告
        self._generate_summary_report()

        return success

    def _generate_summary_report(self):
        """生成总结报告"""
        self.log("\n生成总结报告...")

        report_lines = [
            "# 物理实验总结报告",
            f"\n实验 ID: {self.experiment_id}",
            f"生成时间: {datetime.now().isoformat()}",
            "",
            "## 元数据",
            "",
            "### 环境",
            f"- 操作系统: {self.metadata['environment'].get('os', 'unknown')}",
            f"- Python: {self.metadata['environment'].get('python_version', 'unknown')}",
            f"- GNU Radio: {self.metadata['environment'].get('gnuradio_version', 'unknown')}",
            "",
            "### Git",
            f"- Commit: {self.metadata['git'].get('commit_hash', 'unknown')[:12]}",
            f"- Branch: {self.metadata['git'].get('branch', 'unknown')}",
            f"- Dirty: {self.metadata['git'].get('is_dirty', 'unknown')}",
            "",
            "### 硬件",
            f"- HackRF 数量: {self.metadata['hardware'].get('hackrf_count', 0)}",
        ]

        for device in self.metadata['hardware'].get('devices', []):
            report_lines.append(f"  - {device['role']}: {device['serial']} (固件 {device['firmware']})")

        report_lines.extend([
            "",
            "## 配置",
            "```yaml",
            yaml.dump(self.config, default_flow_style=False, allow_unicode=True),
            "```",
            "",
            "## 结果文件",
            ""
        ])

        # 列出结果文件
        for f in sorted(self.results_dir.glob("experiment_*.json"))[-10:]:
            report_lines.append(f"- `{f.name}`")

        report_lines.extend([
            "",
            "## 下一步",
            "",
            "1. 查看 `figures/` 目录中的图表",
            "2. 对比仿真预测与硬件测量",
            "3. 使用校准数据调整仿真参数",
        ])

        report_text = "\n".join(report_lines)
        report_file = self.reports_dir / f"experiment_report_{self.experiment_id}.md"

        with open(report_file, 'w') as f:
            f.write(report_text)

        self.log(f"报告已保存: {report_file}")

    def save_result_with_metadata(self, results: List[Dict]) -> Path:
        """保存带完整元数据的结果"""
        output = {
            "metadata": self.metadata,
            "config": self.config,
            "results": results
        }

        output_file = self.results_dir / f"experiment_{self.experiment_id}.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        self.log(f"结果已保存: {output_file}")
        return output_file

    def run_all(
        self,
        skip_doctor: bool = False,
        auto_flowgraph: bool = True,
        flowgraphs_only: bool = False
    ) -> bool:
        """运行完整实验流程"""
        self.log("=" * 60)
        self.log("物理实验自动化")
        self.log(f"实验 ID: {self.experiment_id}")
        self.log("=" * 60)

        start_time = time.time()

        # 环境自检
        if not skip_doctor and self.config.get("doctor", {}).get("run_before_experiment", True):
            if not self.run_doctor():
                fail_on_warning = self.config.get("doctor", {}).get("fail_on_warning", False)
                if fail_on_warning:
                    self.log("环境自检失败，终止实验", "ERROR")
                    return False
                else:
                    self.log("环境自检有警告，继续实验", "WARNING")

        # 启动流图
        if auto_flowgraph and self.config.get("flowgraph", {}).get("auto_start", True):
            self.flowgraph_manager = FlowgraphManager(
                self.config,
                config_path=self.runtime_config_path,
                verbose=self.verbose,
            )

            if not self.flowgraph_manager.start_all():
                self.log("流图启动失败", "ERROR")
                return False

            if flowgraphs_only:
                self.log("\n流图已启动，按 Ctrl+C 退出...")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
                self.flowgraph_manager.shutdown_all()
                return True

        try:
            # 运行各阶段
            phases = [
                ("校准", self.phase_calibration),
                ("防御对比", self.phase_defense_comparison),
                ("窗口扫描", self.phase_window_sweep),
                ("分析", self.phase_analysis)
            ]

            results = {}
            for phase_name, phase_func in phases:
                self.log(f"\n开始阶段: {phase_name}")
                try:
                    results[phase_name] = phase_func()
                except Exception as e:
                    self.log(f"阶段 {phase_name} 异常: {e}", "ERROR")
                    results[phase_name] = False

            elapsed = time.time() - start_time

            # 最终总结
            self.log("\n" + "=" * 60)
            self.log("实验完成")
            self.log("=" * 60)
            self.log(f"总耗时: {elapsed/60:.1f} 分钟")

            for phase_name, success in results.items():
                status = "\u2713" if success else "\u2717"
                self.log(f"  {status} {phase_name}")

            all_success = all(results.values())
            if all_success:
                self.log("\n所有阶段成功完成！")
            else:
                self.log("\n部分阶段失败，请查看日志", "WARNING")

            return all_success

        finally:
            # 确保关闭流图
            if self.flowgraph_manager:
                self.flowgraph_manager.shutdown_all()


# =============================================================================
# 配置加载
# =============================================================================

def load_config(config_path: Optional[str] = None) -> Dict:
    """加载配置文件"""
    if config_path is None:
        config_path = PROJECT_ROOT / "physical_experiment/configs/experiment_config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path) as f:
        return yaml.safe_load(f)


def apply_quick_mode(config: Dict) -> Dict:
    """应用快速测试模式"""
    # 减少校准包数
    if "phases" in config and "calibration" in config["phases"]:
        config["phases"]["calibration"]["packets"] = 100
        config["phases"]["calibration"]["distances"] = ["quick_test"]

    # 减少运行次数
    if "phases" in config and "defense_comparison" in config["phases"]:
        config["phases"]["defense_comparison"]["runs_per_mode"] = 2

    # 减少窗口扫描
    if "phases" in config and "window_sweep" in config["phases"]:
        config["phases"]["window_sweep"]["window_sizes"] = [3, 5]
        config["phases"]["window_sweep"]["runs_per_size"] = 2

    # 减少流量
    if "traffic" in config:
        config["traffic"]["num_legit_frames"] = 20
        config["traffic"]["num_replay_attempts"] = 10

    return config


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="物理实验一键自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行完整实验
  python run_full_experiment.py

  # 快速测试（减少运行次数）
  python run_full_experiment.py --quick

  # 跳过环境自检
  python run_full_experiment.py --skip-doctor

  # 只启动流图（调试用）
  python run_full_experiment.py --flowgraphs-only

  # 手动模式（不自动启动流图）
  python run_full_experiment.py --no-auto-flowgraph

  # 只运行特定阶段
  python run_full_experiment.py --phase calibration
"""
    )

    parser.add_argument("--config", type=str,
                        help="配置文件路径")
    parser.add_argument("--phase", type=str,
                        choices=["calibration", "defense", "window", "analysis"],
                        help="只运行特定阶段")
    parser.add_argument("--quick", action="store_true",
                        help="快速测试模式（减少运行次数）")
    parser.add_argument("--skip-doctor", action="store_true",
                        help="跳过环境自检")
    parser.add_argument("--flowgraphs-only", action="store_true",
                        help="只启动流图，不运行实验")
    parser.add_argument("--no-auto-flowgraph", action="store_true",
                        help="不自动启动流图（手动模式）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只显示配置，不运行")
    parser.add_argument("--quiet", action="store_true",
                        help="减少输出")

    args = parser.parse_args()

    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # 应用 CLI 覆盖
    if args.quick:
        config = apply_quick_mode(config)

    if args.phase:
        # 禁用所有阶段，只启用指定的阶段
        phase_map = {
            "calibration": "calibration",
            "defense": "defense_comparison",
            "window": "window_sweep",
            "analysis": "analysis"
        }
        for phase_name in config.get("phases", {}):
            config["phases"][phase_name]["enabled"] = False
        config["phases"][phase_map[args.phase]]["enabled"] = True

    if args.dry_run:
        print("配置:")
        print(yaml.dump(config, default_flow_style=False, allow_unicode=True))
        return

    # 运行实验
    orchestrator = ExperimentOrchestrator(config, verbose=not args.quiet)

    # 设置信号处理
    def signal_handler(sig, frame):
        orchestrator.log("\n收到中断信号，正在清理...", "WARNING")
        if orchestrator.flowgraph_manager:
            orchestrator.flowgraph_manager.shutdown_all()
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        success = orchestrator.run_all(
            skip_doctor=args.skip_doctor,
            auto_flowgraph=not args.no_auto_flowgraph,
            flowgraphs_only=args.flowgraphs_only
        )
        sys.exit(0 if success else 1)

    except Exception as e:
        orchestrator.log(f"实验异常: {e}", "ERROR")
        if orchestrator.flowgraph_manager:
            orchestrator.flowgraph_manager.shutdown_all()
        sys.exit(1)


if __name__ == "__main__":
    main()
