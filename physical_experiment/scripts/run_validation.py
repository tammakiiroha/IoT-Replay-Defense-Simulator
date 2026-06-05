#!/usr/bin/env python3
"""
物理对照实验 - 验证模拟实验的有效性

方案：
  A. 在理想信道条件下（近距离，p_loss≈0）对比物理实验与模拟实验结果
  B. 在受控丢包条件下（p_loss=0.1, 0.2）验证模型统计一致性

使用方法：
    # 仅 Loopback 测试（无需硬件）
    python run_validation.py --loopback

    # 真实硬件实验
    python run_validation.py

    # 快速测试
    python run_validation.py --quick --loopback

    # 受控丢包采样验证 (目标 B)
    python run_validation.py --loopback --loss-samples 0,0.1,0.2

    # 链路自检 (A2 前置)
    python run_validation.py --link-selftest

结论强度说明：
    本验证仅证明：
    - (A) 理想链路下，实机链路与仿真在 LAR/ASR 上一致
    - (B) 在人为注入的 i.i.d 丢包采样点上，统计结果与仿真一致
    本验证不证明：
    - 模型在全参数空间有效
    - W=3~5 在现实无线环境最优
    - p_reorder 维度的有效性（本实验未覆盖）
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from replay.core.channel_models import GilbertElliottLoss as CoreGilbertElliottLoss
from replay.core.stats import wilson_ci as core_wilson_ci

# 导入模拟实验组件
from sim.commands import DEFAULT_COMMANDS
from sim.defaults import (
    DEFAULT_ATTACK_MODE,
    DEFAULT_CHALLENGE_NONCE_BITS,
    DEFAULT_INLINE_ATTACK_BURST,
    DEFAULT_INLINE_ATTACK_PROBABILITY,
    DEFAULT_MAC_LENGTH,
    DEFAULT_SHARED_KEY,
)
from sim.experiment import simulate_one_run
from sim.rng import DeterministicRNG
from sim.types import Mode, AttackMode, SimulationConfig


# =============================================================================
# 统计工具 - Wilson 置信区间 (P1-1)
# =============================================================================

def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    计算二项分布的 Wilson 置信区间

    比普通的 Wald 区间更准确，尤其在 p 接近 0 或 1 时。

    Args:
        successes: 成功次数
        trials: 总试验次数
        confidence: 置信水平 (默认 95%)

    Returns:
        (lower, upper): 置信区间下界和上界

    参考:
        Wilson, E.B. (1927). "Probable Inference, the Law of Succession, and Statistical Inference"
    """
    ci = core_wilson_ci(successes, trials, confidence)
    return (ci.lower, ci.upper)


def ci_overlap(ci1: Tuple[float, float], ci2: Tuple[float, float]) -> bool:
    """检查两个置信区间是否重叠"""
    return ci1[0] <= ci2[1] and ci2[0] <= ci1[1]


def point_in_ci(point: float, ci: Tuple[float, float]) -> bool:
    """检查点估计是否在置信区间内"""
    return ci[0] <= point <= ci[1]


@dataclass
class StatisticalResult:
    """统计结果（包含置信区间）"""
    point_estimate: float
    ci_lower: float
    ci_upper: float
    successes: int
    trials: int

    @property
    def ci(self) -> Tuple[float, float]:
        return (self.ci_lower, self.ci_upper)

    def __str__(self) -> str:
        return f"{self.point_estimate:.2%} [{self.ci_lower:.2%}, {self.ci_upper:.2%}]"


def compute_rate_with_ci(successes: int, trials: int, confidence: float = 0.95) -> StatisticalResult:
    """计算比率及其置信区间"""
    if trials == 0:
        return StatisticalResult(0.0, 0.0, 1.0, 0, 0)

    point = successes / trials
    lower, upper = wilson_ci(successes, trials, confidence)

    return StatisticalResult(point, lower, upper, successes, trials)


# =============================================================================
# Gilbert-Elliott 突发丢包模型 (P1-3)
# =============================================================================

class GilbertElliottLoss:
    """
    Gilbert-Elliott 突发丢包模型

    双状态马尔科夫链:
    - Good 状态: 低丢包率 (p_loss_good)
    - Bad 状态: 高丢包率 (p_loss_bad)

    状态转移:
    - p_good_to_bad: Good -> Bad 转移概率
    - p_bad_to_good: Bad -> Good 转移概率

    用途:
    - 敏感性分析：验证模型对突发丢包的鲁棒性
    - 不代表真实信道，仅用于边界测试
    """

    def __init__(
        self,
        p_loss_good: float = 0.01,
        p_loss_bad: float = 0.5,
        p_good_to_bad: float = 0.05,
        p_bad_to_good: float = 0.3,
        seed: int = 42
    ):
        self.p_loss_good = p_loss_good
        self.p_loss_bad = p_loss_bad
        self.p_good_to_bad = p_good_to_bad
        self.p_bad_to_good = p_bad_to_good

        self.rng = random.Random(seed)
        self._model = CoreGilbertElliottLoss(
            p_good_to_bad=p_good_to_bad,
            p_bad_to_good=p_bad_to_good,
            loss_good=p_loss_good,
            loss_bad=p_loss_bad,
        )

        # 统计
        self.total_frames = 0
        self.lost_frames = 0
        self.good_state_frames = 0
        self.bad_state_frames = 0

    @property
    def avg_loss_rate(self) -> float:
        """平均丢包率（基于稳态概率）"""
        return self._model.steady_state_loss

    @property
    def avg_burst_length(self) -> float:
        """平均突发长度"""
        if self.p_bad_to_good == 0:
            return float('inf')
        return 1 / self.p_bad_to_good

    def should_drop(self) -> bool:
        """决定是否丢弃当前帧"""
        self.total_frames += 1

        dropped = self._model.dropped(self.rng)
        if self._model.in_bad_state:
            self.bad_state_frames += 1
        else:
            self.good_state_frames += 1

        if dropped:
            self.lost_frames += 1
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "model": "gilbert_elliott",
            "p_loss_good": self.p_loss_good,
            "p_loss_bad": self.p_loss_bad,
            "p_good_to_bad": self.p_good_to_bad,
            "p_bad_to_good": self.p_bad_to_good,
            "avg_loss_rate_theoretical": self.avg_loss_rate,
            "avg_burst_length": self.avg_burst_length,
            "total_frames": self.total_frames,
            "lost_frames": self.lost_frames,
            "actual_loss_rate": self.lost_frames / self.total_frames if self.total_frames > 0 else 0,
            "good_state_frames": self.good_state_frames,
            "bad_state_frames": self.bad_state_frames,
        }


# =============================================================================
# LossyTransport - 受控丢包注入层 (目标 B)
# =============================================================================

class LossyTransport:
    """
    受控丢包传输层包装器

    用途：在 physical 流程外包一层，人为注入丢包，
          以验证仿真模型在受控条件下的统计一致性。

    支持两种丢包模型:
    - iid: 独立同分布丢包 (与 sim 的 p_loss 语义对齐)
    - burst: Gilbert-Elliott 突发丢包 (敏感性分析用)

    支持两种丢包率模式:
    - inject: 直接指定注入丢包率 p_inject（默认）
    - target: 指定目标总丢包率 p_target，自动计算注入率
              p_inject = (p_target - p_native) / (1 - p_native)
              需要先通过 link-selftest 估计 p_native

    统计口径：
        - 丢包注入位置为 rx（默认）：帧到达但不交付上层，等效于"信道丢失"
        - 与 sim 的 p_loss 语义对齐：帧未到达 Receiver

    注意：这不是"真实无线信道验证"，而是"受控条件下的统计一致性验证"
    """

    def __init__(
        self,
        inner,
        p_loss: float = 0.0,
        seed: int = 42,
        direction: str = "rx",
        loss_model: str = "iid",
        burst_config: Optional[Dict[str, float]] = None,
        p_native: float = 0.0,
        loss_rate_mode: str = "inject"
    ):
        """
        Args:
            inner: 被包装的传输层 (LoopbackTransport 或 HardwareTransport)
            p_loss: 丢包概率 [0.0, 1.0] (iid 模型) 或平均丢包率 (burst 模型)
                    - inject 模式: 直接作为注入率
                    - target 模式: 作为目标总丢包率
            seed: 随机种子（写入结果文件，保证可复现）
            direction: 丢包注入位置 ("rx" 或 "tx")
            loss_model: "iid" 或 "burst" (Gilbert-Elliott)
            burst_config: burst 模型参数 (可选)
            p_native: 原生丢包率 (CRC/同步失败等)，用于 target 模式计算
            loss_rate_mode: "inject" (直接注入) 或 "target" (目标总丢包率)
        """
        self.inner = inner
        self.seed = seed
        self.direction = direction
        self.loss_model = loss_model
        self.loss_rate_mode = loss_rate_mode
        self.p_native = float(p_native)

        # 计算实际注入率
        if loss_rate_mode == "target":
            # p_target 模式: 计算需要注入的丢包率
            # 公式: p_inject = (p_target - p_native) / (1 - p_native)
            p_target = float(p_loss)
            if p_target < self.p_native:
                # 目标丢包率低于原生丢包率，无法实现
                print(f"⚠️ 警告: 目标丢包率 {p_target:.1%} 低于原生丢包率 {self.p_native:.1%}，设为 0")
                self.p_loss = 0.0
            elif self.p_native >= 1.0:
                self.p_loss = 0.0
            else:
                self.p_loss = (p_target - self.p_native) / (1 - self.p_native)
            self.p_target = p_target
        else:
            # inject 模式: 直接使用指定的注入率
            self.p_loss = float(p_loss)
            self.p_target = None

        if loss_model == "burst":
            # 配置 Gilbert-Elliott 模型
            cfg = burst_config or {}
            self.ge_model = GilbertElliottLoss(
                p_loss_good=cfg.get("p_loss_good", 0.01),
                p_loss_bad=cfg.get("p_loss_bad", 0.5),
                p_good_to_bad=cfg.get("p_good_to_bad", 0.05),
                p_bad_to_good=cfg.get("p_bad_to_good", 0.3),
                seed=seed
            )
            self.rng = None
        else:
            self.rng = random.Random(seed)
            self.ge_model = None

        # 统计计数
        self.injected_loss_count = 0
        self.total_frames_seen = 0

    def _should_drop(self) -> bool:
        """决定是否丢弃帧"""
        if self.loss_model == "burst" and self.ge_model:
            return self.ge_model.should_drop()
        else:
            return self.rng.random() < self.p_loss

    @property
    def is_loopback(self) -> bool:
        return getattr(self.inner, "is_loopback", False)

    @property
    def connected(self) -> bool:
        return self.inner.connected

    def connect(self) -> bool:
        return self.inner.connect()

    def disconnect(self):
        self.inner.disconnect()

    def set_rng(self, rng: random.Random) -> None:
        if hasattr(self.inner, "set_rng"):
            self.inner.set_rng(rng)

    def send_frame(self, frame: Frame) -> None:
        if self.direction == "tx" and self._should_drop():
            self.injected_loss_count += 1
            return  # 等效"信道丢失"，不发出去
        self.inner.send_frame(frame)

    def receive_frame(self) -> Optional[tuple[Frame, float]]:
        result = self.inner.receive_frame()
        if result is None:
            return None  # 原生丢包/同步失败/CRC失败 → loss

        self.total_frames_seen += 1

        if self.direction == "rx" and self._should_drop():
            self.injected_loss_count += 1
            return None  # 人为注入 loss：到达但不交付上层

        return result

    def receive_all_pending(self) -> List[tuple[Frame, float]]:
        """兼容 LoopbackTransport 的批量接收"""
        if hasattr(self.inner, 'receive_all_pending'):
            results = self.inner.receive_all_pending()
            filtered = []
            for frame, latency in results:
                self.total_frames_seen += 1
                if self.direction == "rx" and self._should_drop():
                    self.injected_loss_count += 1
                    continue  # 丢弃
                filtered.append((frame, latency))
            return filtered
        return []

    def has_pending(self) -> bool:
        if hasattr(self.inner, 'has_pending'):
            return self.inner.has_pending()
        return False

    def flush(self) -> List[Frame]:
        if hasattr(self.inner, 'flush'):
            frames = self.inner.flush()
            filtered = []
            for frame in frames:
                self.total_frames_seen += 1
                if self.direction == "rx" and self._should_drop():
                    self.injected_loss_count += 1
                    continue
                filtered.append(frame)
            return filtered
        return []

    def get_stats(self) -> Dict[str, Any]:
        """返回丢包统计（写入结果文件）"""
        stats = {
            "p_loss_injected": self.p_loss,
            "loss_seed": self.seed,
            "loss_direction": self.direction,
            "loss_model": self.loss_model,
            "loss_rate_mode": self.loss_rate_mode,
            "injected_loss_count": self.injected_loss_count,
            "total_frames_seen": self.total_frames_seen,
            "actual_loss_rate": (
                self.injected_loss_count / self.total_frames_seen
                if self.total_frames_seen > 0 else 0.0
            )
        }

        # target 模式额外信息
        if self.loss_rate_mode == "target":
            stats["p_target"] = self.p_target
            stats["p_native"] = self.p_native
            stats["p_inject_calculated"] = self.p_loss

        if self.ge_model:
            stats["burst_stats"] = self.ge_model.get_stats()

        return stats


# 导入物理实验组件
from physical_experiment.scripts.experiment_runner import (
    HardwareExperiment, LoopbackTransport, RunResult
)
from physical_experiment.scripts.doctor import get_environment_snapshot


@dataclass
class ValidationResult:
    """单个配置的验证结果"""
    mode: str
    window_size: int

    # 受控丢包参数 (目标 B)
    p_loss_injected: float  # 注入的丢包率
    loss_seed: int          # 丢包随机种子

    # 物理实验结果 (P1-1: 包含原始计数以支持 Wilson CI)
    physical_lar: float
    physical_asr: float
    physical_runs: int

    # 模拟实验结果
    sim_lar: float
    sim_asr: float
    sim_runs: int

    # 误差 (保留兼容性)
    lar_error: float  # |physical - sim| / sim
    asr_error: float

    # 是否通过验证 (P1-1: 基于 CI 重叠)
    lar_valid: bool  # CI 重叠或误差 < 10%
    asr_valid: bool

    # 物理实验计数
    physical_legit_accepted: int = 0
    physical_legit_total: int = 0
    physical_attack_success: int = 0
    physical_attack_total: int = 0

    # 模拟实验计数
    sim_legit_accepted: int = 0
    sim_legit_total: int = 0
    sim_attack_success: int = 0
    sim_attack_total: int = 0

    # P1-1: Wilson CI 结果
    physical_lar_ci: Optional[Tuple[float, float]] = None
    physical_asr_ci: Optional[Tuple[float, float]] = None
    sim_lar_ci: Optional[Tuple[float, float]] = None
    sim_asr_ci: Optional[Tuple[float, float]] = None
    lar_ci_overlap: bool = True
    asr_ci_overlap: bool = True

    # 丢包统计 (可选)
    loss_stats: Optional[Dict[str, Any]] = None


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = PROJECT_ROOT / "physical_experiment/configs/experiment_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@dataclass
class SimulationResult:
    """模拟实验结果 (P1-1: 包含原始计数)"""
    avg_lar: float
    avg_asr: float
    total_legit_accepted: int
    total_legit_sent: int
    total_attack_success: int
    total_attack_sent: int


def run_simulation(
    mode: Mode,
    window_size: int,
    num_runs: int,
    num_legit: int,
    num_attack: int,
    p_loss: float = 0.0,
    p_reorder: float = 0.0,
    seed: int = 42,
    attacker_record_loss: float = 0.0,
    attack_mode: AttackMode = DEFAULT_ATTACK_MODE,
    inline_attack_probability: float = DEFAULT_INLINE_ATTACK_PROBABILITY,
    inline_attack_burst: int = DEFAULT_INLINE_ATTACK_BURST,
    challenge_nonce_bits: int = DEFAULT_CHALLENGE_NONCE_BITS,
    shared_key: str = DEFAULT_SHARED_KEY,
    mac_length: int = DEFAULT_MAC_LENGTH,
    command_set: Optional[List[str]] = None,
) -> SimulationResult:
    """
    运行模拟实验（复用 sim.experiment.simulate_one_run）

    Returns:
        SimulationResult with counts and rates
    """
    mode_rng = DeterministicRNG(seed)
    total_legit_accepted = 0
    total_attack_success = 0
    total_legit_sent = 0
    total_attack_sent = 0

    base_config = SimulationConfig(
        mode=mode,
        attack_mode=attack_mode,
        num_legit=num_legit,
        num_replay=num_attack,
        p_loss=p_loss,
        p_reorder=p_reorder,
        window_size=window_size,
        command_set=command_set or DEFAULT_COMMANDS,
        shared_key=shared_key,
        mac_length=mac_length,
        attacker_record_loss=attacker_record_loss,
        inline_attack_probability=inline_attack_probability,
        inline_attack_burst=inline_attack_burst,
        challenge_nonce_bits=challenge_nonce_bits,
    )

    for _ in range(num_runs):
        scenario_seed = mode_rng.randint(0, 2**31 - 1)
        scenario_rng = DeterministicRNG(scenario_seed)
        run_result = simulate_one_run(base_config, rng=scenario_rng)

        total_legit_accepted += run_result.legit_accepted
        total_attack_success += run_result.attack_success
        total_legit_sent += run_result.legit_sent
        total_attack_sent += run_result.attack_attempts

    avg_lar = total_legit_accepted / total_legit_sent if total_legit_sent > 0 else 0.0
    avg_asr = total_attack_success / total_attack_sent if total_attack_sent > 0 else 0.0

    return SimulationResult(
        avg_lar=avg_lar,
        avg_asr=avg_asr,
        total_legit_accepted=total_legit_accepted,
        total_legit_sent=total_legit_sent,
        total_attack_success=total_attack_success,
        total_attack_sent=total_attack_sent
    )


@dataclass
class PhysicalResult:
    """物理实验结果 (P1-1: 包含原始计数)"""
    avg_lar: float
    avg_asr: float
    total_legit_accepted: int
    total_legit_sent: int
    total_attack_success: int
    total_attack_sent: int
    loss_stats: Optional[Dict[str, Any]] = None


def run_physical_experiment(
    config: Dict[str, Any],
    mode: Mode,
    window_size: int,
    num_runs: int,
    loopback: bool = True,
    seed: int = 42,
    p_loss_inject: float = 0.0,
    loss_seed: int = 42,
    loss_direction: str = "rx",
    loss_model: str = "iid",
    burst_config: Optional[Dict[str, float]] = None,
    p_native: float = 0.0,
    loss_rate_mode: str = "inject"
) -> PhysicalResult:
    """
    运行物理实验（或 Loopback 模式）

    Args:
        p_loss_inject: 受控丢包注入率 (目标 B)
        loss_seed: 丢包注入随机种子
        loss_direction: 丢包注入位置 ("rx" 或 "tx")
        loss_model: "iid" 或 "burst" (Gilbert-Elliott)
        burst_config: burst 模型参数

    Returns:
        PhysicalResult with counts and rates
    """
    experiment = HardwareExperiment(config)

    rng = DeterministicRNG(seed)

    # 连接（Loopback 模式使用 p_loss=0, p_reorder=0，丢包由 LossyTransport 注入）
    if not experiment.connect(loopback=loopback, p_loss=0.0, p_reorder=0.0, rng=rng):
        raise RuntimeError("连接失败")

    # 如果需要受控丢包注入，包装传输层
    loss_stats = None
    if p_loss_inject > 0.0:
        original_transport = experiment.transport
        experiment.transport = LossyTransport(
            inner=original_transport,
            p_loss=p_loss_inject,
            seed=loss_seed,
            direction=loss_direction,
            loss_model=loss_model,
            burst_config=burst_config,
            p_native=p_native,
            loss_rate_mode=loss_rate_mode
        )

    try:
        total_legit_accepted = 0
        total_attack_success = 0
        total_legit_sent = 0
        total_attack_sent = 0

        for run_id in range(1, num_runs + 1):
            result = experiment.run_single_experiment(
                mode=mode,
                window_size=window_size,
                run_id=run_id,
                rng=rng
            )

            # 累计计数 (从 RunResult 获取)
            total_legit_accepted += result.legit_accepted
            total_legit_sent += result.legit_sent
            total_attack_success += result.attack_success
            total_attack_sent += result.attack_sent

        # 获取丢包统计
        if p_loss_inject > 0.0 and hasattr(experiment.transport, 'get_stats'):
            loss_stats = experiment.transport.get_stats()

        avg_lar = total_legit_accepted / total_legit_sent if total_legit_sent > 0 else 0
        avg_asr = total_attack_success / total_attack_sent if total_attack_sent > 0 else 0

        return PhysicalResult(
            avg_lar=avg_lar,
            avg_asr=avg_asr,
            total_legit_accepted=total_legit_accepted,
            total_legit_sent=total_legit_sent,
            total_attack_success=total_attack_success,
            total_attack_sent=total_attack_sent,
            loss_stats=loss_stats
        )

    finally:
        experiment.disconnect()


# =============================================================================
# P1-2: 链路自检模式
# =============================================================================

def run_link_selftest(
    config: Dict[str, Any],
    loopback: bool = True,
    num_frames: int = 100,
    seed: int = 42
) -> Tuple[bool, Dict[str, Any]]:
    """
    链路自检 - 验证 FSK 物理链路闭环 (A2 前置检查)

    在理想条件（p_loss=0）下发送一组帧，验证链路丢包率是否符合预期。

    Args:
        config: 实验配置
        loopback: 是否使用 loopback 模式
        num_frames: 测试帧数
        seed: 随机种子

    Returns:
        (passed, stats): 是否通过和统计信息
    """
    print("\n" + "=" * 60)
    print("链路自检 (Link Self-Test)")
    print("=" * 60)
    print(f"模式: {'Loopback' if loopback else 'Hardware (FSK)'}")
    print(f"测试帧数: {num_frames}")

    experiment = HardwareExperiment(config)
    rng = DeterministicRNG(seed)

    if not experiment.connect(loopback=loopback, p_loss=0.0, p_reorder=0.0, rng=rng):
        print("❌ 连接失败")
        return False, {"error": "connection_failed"}

    try:
        # 使用 no_def 模式，仅测试链路
        result = experiment.run_single_experiment(
            mode=Mode.NO_DEFENSE,
            window_size=1,
            run_id=1,
            rng=rng,
            num_legit_override=num_frames,
            num_attack_override=0  # 不测试攻击
        )

        received = result.legit_accepted
        loss_rate = 1 - (received / num_frames) if num_frames > 0 else 0

        # 计算 Wilson CI
        lar_ci = wilson_ci(received, num_frames)

        stats = {
            "frames_sent": num_frames,
            "frames_received": received,
            "loss_rate": loss_rate,
            "lar": received / num_frames if num_frames > 0 else 0,
            "lar_ci_95": lar_ci,
            "mode": "loopback" if loopback else "hardware"
        }

        print(f"\n结果:")
        print(f"  发送: {num_frames} 帧")
        print(f"  接收: {received} 帧")
        print(f"  LAR: {stats['lar']:.2%} [{lar_ci[0]:.2%}, {lar_ci[1]:.2%}]")
        print(f"  丢包率: {loss_rate:.2%}")

        # 判断标准
        if loopback:
            # Loopback 模式应该 100% 接收
            passed = received == num_frames
            threshold_msg = "Loopback 应 100% 接收"
        else:
            # Hardware 模式允许少量丢包 (< 5%)
            passed = loss_rate < 0.05
            threshold_msg = "Hardware 允许 < 5% 丢包"

        if passed:
            print(f"\n✓ 链路自检通过 ({threshold_msg})")
        else:
            print(f"\n✗ 链路自检失败 ({threshold_msg})")
            if not loopback:
                print("  可能原因:")
                print("    - 同轴连接问题")
                print("    - 衰减不足或过大")
                print("    - 频率偏移")
                print("    - 增益设置不当")

        return passed, stats

    finally:
        experiment.disconnect()


def run_validation(
    config: Dict[str, Any],
    modes: List[str],
    window_sizes: List[int],
    num_runs: int,
    loopback: bool = True,
    seed: int = 42,
    loss_samples: List[float] = None,
    loss_direction: str = "rx",
    loss_model: str = "iid",
    burst_config: Optional[Dict[str, float]] = None,
    p_native: float = 0.0,
    loss_rate_mode: str = "inject",
    attacker_record_loss: float = 0.0
) -> List[ValidationResult]:
    """
    运行完整验证实验

    Args:
        loss_samples: 受控丢包采样点列表，例如 [0.0, 0.1, 0.2]
                      默认为 [0.0]（仅理想点验证，目标 A）
        loss_model: "iid" 或 "burst" (Gilbert-Elliott)
        burst_config: burst 模型参数
    """
    if loss_samples is None:
        loss_samples = [0.0]

    results = []

    # 从配置获取参数
    num_legit = config["traffic"]["num_legit_frames"]
    num_attack = config["traffic"]["num_replay_attempts"]

    for p_loss in loss_samples:
        loss_seed = seed + int(p_loss * 1000)  # 每个采样点使用不同种子

        for mode_str in modes:
            mode = Mode(mode_str)
            test_window_sizes = window_sizes if mode == Mode.WINDOW else [1]

            for ws in test_window_sizes:
                print(f"\n{'='*60}")
                print(f"验证: mode={mode_str}, window_size={ws}, p_loss={p_loss:.1%}")
                if loss_model == "burst":
                    print(f"      丢包模型: Gilbert-Elliott (突发)")
                print(f"{'='*60}")

                # 1. 运行物理实验（带受控丢包注入）
                print(f"\n[1/2] 运行物理实验 (p_loss_inject={p_loss:.1%})...")
                phys_result = run_physical_experiment(
                    config=config,
                    mode=mode,
                    window_size=ws,
                    num_runs=num_runs,
                    loopback=loopback,
                    seed=seed,
                    p_loss_inject=p_loss,
                    loss_seed=loss_seed,
                    loss_direction=loss_direction,
                    loss_model=loss_model,
                    burst_config=burst_config,
                    p_native=p_native,
                    loss_rate_mode=loss_rate_mode
                )

                # P1-1: 计算 Wilson CI
                phys_lar_ci = wilson_ci(phys_result.total_legit_accepted, phys_result.total_legit_sent)
                phys_asr_ci = wilson_ci(phys_result.total_attack_success, phys_result.total_attack_sent)

                print(f"  实测: LAR={phys_result.avg_lar:.2%} [{phys_lar_ci[0]:.2%}, {phys_lar_ci[1]:.2%}]")
                print(f"        ASR={phys_result.avg_asr:.2%} [{phys_asr_ci[0]:.2%}, {phys_asr_ci[1]:.2%}]")
                if phys_result.loss_stats:
                    print(f"  丢包统计: 注入{phys_result.loss_stats['injected_loss_count']}帧, "
                          f"实际丢包率={phys_result.loss_stats['actual_loss_rate']:.2%}")

                # 2. 运行模拟实验（相同 p_loss，p_reorder=0）
                print(f"\n[2/2] 运行模拟实验 (p_loss={p_loss:.1%}, p_reorder=0)...")
                sim_result = run_simulation(
                    mode=mode,
                    window_size=ws,
                    num_runs=num_runs,
                    num_legit=num_legit,
                    num_attack=num_attack,
                    p_loss=p_loss,
                    p_reorder=0.0,
                    seed=seed,
                    attacker_record_loss=attacker_record_loss,
                    attack_mode=AttackMode(config["attack"]["mode"]),
                    inline_attack_probability=config["attack"]["inline_probability"],
                    inline_attack_burst=config["attack"]["inline_burst"],
                    challenge_nonce_bits=config["protocol"]["nonce_bits"],
                    shared_key=config["protocol"]["shared_key"],
                    mac_length=config["protocol"]["mac_length"],
                    command_set=config["traffic"]["commands"],
                )

                # P1-1: 计算 Wilson CI
                sim_lar_ci = wilson_ci(sim_result.total_legit_accepted, sim_result.total_legit_sent)
                sim_asr_ci = wilson_ci(sim_result.total_attack_success, sim_result.total_attack_sent)

                print(f"  模拟: LAR={sim_result.avg_lar:.2%} [{sim_lar_ci[0]:.2%}, {sim_lar_ci[1]:.2%}]")
                print(f"        ASR={sim_result.avg_asr:.2%} [{sim_asr_ci[0]:.2%}, {sim_asr_ci[1]:.2%}]")

                # 3. P1-1: 基于 CI 重叠判断一致性
                lar_overlap = ci_overlap(phys_lar_ci, sim_lar_ci)
                asr_overlap = ci_overlap(phys_asr_ci, sim_asr_ci)

                # 计算传统误差（保留兼容性）
                lar_error = abs(phys_result.avg_lar - sim_result.avg_lar) / max(sim_result.avg_lar, 0.001)
                asr_error = abs(phys_result.avg_asr - sim_result.avg_asr) / max(sim_result.avg_asr, 0.001) if sim_result.avg_asr > 0.001 else 0

                # ASR 特殊处理：如果两者都接近0，认为是匹配的
                if phys_result.avg_asr < 0.01 and sim_result.avg_asr < 0.01:
                    asr_error = 0
                    asr_overlap = True

                # P1-1: 验证通过条件 = CI 重叠 OR 误差 < 10%
                lar_valid = lar_overlap or lar_error < 0.10
                asr_valid = asr_overlap or asr_error < 0.10

                print(f"\n  对比结果 (P1-1 Wilson CI):")
                print(f"    LAR: CI重叠={'✓' if lar_overlap else '✗'}, 误差={lar_error:.1%} → {'✓' if lar_valid else '✗'}")
                print(f"    ASR: CI重叠={'✓' if asr_overlap else '✗'}, 误差={asr_error:.1%} → {'✓' if asr_valid else '✗'}")

                results.append(ValidationResult(
                    mode=mode_str,
                    window_size=ws,
                    p_loss_injected=p_loss,
                    loss_seed=loss_seed,
                    physical_lar=phys_result.avg_lar,
                    physical_asr=phys_result.avg_asr,
                    physical_runs=num_runs,
                    physical_legit_accepted=phys_result.total_legit_accepted,
                    physical_legit_total=phys_result.total_legit_sent,
                    physical_attack_success=phys_result.total_attack_success,
                    physical_attack_total=phys_result.total_attack_sent,
                    sim_lar=sim_result.avg_lar,
                    sim_asr=sim_result.avg_asr,
                    sim_runs=num_runs,
                    sim_legit_accepted=sim_result.total_legit_accepted,
                    sim_legit_total=sim_result.total_legit_sent,
                    sim_attack_success=sim_result.total_attack_success,
                    sim_attack_total=sim_result.total_attack_sent,
                    lar_error=lar_error,
                    asr_error=asr_error,
                    lar_valid=lar_valid,
                    asr_valid=asr_valid,
                    physical_lar_ci=phys_lar_ci,
                    physical_asr_ci=phys_asr_ci,
                    sim_lar_ci=sim_lar_ci,
                    sim_asr_ci=sim_asr_ci,
                    lar_ci_overlap=lar_overlap,
                    asr_ci_overlap=asr_overlap,
                    loss_stats=phys_result.loss_stats
                ))

    return results


def print_summary(results: List[ValidationResult]):
    """打印汇总表格"""
    print("\n")
    print("=" * 90)
    print("验证结果汇总")
    print("=" * 90)
    print()
    print(f"{'Mode':<12} {'Window':<8} {'p_loss':<8} {'实测LAR':<10} {'模拟LAR':<10} {'误差':<8} {'结果':<6}")
    print("-" * 90)

    all_valid = True
    for r in results:
        status = "✓" if (r.lar_valid and r.asr_valid) else "✗"
        if not (r.lar_valid and r.asr_valid):
            all_valid = False

        print(f"{r.mode:<12} {r.window_size:<8} {r.p_loss_injected:<8.1%} {r.physical_lar:<10.2%} {r.sim_lar:<10.2%} {r.lar_error:<8.1%} {status:<6}")

    print("-" * 90)
    print()

    if all_valid:
        print("结论: 所有配置验证通过 ✓")
        print("      实测与 sim 统计一致，验证 counting rules/状态机一致性。")
        print("      A2（FSK 链路）需 hardware/coax 另验。")
    else:
        print("结论: 部分配置验证失败 ✗")
        print("      请检查失败项的原因。")

    print()
    print("=" * 90)
    print("结论强度说明")
    print("=" * 90)
    print("""
本验证仅证明：
  (A1) 防御逻辑与统计口径一致（loopback 可覆盖）
  (A2) FSK 物理链路闭环（仅 hardware/coax 覆盖）
  (B) 在人为注入的 i.i.d 丢包采样点上，统计结果与仿真一致

本验证不证明：
  - 模型在全参数空间有效
  - p_reorder 维度的有效性（本实验未覆盖）
  - 现实无线环境下的最优窗口选择
""")
    print()


def evaluate_goal_criteria(
    results: List[ValidationResult],
    lar_min: float = 0.90,
    no_def_asr_min: float = 0.70,
    defended_asr_max: float = 0.10,
    target_loss: float = 0.0
) -> Dict[str, Any]:
    """
    目标验收: 防御逻辑一致性 + FSK/链路可用性前提下的行为期望 + 仿真对照一致性。

    说明:
      - 该检查面向 p_loss=0 的理想点（A1/A2 主验收点）。
      - 一致性复用 lar_valid/asr_valid（Wilson CI 重叠或误差阈值通过）。
    """
    tol = 1e-9
    target_results = [r for r in results if abs(r.p_loss_injected - target_loss) <= tol]

    summary: Dict[str, Any] = {
        "target_loss": target_loss,
        "lar_min": lar_min,
        "no_def_asr_min": no_def_asr_min,
        "defended_asr_max": defended_asr_max,
        "passed": False,
        "reason": "",
        "modes": {},
        "ordering_check_passed": False,
    }

    if not target_results:
        summary["reason"] = f"未找到 p_loss={target_loss:.1%} 的验证结果"
        return summary

    grouped: Dict[str, List[ValidationResult]] = {}
    for item in target_results:
        grouped.setdefault(item.mode, []).append(item)

    required_modes = {"no_def", "rolling", "window", "challenge"}
    missing = sorted(required_modes - set(grouped.keys()))
    if missing:
        summary["reason"] = f"缺少必要模式结果: {', '.join(missing)}"
        return summary

    no_def_asr_floor = 0.0
    defended_asr_ceiling_values: List[float] = []
    all_modes_passed = True

    for mode in sorted(required_modes):
        mode_items = grouped[mode]
        lar_values = [x.physical_lar for x in mode_items]
        asr_values = [x.physical_asr for x in mode_items]
        cmp_pass = all(x.lar_valid and x.asr_valid for x in mode_items)

        lar_mean = statistics.mean(lar_values)
        asr_mean = statistics.mean(asr_values)
        lar_min_observed = min(lar_values)
        asr_max_observed = max(asr_values)

        if mode == "no_def":
            behavior_pass = all(x >= no_def_asr_min for x in asr_values)
            no_def_asr_floor = min(asr_values)
        else:
            behavior_pass = all(x <= defended_asr_max for x in asr_values)
            defended_asr_ceiling_values.append(asr_max_observed)

        lar_pass = all(x >= lar_min for x in lar_values)
        mode_pass = cmp_pass and behavior_pass and lar_pass
        all_modes_passed = all_modes_passed and mode_pass

        summary["modes"][mode] = {
            "samples": len(mode_items),
            "physical_lar_mean": lar_mean,
            "physical_asr_mean": asr_mean,
            "physical_lar_min": lar_min_observed,
            "physical_asr_max": asr_max_observed,
            "comparison_passed": cmp_pass,
            "lar_passed": lar_pass,
            "behavior_passed": behavior_pass,
            "passed": mode_pass,
        }

    if defended_asr_ceiling_values:
        # 额外行为约束：无防御 ASR 下界应高于任意防御模式 ASR 上界
        summary["ordering_check_passed"] = no_def_asr_floor > max(defended_asr_ceiling_values)
    else:
        summary["ordering_check_passed"] = False

    summary["passed"] = all_modes_passed and summary["ordering_check_passed"]
    if summary["passed"]:
        summary["reason"] = "目标验收通过"
    else:
        summary["reason"] = "存在模式未达标或 no_def/defended 行为排序不成立"
    return summary


def print_goal_assessment(goal: Dict[str, Any]) -> None:
    """打印目标验收摘要。"""
    print("\n" + "=" * 90)
    print("目标验收 (防御逻辑一致性 + FSK链路可运行 + 仿真对照)")
    print("=" * 90)
    print(f"验收点: p_loss={goal.get('target_loss', 0.0):.1%}")
    print(f"阈值: LAR≥{goal.get('lar_min', 0.0):.0%}, "
          f"no_def ASR≥{goal.get('no_def_asr_min', 0.0):.0%}, "
          f"defended ASR≤{goal.get('defended_asr_max', 0.0):.0%}")

    if not goal.get("modes"):
        print(f"结果: ✗ {goal.get('reason', '无可用结果')}")
        return

    for mode in ["no_def", "rolling", "window", "challenge"]:
        item = goal["modes"].get(mode)
        if not item:
            continue
        status = "✓" if item["passed"] else "✗"
        print(
            f"{status} {mode:<10} LAR={item['physical_lar_mean']:.2%}, "
            f"ASR={item['physical_asr_mean']:.2%}, "
            f"CI对照={'✓' if item['comparison_passed'] else '✗'}"
        )

    ordering = "✓" if goal.get("ordering_check_passed") else "✗"
    print(f"{ordering} no_def ASR > defended ASR（行为排序检查）")
    print(f"{'✓' if goal.get('passed') else '✗'} 总结: {goal.get('reason', '')}")


def save_results(
    results: List[ValidationResult],
    output_path: Path,
    config: Dict[str, Any] = None,
    goal_validation: Optional[Dict[str, Any]] = None
):
    """保存结果到 JSON（包含完整元数据以保证可复现性）"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 统计口径说明
    counting_rules = {
        "legit_accept": "合法帧被 Receiver.process() 接受",
        "legit_reject": "合法帧被 MAC/计数器/nonce 验证拒绝",
        "legit_loss": "合法帧未到达 Receiver（含：信道丢失、CRC失败、同步失败、受控丢包注入）",
        "attack_success": "攻击帧被 Receiver.process() 接受",
        "attack_reject": "攻击帧被 MAC/计数器/nonce 验证拒绝",
        "attack_loss": "攻击帧未到达 Receiver（同上）",
        "note": "CRC失败、同步失败在 physical 侧计为 loss，与 sim 的 p_loss 语义对齐"
    }

    # 结论强度说明
    conclusion_scope = {
        "validates": [
            "(A1) 防御逻辑与统计口径一致（loopback 可覆盖）",
            "(A2) FSK 物理链路闭环（仅 hardware/coax 覆盖）",
            "(B) 在人为注入的 i.i.d 丢包采样点上，统计结果与仿真一致"
        ],
        "does_not_validate": [
            "模型在全参数空间有效",
            "p_reorder 维度的有效性（本实验未覆盖）",
            "现实无线环境下的最优窗口选择"
        ]
    }

    data = {
        "validation_time": datetime.now().isoformat(),
        "environment": get_environment_snapshot(),
        "counting_rules": counting_rules,
        "conclusion_scope": conclusion_scope,
        "summary": {
            "total_configs": len(results),
            "passed": sum(1 for r in results if r.lar_valid and r.asr_valid),
            "failed": sum(1 for r in results if not (r.lar_valid and r.asr_valid)),
            "loss_samples_tested": sorted(set(r.p_loss_injected for r in results))
        },
        "results": [asdict(r) for r in results]
    }

    if config:
        data["config"] = config
    if goal_validation is not None:
        data["goal_validation"] = goal_validation

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"结果已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="物理对照实验 - 验证模拟实验有效性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Loopback 测试（无需硬件）- 目标 A
  python run_validation.py --loopback

  # 快速测试
  python run_validation.py --quick --loopback

  # 真实硬件实验
  python run_validation.py

  # 只测试特定模式
  python run_validation.py --modes window rolling --loopback

  # 受控丢包采样验证 - 目标 B
  python run_validation.py --loopback --loss-samples 0,0.1,0.2

  # 完整验证 (A + B)
  python run_validation.py --loopback --loss-samples 0,0.1,0.2 --runs 10

  # P1-2: 链路自检（A2 前置检查）
  python run_validation.py --link-selftest --loopback
  python run_validation.py --link-selftest  # 硬件模式

  # P1-3: 突发丢包敏感性测试 (Gilbert-Elliott)
  python run_validation.py --loopback --loss-samples 0.1 --loss-model burst

结论强度说明:
  本验证仅证明:
    (A) 理想链路（p_loss≈0）下，实机链路与仿真一致
    (B) 在受控丢包采样点上，统计结果与仿真一致
  本验证不证明:
    - 模型在全参数空间有效
    - p_reorder 维度的有效性
    - 现实无线环境下的最优窗口选择
"""
    )

    parser.add_argument("--loopback", action="store_true",
                        help="Loopback 模式（无需硬件）")
    parser.add_argument("--modes", nargs="+",
                        default=["no_def", "rolling", "window", "challenge"],
                        help="要测试的防御模式")
    parser.add_argument("--window-sizes", nargs="+", type=int,
                        default=[5],
                        help="Window 模式的窗口大小")
    parser.add_argument("--runs", type=int, default=10,
                        help="每个配置的运行次数")
    parser.add_argument("--quick", action="store_true",
                        help="快速测试模式（减少运行次数）")
    parser.add_argument("--output", type=str, default=None,
                        help="结果输出路径")
    parser.add_argument("--tx-port", type=int, default=None,
                        help="覆盖配置中的 ZMQ TX 端口")
    parser.add_argument("--rx-port", type=int, default=None,
                        help="覆盖配置中的 ZMQ RX 端口")

    # P1-2: 链路自检
    parser.add_argument("--link-selftest", action="store_true",
                        help="运行链路自检（A2 前置检查）")
    parser.add_argument("--selftest-frames", type=int, default=100,
                        help="自检帧数（默认 100）")

    # 受控丢包采样参数 (目标 B)
    parser.add_argument("--loss-samples", type=str, default="0",
                        help="受控丢包采样点，逗号分隔 (例如: 0,0.1,0.2)")
    parser.add_argument("--loss-direction", type=str, default="rx",
                        choices=["rx", "tx"],
                        help="丢包注入位置 (rx=接收后丢弃, tx=发送前丢弃)")

    # P1-3: 丢包模型选择
    parser.add_argument("--loss-model", type=str, default="iid",
                        choices=["iid", "burst"],
                        help="丢包模型: iid (独立同分布) 或 burst (Gilbert-Elliott 突发)")
    parser.add_argument("--burst-p-good", type=float, default=0.01,
                        help="突发模型: Good 状态丢包率 (默认 0.01)")
    parser.add_argument("--burst-p-bad", type=float, default=0.5,
                        help="突发模型: Bad 状态丢包率 (默认 0.5)")
    parser.add_argument("--burst-g2b", type=float, default=0.05,
                        help="突发模型: Good→Bad 转移概率 (默认 0.05)")
    parser.add_argument("--burst-b2g", type=float, default=0.3,
                        help="突发模型: Bad→Good 转移概率 (默认 0.3)")

    # 丢包率模式 (target 模式)
    parser.add_argument("--loss-rate-mode", type=str, default="inject",
                        choices=["inject", "target"],
                        help="丢包率模式: inject (直接注入) 或 target (目标总丢包率)")
    parser.add_argument("--p-native", type=float, default=0.0,
                        help="原生丢包率 (用于 target 模式计算注入率，可通过 --link-selftest 估计)")

    # Attacker 观察模型参数
    parser.add_argument("--attacker-record-loss", type=float, default=0.0,
                        help="Attacker 记录丢失率 (攻击者未能观察到帧的概率)")
    parser.add_argument("--goal-check", action="store_true",
                        help="启用三目标验收门槛并以通过/失败返回退出码")
    parser.add_argument("--goal-lar-min", type=float, default=0.90,
                        help="目标验收: 各模式最低 LAR 阈值")
    parser.add_argument("--goal-no-def-asr-min", type=float, default=0.70,
                        help="目标验收: no_def 模式最低 ASR 阈值")
    parser.add_argument("--goal-defended-asr-max", type=float, default=0.10,
                        help="目标验收: 防御模式最高 ASR 阈值")

    args = parser.parse_args()

    # 解析丢包采样点
    loss_samples = [float(x.strip()) for x in args.loss_samples.split(",")]
    for p in loss_samples:
        if p < 0.0 or p > 1.0:
            parser.error(f"--loss-samples 包含非法值 {p}，应在 [0,1] 范围内")

    # 加载配置
    config = load_config()
    if args.tx_port is not None:
        config.setdefault("zmq", {})["tx_port"] = args.tx_port
    if args.rx_port is not None:
        config.setdefault("zmq", {})["rx_port"] = args.rx_port

    # 快速模式
    if args.quick:
        # 仅在未显式传 --runs 时应用 quick 默认值，避免覆盖用户输入。
        if args.runs == parser.get_default("runs"):
            args.runs = 3
        config["traffic"]["num_legit_frames"] = 20
        config["traffic"]["num_replay_attempts"] = 50

    # P1-2: 链路自检模式
    if args.link_selftest:
        print("=" * 60)
        print("P1-2: 链路自检模式")
        print("=" * 60)

        passed, stats = run_link_selftest(
            config=config,
            loopback=args.loopback,
            num_frames=args.selftest_frames,
            seed=config["experiment"]["random_seed"]
        )

        # 保存自检结果
        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = PROJECT_ROOT / f"physical_experiment/results/selftest_{timestamp}.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "test_type": "link_selftest",
                "passed": passed,
                "stats": stats,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存: {output_path}")

        sys.exit(0 if passed else 1)

    # P1-3: 构建 burst 配置
    burst_config = None
    if args.loss_model == "burst":
        burst_config = {
            "p_loss_good": args.burst_p_good,
            "p_loss_bad": args.burst_p_bad,
            "p_good_to_bad": args.burst_g2b,
            "p_bad_to_good": args.burst_b2g
        }

    print("=" * 60)
    print("物理对照实验 - 验证模拟实验有效性")
    print("=" * 60)
    print(f"模式: {'Loopback (无硬件)' if args.loopback else '真实硬件'}")
    print(f"防御模式: {args.modes}")
    print(f"窗口大小: {args.window_sizes}")
    print(f"运行次数: {args.runs}")
    print(f"丢包采样点: {loss_samples}")
    print(f"丢包注入位置: {args.loss_direction}")
    print(f"丢包模型: {args.loss_model}" + (f" (Gilbert-Elliott)" if args.loss_model == "burst" else " (i.i.d.)"))
    print(f"信道条件: p_reorder=0 (本实验不验证乱序维度)")
    print(f"统计方法: Wilson CI (95% 置信区间)")

    # 运行验证
    results = run_validation(
        config=config,
        modes=args.modes,
        window_sizes=args.window_sizes,
        num_runs=args.runs,
        loopback=args.loopback,
        seed=config["experiment"]["random_seed"],
        loss_samples=loss_samples,
        loss_direction=args.loss_direction,
        loss_model=args.loss_model,
        burst_config=burst_config,
        p_native=args.p_native,
        loss_rate_mode=args.loss_rate_mode,
        attacker_record_loss=args.attacker_record_loss
    )

    # 打印汇总
    print_summary(results)

    goal_summary = None
    if args.goal_check:
        goal_summary = evaluate_goal_criteria(
            results,
            lar_min=args.goal_lar_min,
            no_def_asr_min=args.goal_no_def_asr_min,
            defended_asr_max=args.goal_defended_asr_max,
            target_loss=0.0
        )
        print_goal_assessment(goal_summary)

    # 保存结果
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = PROJECT_ROOT / f"physical_experiment/results/validation_{timestamp}.json"

    save_results(results, output_path, config, goal_validation=goal_summary)

    if args.goal_check and goal_summary is not None and not goal_summary.get("passed", False):
        sys.exit(2)


if __name__ == "__main__":
    main()
