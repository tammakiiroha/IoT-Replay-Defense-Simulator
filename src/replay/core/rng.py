"""Deterministic RNG shared by simulation backends and parity tests."""
from __future__ import annotations

import secrets
from collections.abc import Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")

MASK64 = (1 << 64) - 1
FLOAT_DENOMINATOR = 1 << 53


class RandomLike(Protocol):
    def random(self) -> float: ...

    def randint(self, a: int, b: int) -> int: ...

    def choice(self, seq: Sequence[T]) -> T: ...

    def getrandbits(self, k: int) -> int: ...


class DeterministicRNG:
    """SplitMix64-based RNG with a minimal Python random-like interface."""

    def __init__(self, seed: int | None = None):
        if seed is None:
            seed = secrets.randbits(64)
        self._state = seed & MASK64

    def _next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & MASK64
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return (z ^ (z >> 31)) & MASK64

    def random(self) -> float:
        return (self._next_u64() >> 11) / FLOAT_DENOMINATOR

    def getrandbits(self, k: int) -> int:
        if k < 0:
            raise ValueError("number of bits must be non-negative")
        if k == 0:
            return 0

        acc = 0
        produced = 0
        while produced < k:
            acc |= self._next_u64() << produced
            produced += 64
        return acc & ((1 << k) - 1)

    def _randbelow(self, limit: int) -> int:
        if limit <= 0:
            raise ValueError("limit must be positive")
        bits = (limit - 1).bit_length()
        while True:
            candidate = self.getrandbits(bits)
            if candidate < limit:
                return candidate

    def randint(self, a: int, b: int) -> int:
        if b < a:
            raise ValueError("empty range for randint()")
        return a + self._randbelow(b - a + 1)

    def choice(self, seq: Sequence[T]) -> T:
        if not seq:
            raise IndexError("cannot choose from an empty sequence")
        return seq[self._randbelow(len(seq))]
