from __future__ import annotations


def window_commit(n: int, h: int, mask: list[int], w: int) -> tuple[int, list[int]]:
    """滑动窗口状态更新（§8.6-3）。mask[d]=1 表示 counter h-d 已接受。
    仅在帧被接受（ACCEPT_FORWARD / ACCEPT_IN_WINDOW）时调用。返回 (new_h, new_mask)。"""
    if n > h:  # 情形1：前跳接受
        jump = n - h
        new_mask = [0] * w
        new_mask[0] = 1  # 新窗口顶 H'=n 自身置位
        for d in range(w):
            if jump + d < w:
                new_mask[jump + d] = mask[d]
        return n, new_mask
    if h - w + 1 <= n <= h and mask[h - n] == 0:  # 情形2：窗口内接受
        new_mask = list(mask)
        new_mask[h - n] = 1
        return h, new_mask
    return h, list(mask)  # 情形3：dup/old/macfail/resync-pending，不变
