"""Typed data structures shared across the simulation package."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class Mode(str, Enum):
    """Supported receiver protection modes."""

    NO_DEFENSE = "no_def"
    ROLLING_MAC = "rolling"
    WINDOW = "window"
    CHALLENGE = "challenge"


class AttackMode(str, Enum):
    """How the attacker schedules replay attempts."""

    POST_RUN = "post"
    INLINE = "inline"


@dataclass
class Frame:
    """Simplified abstraction of an RF control frame."""

    command: str
    counter: Optional[int] = None
    mac: Optional[str] = None
    nonce: Optional[str] = None
    is_attack: bool = False  # Metadata to track source (not transmitted over air, but useful for sim)

    def clone(self) -> "Frame":
        return Frame(
            command=self.command,
            counter=self.counter,
            mac=self.mac,
            nonce=self.nonce,
            is_attack=self.is_attack,
        )


@dataclass
class ReceiverState:
    """Mutable state that the receiver persists across frames."""

    last_counter: int = -1
    expected_nonce: Optional[str] = None
    # Bitmask for sliding window: bit 0 is last_counter, bit 1 is last_counter-1, etc.
    received_mask: int = 0


@dataclass
class SimulationConfig:
    """Configuration bundle for a single simulation scenario."""

    mode: Mode
    attack_mode: AttackMode = AttackMode.POST_RUN
    num_legit: int = 20
    num_replay: int = 100
    p_loss: float = 0.0
    p_reorder: float = 0.0  # Probability of packet reordering
    window_size: int = 0
    command_sequence: Optional[Sequence[str]] = None
    command_set: Optional[Sequence[str]] = None
    target_commands: Optional[Sequence[str]] = None  # For selective replay
    rng_seed: Optional[int] = None
    mac_length: int = 8
    shared_key: str = "sim_shared_key"
    attacker_record_loss: float = 0.0
    inline_attack_probability: float = 0.3
    inline_attack_burst: int = 1
    challenge_nonce_bits: int = 32

    def effective_command_set(self) -> Sequence[str]:
        from .commands import DEFAULT_COMMANDS  # lazy import to avoid cycles

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
    metadata: Dict[str, float | str] = field(default_factory=dict)

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
    metadata: Dict[str, float | int] = field(default_factory=dict)  # For performance metrics

    def as_dict(self) -> Dict[str, float | int | str]:
        result = {
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
        }
        if self.metadata:
            result.update(self.metadata)
        return result
