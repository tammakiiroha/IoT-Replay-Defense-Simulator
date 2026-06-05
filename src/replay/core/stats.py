"""Binomial-proportion statistics."""
from __future__ import annotations

import math
from dataclasses import dataclass

_Z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}


@dataclass(frozen=True)
class BinomialCI:
    point: float
    lower: float
    upper: float
    successes: int
    trials: int

    @property
    def half_width(self) -> float:
        return (self.upper - self.lower) / 2.0


def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> BinomialCI:
    if trials <= 0:
        return BinomialCI(0.0, 0.0, 1.0, 0, 0)
    z = _Z.get(confidence, 1.96)
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denom
    return BinomialCI(
        point=p,
        lower=max(0.0, center - margin),
        upper=min(1.0, center + margin),
        successes=successes,
        trials=trials,
    )


def ci_overlap(a: BinomialCI, b: BinomialCI) -> bool:
    return a.lower <= b.upper and b.lower <= a.upper
