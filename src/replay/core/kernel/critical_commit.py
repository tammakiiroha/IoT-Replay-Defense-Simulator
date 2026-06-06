"""Critical 两阶段提交原语（§4.4）：payload 摘要、pid 派生、原子窗口提交（复用 window_commit）。"""
from __future__ import annotations

import hashlib

from .window_commit import window_commit


def payload_digest(payload: bytes) -> bytes:
    # 定长 16 字节，与 crit_*_tag 的 payload_hash: bytes 对齐
    return hashlib.sha256(payload).digest()[:16]


def pid_for(*, epoch: int, ctr: int, cmd: str, payload_hash: bytes) -> int:
    raw = f"{epoch}|{ctr}|{cmd}|".encode() + payload_hash
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")  # 确定性 int pid（去重键）


def critical_commit(*, n: int, h: int, mask: list[int], w: int) -> tuple[int, list[int]]:
    """原子 commit 的窗口部分：与 normal accept 调同一 window_commit（§4.1）。"""
    return window_commit(n, h, mask, w)
