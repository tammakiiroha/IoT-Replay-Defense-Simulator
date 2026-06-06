"""Critical 两阶段提交原语（§4.4）：payload 摘要、pid 派生、原子窗口提交（复用 window_commit）。"""
from __future__ import annotations

import hashlib

from .window_commit import window_commit


def payload_digest(payload: bytes) -> bytes:
    # 定长 16 字节，与 crit_*_tag 的 payload_hash: bytes 对齐
    return hashlib.sha256(payload).digest()[:16]


def pid_for(*, epoch: int, ctr: int, cmd: str, payload_hash: bytes) -> int:
    raw = f"{epoch}|{ctr}|{cmd}|".encode() + payload_hash
    # 取 63 位：确定性、非负，且落在 MAC 编码器 _to_typed_bytes 的 signed 8-byte 范围内
    # （crit_confirm_tag 把 pid 喂进 HMAC，全 64 位会触发 to_bytes(8, signed=True) 溢出）
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def critical_commit(*, n: int, h: int, mask: list[int], w: int) -> tuple[int, list[int]]:
    """原子 commit 的窗口部分：与 normal accept 调同一 window_commit（§4.1）。"""
    return window_commit(n, h, mask, w)
