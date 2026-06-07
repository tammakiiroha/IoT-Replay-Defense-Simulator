"""Epoch / reboot / counter-lease 纯函数原语（§8.5）。

engine 与 protocol 共用：reboot 时单调 bump epoch；boot 时烧掉旧 lease 段防 counter 复用。
"""
from __future__ import annotations


def epoch_bump(epoch: int) -> int:
    """reboot 单调推进新鲜域（R2）。旧 epoch 帧此后被接收端显式守门拒（D7）。"""
    return epoch + 1


def burn_lease_on_boot(reserve_high: int, reserve_size: int) -> tuple[int, int]:
    """boot 时烧掉整段旧 lease 预约，返回 (next_tx_counter, new_reserve_high)（R5, D6）。

    next_tx_counter = reserve_high（下一帧 next_frame 会 +1 -> 从 reserve_high+1 起，
    必 > 崩溃前任何已用 ctr）；new_reserve_high = reserve_high + reserve_size（预约新段，
    模拟一次 NVM 写）。纯函数——调用方负责写回 sender 字段。
    """
    return reserve_high, reserve_high + reserve_size


def lease_ok(prev_ctr: int, new_ctr: int) -> bool:
    """跨 boot 单调断言：新 ctr 必须严格大于旧 ctr（不回退、不复用）。"""
    return new_ctr > prev_ctr
