"""Security primitives used by the defensive protocol variants."""
from __future__ import annotations

import hmac
import hashlib
from typing import Optional


def compute_mac(token: int | str, command: str, key: str, mac_length: int = 8) -> str:
    """Return a truncated hexadecimal HMAC over a token and command."""

    if token is None:
        raise ValueError("Token is required to compute a MAC")

    message = f"{token}|{command}".encode("utf-8")
    mac = hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    if mac_length <= 0:
        return mac
    return mac[:mac_length]


def constant_time_compare(a: Optional[str], b: Optional[str]) -> bool:
    """Wrapper that safely compares two MAC strings, handling missing values."""

    if a is None or b is None:
        return False
    return hmac.compare_digest(a, b)
