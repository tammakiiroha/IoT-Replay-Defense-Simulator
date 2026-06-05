"""Pluggable loss/delay models for the simulation channel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .rng import RandomLike


class LossModel(Protocol):
    def dropped(self, rng: RandomLike) -> bool: ...


class DelayModel(Protocol):
    def delay(self, rng: RandomLike) -> int: ...


@dataclass
class IidLoss:
    p_loss: float

    def dropped(self, rng: RandomLike) -> bool:
        return self.p_loss > 0 and rng.random() < self.p_loss


@dataclass
class GilbertElliottLoss:
    p_good_to_bad: float = 0.05
    p_bad_to_good: float = 0.30
    loss_good: float = 0.01
    loss_bad: float = 0.60
    in_bad_state: bool = False

    def dropped(self, rng: RandomLike) -> bool:
        if self.in_bad_state:
            if rng.random() < self.p_bad_to_good:
                self.in_bad_state = False
        elif rng.random() < self.p_good_to_bad:
            self.in_bad_state = True
        p = self.loss_bad if self.in_bad_state else self.loss_good
        return rng.random() < p

    @property
    def steady_state_loss(self) -> float:
        denom = self.p_good_to_bad + self.p_bad_to_good
        p_bad = self.p_good_to_bad / denom if denom else 0.0
        return (1 - p_bad) * self.loss_good + p_bad * self.loss_bad


@dataclass
class TraceLoss:
    drops: list[bool]
    _i: int = 0

    def dropped(self, rng: RandomLike) -> bool:
        if not self.drops:
            return False
        idx = min(self._i, len(self.drops) - 1)
        self._i += 1
        return self.drops[idx]


@dataclass
class ReorderDelay:
    p_reorder: float
    max_delay: int = 3

    def delay(self, rng: RandomLike) -> int:
        if self.p_reorder > 0 and rng.random() < self.p_reorder:
            return rng.randint(1, self.max_delay)
        return 0
