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


@dataclass(frozen=True)
class AttackContext:
    """Defense parameters the engine injects so adaptive strategies can target
    window/resync/critical structure. `RandomReplay` ignores it; adaptive
    strategies (P3) read it. All fields default so it stays optional."""

    window_size: int = 0
    g_hard: int = 0
    last_counter: int = -1
    received_mask: tuple[int, ...] = ()
    policy_table: object | None = None


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


# Legacy name — the historical `Attacker` IS the RandomReplay baseline.
Attacker = RandomReplay


__all__ = ["AttackContext", "AttackerStrategy", "RandomReplay", "Attacker"]
