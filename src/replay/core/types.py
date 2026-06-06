"""Typed data structures shared across the simulation package."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    """Supported receiver protection modes."""

    NO_DEFENSE = "no_def"
    ROLLING_MAC = "rolling"
    WINDOW = "window"
    CHALLENGE = "challenge"
    HSW_CR = "hsw_cr"
    OSCORE_LIKE = "oscore_like"


class AttackMode(str, Enum):
    """How the attacker schedules replay attempts."""

    POST_RUN = "post"
    INLINE = "inline"


@dataclass
class Frame:
    """Simplified abstraction of an RF control frame."""

    command: str
    counter: int | None = None
    mac: str | None = None
    nonce: str | None = None
    is_attack: bool = False
    # HSW-CR 扩展（研究计划 §3.3）
    dev_id: int = 0
    key_id: int = 0
    epoch: int = 0
    flags: int = 0
    payload: bytes = b""

    def clone(self) -> Frame:
        return Frame(
            command=self.command,
            counter=self.counter,
            mac=self.mac,
            nonce=self.nonce,
            is_attack=self.is_attack,
            dev_id=self.dev_id,
            key_id=self.key_id,
            epoch=self.epoch,
            flags=self.flags,
            payload=self.payload,
        )


@dataclass
class ReceiverState:
    """Mutable state that the receiver persists across frames."""

    last_counter: int = -1
    expected_nonce: str | None = None
    received_mask: int = 0
    outstanding_nonces: dict[str, int] = field(default_factory=dict)
    used_nonces: set[str] = field(default_factory=set)


@dataclass
class SimulationConfig:
    """Configuration bundle for a single simulation scenario."""

    mode: Mode
    attack_mode: AttackMode = AttackMode.POST_RUN
    num_legit: int = 20
    num_replay: int = 100
    p_loss: float = 0.0
    p_reorder: float = 0.0
    window_size: int = 0
    command_sequence: Sequence[str] | None = None
    command_set: Sequence[str] | None = None
    target_commands: Sequence[str] | None = None
    rng_seed: int | None = None
    mac_length: int = 8
    shared_key: str = "sim_shared_key"
    attacker_record_loss: float = 0.0
    inline_attack_probability: float = 0.3
    inline_attack_burst: int = 1
    challenge_nonce_bits: int = 32
    max_outstanding_challenges: int = 32
    challenge_ttl_ticks: int = 100
    channel_model: str = "iid"
    burst_p_good_to_bad: float = 0.05
    burst_p_bad_to_good: float = 0.30
    loss_good: float = 0.01
    loss_bad: float = 0.60
    loss_trace: Sequence[bool] | None = None
    paired: bool = False
    target_ci_half_width: float | None = None
    max_runs: int = 2000
    command_risk: dict[str, float] | None = None
    risk_high: float = 0.8
    auth_profile: str = "hmac"
    mac_tag_bits: int = 80

    def effective_command_set(self) -> Sequence[str]:
        from .commands import DEFAULT_COMMANDS

        if self.command_set:
            return self.command_set
        return DEFAULT_COMMANDS


@dataclass
class SimulationRunResult:
    """Counters produced by a single Monte Carlo run."""

    legit_sent: int
    legit_accepted: int
    attack_attempts: int
    attack_success: int
    mode: Mode
    frr: float = 0.0
    energy_proxy: float = 0.0
    bytes_overhead: float = 0.0
    state_bytes: float = 0.0
    latency_ticks: float = 0.0
    crypto_ops: float = 0.0
    challenge_round_trips: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def legit_accept_rate(self) -> float:
        return self._safe_div(self.legit_accepted, self.legit_sent)

    @property
    def attack_success_rate(self) -> float:
        return self._safe_div(self.attack_success, self.attack_attempts)

    @staticmethod
    def _safe_div(num: int, denom: int) -> float:
        if denom == 0:
            return 0.0
        return num / denom


@dataclass
class AggregateStats:
    """Aggregated statistics over many runs for a single mode."""

    mode: Mode
    runs: int
    avg_legit_rate: float
    std_legit_rate: float
    avg_attack_rate: float
    std_attack_rate: float
    p_loss: float
    p_reorder: float
    window_size: int
    num_legit: int
    num_replay: int
    attack_mode: AttackMode
    legit_accepted: int = 0
    legit_total: int = 0
    attack_accepted: int = 0
    attack_total: int = 0
    lar_ci_low: float = 0.0
    lar_ci_high: float = 0.0
    asr_ci_low: float = 0.0
    asr_ci_high: float = 0.0
    frr: float = 0.0
    energy_proxy: float = 0.0
    bytes_overhead: float = 0.0
    state_bytes: float = 0.0
    latency_ticks: float = 0.0
    crypto_ops: float = 0.0
    challenge_round_trips: float = 0.0
    mac_tag_bits: int = 80
    auth_profile: str = "hmac"
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "mode": self.mode.value,
            "runs": self.runs,
            "avg_legit_rate": self.avg_legit_rate,
            "std_legit_rate": self.std_legit_rate,
            "avg_attack_rate": self.avg_attack_rate,
            "std_attack_rate": self.std_attack_rate,
            "p_loss": self.p_loss,
            "p_reorder": self.p_reorder,
            "window_size": self.window_size,
            "num_legit": self.num_legit,
            "num_replay": self.num_replay,
            "attack_mode": self.attack_mode.value,
            "legit_accepted": self.legit_accepted,
            "legit_total": self.legit_total,
            "attack_accepted": self.attack_accepted,
            "attack_total": self.attack_total,
            "lar_ci_low": self.lar_ci_low,
            "lar_ci_high": self.lar_ci_high,
            "asr_ci_low": self.asr_ci_low,
            "asr_ci_high": self.asr_ci_high,
            "frr": self.frr,
            "energy_proxy": self.energy_proxy,
            "bytes_overhead": self.bytes_overhead,
            "state_bytes": self.state_bytes,
            "latency_ticks": self.latency_ticks,
            "crypto_ops": self.crypto_ops,
            "challenge_round_trips": self.challenge_round_trips,
            "mac_tag_bits": self.mac_tag_bits,
            "auth_profile": self.auth_profile,
        }
        if self.metadata:
            result.update(self.metadata)
        return result
