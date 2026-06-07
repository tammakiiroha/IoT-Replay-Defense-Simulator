"""Pre-generated scenario traces for paired common-random-number experiments."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from .rng import DeterministicRNG, RandomLike
from .types import SimulationConfig


@dataclass(frozen=True)
class ScenarioTrace:
    commands: list[str]
    legit_dropped: list[bool]
    legit_delay: list[int]
    attacker_record_dropped: list[bool]
    inline_attempt: list[bool]
    replay_pick: list[int]
    replay_dropped: list[bool]
    replay_delay: list[int]
    # 反向 resync 信道决策（paired 路径确定性来源；按 resync 尝试序号索引，§4.3）
    resync_challenge_dropped: list[bool] = field(default_factory=list)
    resync_challenge_delay: list[int] = field(default_factory=list)
    resync_confirm_dropped: list[bool] = field(default_factory=list)
    resync_confirm_delay: list[int] = field(default_factory=list)
    # 反向 critical 两阶段信道决策（paired 路径；按 critical 尝试序号索引，§4.4）
    critical_challenge_dropped: list[bool] = field(default_factory=list)
    critical_challenge_delay: list[int] = field(default_factory=list)
    critical_confirm_dropped: list[bool] = field(default_factory=list)
    critical_confirm_delay: list[int] = field(default_factory=list)
    # reboot 后认证重建信道决策（paired 路径；每次运行最多一次 reboot，§8.5）
    reboot_challenge_dropped: list[bool] = field(default_factory=list)
    reboot_challenge_delay: list[int] = field(default_factory=list)
    reboot_confirm_dropped: list[bool] = field(default_factory=list)
    reboot_confirm_delay: list[int] = field(default_factory=list)
    # 攻击专属额外丢弃（weak 强度；按 replay 序号索引，§6 G10）——末尾追加保非 weak 零漂移
    attack_extra_dropped: list[bool] = field(default_factory=list)

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    @property
    def legit_drop_count(self) -> int:
        return sum(1 for dropped in self.legit_dropped if dropped)


def _dropped(rng: RandomLike, probability: float) -> bool:
    return probability > 0.0 and rng.random() < probability


def _delay(rng: RandomLike, probability: float) -> int:
    return rng.randint(1, 3) if _dropped(rng, probability) else 0


def generate_trace(config: SimulationConfig, seed: int) -> ScenarioTrace:
    """Generate channel and attacker-randomness decisions independent of mode RNG."""

    rng = DeterministicRNG(seed)
    command_space = list(config.effective_command_set())
    commands: list[str] = []
    legit_dropped: list[bool] = []
    legit_delay: list[int] = []
    attacker_record_dropped: list[bool] = []

    for index in range(config.num_legit):
        if config.command_sequence:
            command = config.command_sequence[index % len(config.command_sequence)]
        else:
            command = rng.choice(command_space)
        commands.append(command)
        legit_dropped.append(_dropped(rng, config.p_loss))
        legit_delay.append(_delay(rng, config.p_reorder))
        attacker_record_dropped.append(_dropped(rng, config.attacker_record_loss))

    inline_slots = config.num_legit * max(1, config.inline_attack_burst)
    inline_attempt = [
        _dropped(rng, config.inline_attack_probability) for _ in range(inline_slots)
    ]

    replay_pick: list[int] = []
    replay_dropped: list[bool] = []
    replay_delay: list[int] = []
    for _ in range(config.num_replay):
        replay_pick.append(rng.getrandbits(31))
        replay_dropped.append(_dropped(rng, config.p_loss))
        replay_delay.append(_delay(rng, config.p_reorder))

    # 反向 resync 信道决策——必须在所有现有抽取之后（末尾），以免改动既有数组的抽取顺序，
    # 从而保证非 resync 模式 paired 数值逐字节不变（§Phase 1.5 append 技巧）。
    resync_challenge_dropped: list[bool] = []
    resync_challenge_delay: list[int] = []
    resync_confirm_dropped: list[bool] = []
    resync_confirm_delay: list[int] = []
    for _ in range(config.num_legit):
        resync_challenge_dropped.append(_dropped(rng, config.p_loss))
        resync_challenge_delay.append(_delay(rng, config.p_reorder))
        resync_confirm_dropped.append(_dropped(rng, config.p_loss))
        resync_confirm_delay.append(_delay(rng, config.p_reorder))

    # 反向 critical 信道决策——同样追加在所有现有抽取之后（末尾），保持非 critical 模式
    # paired 数值逐字节不变（与 resync 同一 append 技巧，§Phase 3）。
    critical_challenge_dropped: list[bool] = []
    critical_challenge_delay: list[int] = []
    critical_confirm_dropped: list[bool] = []
    critical_confirm_delay: list[int] = []
    reboot_challenge_dropped: list[bool] = []
    reboot_challenge_delay: list[int] = []
    reboot_confirm_dropped: list[bool] = []
    reboot_confirm_delay: list[int] = []
    for _ in range(config.num_legit):
        critical_challenge_dropped.append(_dropped(rng, config.p_loss))
        critical_challenge_delay.append(_delay(rng, config.p_reorder))
        critical_confirm_dropped.append(_dropped(rng, config.p_loss))
        critical_confirm_delay.append(_delay(rng, config.p_reorder))

    # reboot 后认证重建信道决策（每次运行最多一次 reboot，故长度 1；同末尾追加技巧）
    reboot_challenge_dropped.append(_dropped(rng, config.p_loss))
    reboot_challenge_delay.append(_delay(rng, config.p_reorder))
    reboot_confirm_dropped.append(_dropped(rng, config.p_loss))
    reboot_confirm_delay.append(_delay(rng, config.p_reorder))

    # 攻击专属额外丢弃（weak 强度）——在所有现有抽取之后追加，保证非 weak/默认逐字节不变。
    # 概率 0.5：P_deliver^A = 0.5 * (1 - p_loss)，即信道之外再叠一道 attack-only 丢弃。
    attack_extra_dropped = [_dropped(rng, 0.5) for _ in range(config.num_replay)]

    return ScenarioTrace(
        commands=commands,
        legit_dropped=legit_dropped,
        legit_delay=legit_delay,
        attacker_record_dropped=attacker_record_dropped,
        inline_attempt=inline_attempt,
        replay_pick=replay_pick,
        replay_dropped=replay_dropped,
        replay_delay=replay_delay,
        resync_challenge_dropped=resync_challenge_dropped,
        resync_challenge_delay=resync_challenge_delay,
        resync_confirm_dropped=resync_confirm_dropped,
        resync_confirm_delay=resync_confirm_delay,
        critical_challenge_dropped=critical_challenge_dropped,
        critical_challenge_delay=critical_challenge_delay,
        critical_confirm_dropped=critical_confirm_dropped,
        critical_confirm_delay=critical_confirm_delay,
        reboot_challenge_dropped=reboot_challenge_dropped,
        reboot_challenge_delay=reboot_challenge_delay,
        reboot_confirm_dropped=reboot_confirm_dropped,
        reboot_confirm_delay=reboot_confirm_delay,
        attack_extra_dropped=attack_extra_dropped,
    )
