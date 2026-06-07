from __future__ import annotations

import hashlib
import hmac

_TAG_HEX = 96 // 4  # 24

DOMAIN_NORMAL_REQ = b"HSWCR_NORMAL_REQ"
DOMAIN_CRIT_PREPARE = b"HSWCR_CRIT_PREPARE"
DOMAIN_CRIT_CONFIRM = b"HSWCR_CRIT_CONFIRM"
DOMAIN_RESYNC_CONFIRM = b"HSWCR_RESYNC_CONFIRM"


def _to_typed_bytes(p: object) -> tuple[bytes, bytes]:
    # 返回 (1B 类型标签, 内容)；类型标签防 int↔bytes、bool↔bytes 等类型混淆（修审查 P1-2）
    if isinstance(p, bytes):
        return b"b", p
    if isinstance(p, bool):                    # 注意：必须在 int 之前（bool 是 int 子类）
        return b"?", (b"\x01" if p else b"\x00")
    if isinstance(p, int):
        return b"i", p.to_bytes(8, "big", signed=True)
    return b"s", str(p).encode("utf-8")


def _encode(*parts: object) -> bytes:
    out = bytearray()
    for p in parts:
        tag, b = _to_typed_bytes(p)
        out += tag + len(b).to_bytes(4, "big") + b  # 类型标签 + 4B 长度前缀 + 内容
    return bytes(out)


def hmac96(key: str, *parts: object) -> str:
    return hmac.new(key.encode(), _encode(*parts), hashlib.sha256).hexdigest()[:_TAG_HEX]


def normal_req_tag(
    key: str, dev_id: int, key_id: int, epoch: int, ctr: int,
    cmd: str, payload: bytes, flags: int,
) -> str:
    return hmac96(key, DOMAIN_NORMAL_REQ, dev_id, key_id, epoch, ctr, cmd, payload, flags)


def crit_prepare_tag(
    key: str, dev_id: int, key_id: int, epoch: int, ctr: int,
    cmd: str, payload_hash: bytes, flags: int,
) -> str:
    return hmac96(key, DOMAIN_CRIT_PREPARE, dev_id, key_id, epoch, ctr, cmd, payload_hash, flags)


def crit_confirm_tag(
    key: str, dev_id: int, key_id: int, epoch: int, ctr: int, cmd: str,
    payload_hash: bytes, pid: int, nonce_id: int, nonce_r: str, ttl: int, flags: int,
) -> str:
    return hmac96(
        key, DOMAIN_CRIT_CONFIRM, dev_id, key_id, epoch, ctr, cmd,
        payload_hash, pid, nonce_id, nonce_r, ttl, flags,
    )


def resync_confirm_tag(
    key: str, dev_id: int, key_id: int, old_epoch: int, new_epoch: int,
    old_h: int, new_h: int, nonce_r: str, ttl: int, flags: int,
) -> str:
    return hmac96(
        key, DOMAIN_RESYNC_CONFIRM, dev_id, key_id, old_epoch, new_epoch,
        old_h, new_h, nonce_r, ttl, flags,
    )
