"""Attacker model for record-and-replay experiments."""
from __future__ import annotations

from collections.abc import Sequence

from .rng import RandomLike
from .types import Frame


class Attacker:
    def __init__(self, record_loss: float = 0.0, target_commands: Sequence[str] | None = None):
        self.record_loss = record_loss
        self.target_commands = set(target_commands) if target_commands else None
        self._recorded: list[Frame] = []

    def observe(self, frame: Frame, rng: RandomLike) -> None:
        if self.record_loss > 0 and rng.random() < self.record_loss:
            return
        self._recorded.append(frame.clone())

    def pick_frame(self, rng: RandomLike) -> Frame | None:
        if not self._recorded:
            return None
        if not self.target_commands:
            return rng.choice(self._recorded).clone()
        candidates = [frame for frame in self._recorded if frame.command in self.target_commands]
        if not candidates:
            return None
        return rng.choice(candidates).clone()

    def clear(self) -> None:
        self._recorded.clear()
