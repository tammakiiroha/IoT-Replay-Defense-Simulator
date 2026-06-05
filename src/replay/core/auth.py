"""Authenticator profiles for replay-defense modes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .security import compute_mac_bits, constant_time_compare


class Authenticator(Protocol):
    @property
    def profile(self) -> str: ...

    @property
    def tag_bits(self) -> int: ...

    def tag(self, token: int | str, command: str) -> str: ...

    def verify(self, token: int | str, command: str, tag: str | None) -> bool: ...


@dataclass(frozen=True)
class HmacAuthenticator:
    key: str
    tag_bits: int = 80
    profile: str = "hmac"

    def tag(self, token: int | str, command: str) -> str:
        return compute_mac_bits(token, command, key=self.key, tag_bits=self.tag_bits)

    def verify(self, token: int | str, command: str, tag: str | None) -> bool:
        return constant_time_compare(self.tag(token, command), tag)


class AsconAeadAuthenticator:
    profile = "ascon"

    def __init__(self, key: bytes | str, tag_bits: int = 80):
        try:
            self._ascon = __import__("ascon")
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pip install replay[crypto]") from exc
        raw_key = key.encode() if isinstance(key, str) else key
        self.key = raw_key[:16].ljust(16, b"0")
        self.tag_bits = tag_bits

    def tag(self, token: int | str, command: str) -> str:
        data = f"{token}|{command}".encode()
        digest = self._ascon.hash(self.key + data, variant="Ascon-Hash", hashlength=32)
        return digest.hex()[: self.tag_bits // 4]

    def verify(self, token: int | str, command: str, tag: str | None) -> bool:
        return constant_time_compare(self.tag(token, command), tag)
