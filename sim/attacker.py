"""Attacker model for record-and-replay experiments."""
from __future__ import annotations

import random
from typing import List, Optional, Sequence

from .types import Frame


class Attacker:
    def __init__(self, record_loss: float = 0.0, target_commands: Optional[Sequence[str]] = None):
        self.record_loss = record_loss
        self.target_commands = set(target_commands) if target_commands else None
        self._recorded: List[Frame] = []

    def observe(self, frame: Frame, rng: random.Random) -> None:
        if self.record_loss > 0 and rng.random() < self.record_loss:
            return
        self._recorded.append(frame.clone())

    def pick_frame(self, rng: random.Random) -> Optional[Frame]:
        if not self._recorded:
            return None
        
        # If no target commands specified, pick any
        if not self.target_commands:
            template = rng.choice(self._recorded)
            return template.clone()
        
        # Filter for target commands
        candidates = [f for f in self._recorded if f.command in self.target_commands]
        if not candidates:
            return None
            
        template = rng.choice(candidates)
        return template.clone()

    def clear(self) -> None:
        self._recorded.clear()
