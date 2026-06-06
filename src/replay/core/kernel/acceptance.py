from __future__ import annotations

from enum import Enum


class SwDecision(str, Enum):
    ACCEPT_FORWARD = "accept_forward"
    ACCEPT_IN_WINDOW = "accept_in_window"
    REJECT_DUP = "reject_dup"
    REJECT_OLD = "reject_old"


def classify(n: int, h: int, mask: list[int], w: int) -> SwDecision:
    """SW 四分支判定（§5.2）。只判定是否接受，不更新状态（更新走 window_commit）。"""
    if n > h:
        return SwDecision.ACCEPT_FORWARD
    if h - w + 1 <= n <= h:
        return SwDecision.REJECT_DUP if mask[h - n] == 1 else SwDecision.ACCEPT_IN_WINDOW
    return SwDecision.REJECT_OLD
