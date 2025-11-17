"""Simple lossy channel model."""
from __future__ import annotations

import random


def should_drop(probability: float, rng: random.Random) -> bool:
    if probability <= 0.0:
        return False
    if probability >= 1.0:
        return True
    return rng.random() < probability
