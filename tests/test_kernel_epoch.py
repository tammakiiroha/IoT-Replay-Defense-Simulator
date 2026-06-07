from replay.core.kernel.epoch import burn_lease_on_boot, epoch_bump, lease_ok


def test_epoch_bump_is_monotonic():
    assert epoch_bump(0) == 1
    assert epoch_bump(7) == 8
    # 严格递增：连续 bump 不回退
    e = 0
    for _ in range(5):
        e2 = epoch_bump(e)
        assert e2 > e
        e = e2


def test_burn_lease_on_boot_prevents_reuse():
    # 崩溃前只用到 10、NVM high=100 -> boot 烧旧段：下一帧 tx_counter 必 >100（非 11、非 1）
    next_tx_counter, new_reserve_high = burn_lease_on_boot(100, 100)
    assert next_tx_counter == 100          # next_frame 会 +1 -> 101 > 100
    assert new_reserve_high == 200
    # 下一帧 ctr = next_tx_counter + 1
    assert next_tx_counter + 1 == 101


def test_burn_lease_on_boot_reserve_size_varies():
    assert burn_lease_on_boot(50, 32) == (50, 82)
    assert burn_lease_on_boot(0, 16) == (0, 16)


def test_lease_ok_rejects_reuse_and_rollback():
    assert lease_ok(10, 11) is True
    assert lease_ok(10, 10) is False       # 复用
    assert lease_ok(10, 5) is False        # 回退
