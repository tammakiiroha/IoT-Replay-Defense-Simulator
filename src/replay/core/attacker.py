"""Attacker model for record-and-replay experiments.

`AttackerStrategy` is the pluggable policy: `RandomReplay` is the baseline (the
historical `Attacker` behaviour, byte-for-byte) and adaptive strategies are added
in Phase 5 P3. Two selection entry points keep both engine paths zero-drift:
- `pick_frame(rng, ...)`   — live path (rng.choice over the strategy's own recording)
- `pick_recorded(raw_pick, recorded, ...)` — paired/trace path (deterministic index)
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .rng import RandomLike
from .types import Frame


class CriticalPolicy(Protocol):
    """Structural type for the receiver policy table — adaptive strategies only
    need to ask whether a command is critical (no bare-object coupling)."""

    def is_critical(self, cmd: str) -> bool: ...


@dataclass(frozen=True)
class AttackContext:
    """Defense parameters the engine injects so adaptive strategies can target
    window/resync/critical structure. `RandomReplay` ignores it; adaptive
    strategies (P3) read it. All fields default so it stays optional."""

    window_size: int = 0
    g_hard: int = 0
    last_counter: int = -1
    received_mask: tuple[int, ...] = ()
    policy_table: CriticalPolicy | None = None


class AttackerStrategy(Protocol):
    """Pluggable frame-selection policy for the attacker."""

    def observe(self, frame: Frame, rng: RandomLike) -> None: ...

    def pick_frame(
        self, rng: RandomLike, *, context: AttackContext | None = None
    ) -> Frame | None: ...

    def pick_recorded(
        self,
        raw_pick: int,
        recorded: Sequence[Frame],
        *,
        context: AttackContext | None = None,
    ) -> Frame | None: ...


class RandomReplay:
    """Baseline strategy: records (with `record_loss`) and replays a uniformly /
    deterministically chosen recorded frame. Byte-identical to the legacy
    `Attacker` on both the live and paired paths (A1 zero-drift)."""

    def __init__(
        self,
        record_loss: float = 0.0,
        target_commands: Sequence[str] | None = None,
    ):
        self.record_loss = record_loss
        self.target_commands = set(target_commands) if target_commands else None
        self._recorded: list[Frame] = []

    def observe(self, frame: Frame, rng: RandomLike) -> None:
        if self.record_loss > 0 and rng.random() < self.record_loss:
            return
        self._recorded.append(frame.clone())

    def pick_frame(
        self, rng: RandomLike, *, context: AttackContext | None = None
    ) -> Frame | None:
        # live path — unchanged legacy logic (context ignored by baseline)
        if not self._recorded:
            return None
        if not self.target_commands:
            return rng.choice(self._recorded).clone()
        candidates = [f for f in self._recorded if f.command in self.target_commands]
        if not candidates:
            return None
        return rng.choice(candidates).clone()

    def pick_recorded(
        self,
        raw_pick: int,
        recorded: Sequence[Frame],
        *,
        context: AttackContext | None = None,
    ) -> Frame | None:
        # paired/trace path — unchanged legacy `pick_replay` logic
        if self.target_commands:
            candidates = [f for f in recorded if f.command in self.target_commands]
        else:
            candidates = list(recorded)
        if not candidates:
            return None
        return candidates[raw_pick % len(candidates)].clone()

    def clear(self) -> None:
        self._recorded.clear()


class AdaptiveReplay(RandomReplay):
    """Adaptive attacker (Phase 5 D4): records like RandomReplay but selects
    frames by an attack-specific policy. Capability boundary (A2): only ever
    picks/reorders ALREADY-RECORDED legitimate frames — never forges any field.

    Modes:
    - adaptive_lostframe: in-window slot that the receiver has NOT yet accepted.
    - adaptive_resync:    recorded NORMAL frame whose counter gap > g_hard
                          (would trigger needs_resync); never fabricates a gap.
    - adaptive_critical:  recorded FLAG_CRIT_PREPARE frame (replay old critical).
    """

    def __init__(
        self,
        mode: str,
        record_loss: float = 0.0,
        target_commands: Sequence[str] | None = None,
    ):
        super().__init__(record_loss, target_commands)
        self.mode = mode

    def pick_frame(
        self, rng: RandomLike, *, context: AttackContext | None = None
    ) -> Frame | None:
        candidates = self._candidates(self._recorded, context)
        if not candidates:
            return None
        return rng.choice(candidates).clone()

    def pick_recorded(
        self,
        raw_pick: int,
        recorded: Sequence[Frame],
        *,
        context: AttackContext | None = None,
    ) -> Frame | None:
        candidates = self._candidates(recorded, context)
        if not candidates:
            return None
        return candidates[raw_pick % len(candidates)].clone()

    def _candidates(
        self, frames: Sequence[Frame], context: AttackContext | None
    ) -> list[Frame]:
        if context is None:
            return []
        if self.mode == "adaptive_critical":
            return [f for f in frames if f.flags == Frame.FLAG_CRIT_PREPARE]
        if self.mode == "adaptive_resync":
            return [f for f in frames if self._is_resync_candidate(f, context)]
        return [f for f in frames if self._is_lostframe_candidate(f, context)]

    @staticmethod
    def _is_lostframe_candidate(frame: Frame, ctx: AttackContext) -> bool:
        if frame.counter is None:
            return False
        offset = ctx.last_counter - frame.counter
        if not (0 <= offset < ctx.window_size):
            return False
        if offset >= len(ctx.received_mask):
            return False
        return ctx.received_mask[offset] == 0

    @staticmethod
    def _is_resync_candidate(frame: Frame, ctx: AttackContext) -> bool:
        if frame.counter is None:
            return False
        if frame.flags == Frame.FLAG_CRIT_PREPARE:
            return False
        if ctx.policy_table is not None and ctx.policy_table.is_critical(frame.command):
            return False
        return frame.counter - ctx.last_counter > ctx.g_hard


# Legacy name — the historical `Attacker` IS the RandomReplay baseline.
Attacker = RandomReplay


__all__ = [
    "AttackContext",
    "AttackerStrategy",
    "CriticalPolicy",
    "RandomReplay",
    "AdaptiveReplay",
    "Attacker",
]
