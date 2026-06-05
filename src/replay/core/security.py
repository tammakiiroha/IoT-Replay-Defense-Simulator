"""Security primitives used by the defensive protocol variants."""
from __future__ import annotations

import hashlib
import hmac


def compute_mac(token: int | str, command: str, key: str, mac_length: int = 8) -> str:
    """Return a truncated hexadecimal HMAC over a token and command."""

    if token is None:
        raise ValueError("Token is required to compute a MAC")

    message = f"{token}|{command}".encode()
    mac = hmac.new(key.encode(), message, hashlib.sha256).hexdigest()
    if mac_length <= 0:
        return mac
    return mac[:mac_length]


def compute_mac_bits(token: int | str, command: str, *, key: str, tag_bits: int = 80) -> str:
    if tag_bits % 4 != 0:
        raise ValueError("tag_bits must be divisible by 4 for hex encoding")
    return compute_mac(token, command, key=key, mac_length=tag_bits // 4)


def constant_time_compare(a: str | None, b: str | None) -> bool:
    """Safely compare two MAC strings."""

    if a is None or b is None:
        return False
    return hmac.compare_digest(a, b)
