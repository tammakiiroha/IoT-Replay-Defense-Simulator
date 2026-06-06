"""Resync 提交原语（§4.3）：同 epoch 封窗（H2）+ reboot epoch bump。engine/protocol 共用。"""
from __future__ import annotations


def resync_commit_same_epoch(new_h: int, w: int) -> tuple[int, list[int]]:
    """同 epoch 重同步提交：H←new_h，整窗封死 M_W[d]=1 ∀d（§4.3 H2）。
    封窗后只有 ctr>new_h 的新帧可被接受；旧 in-window 帧被判 dup 拒绝。"""
    return new_h, [1] * w


def epoch_bump(old_epoch: int, new_h: int, w: int) -> tuple[int, int, list[int]]:
    """reboot/brownout 强重同步：epoch←old+1，H←new_h，M_W 清零（旧 epoch 帧由调用方全拒）。"""
    return old_epoch + 1, new_h, [0] * w
