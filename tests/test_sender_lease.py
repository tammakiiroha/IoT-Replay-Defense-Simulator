from replay.core.kernel.epoch import lease_ok
from replay.core.sender import Sender
from replay.core.types import Mode

KEY = "k"


def test_counter_lease_never_reuses_across_boot():
    # 崩溃前只用到 10、NVM high=100 -> boot 烧旧段：下一帧 ctr 必 >100（非 11、非 1）
    s = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8, reserve_size=100)
    s.tx_counter = 10
    s.nvm_ctr_reserve_high = 100
    s.begin_boot()
    frame = s.next_frame("PING")
    assert frame.counter is not None and frame.counter > 100
    assert frame.counter == 101
    assert s.boot_counter == 1


def test_lease_reserves_in_blocks_not_every_frame():
    s = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8, reserve_size=64)
    highs = []
    for _ in range(70):
        s.next_frame("PING")
        highs.append(s.nvm_ctr_reserve_high)
    assert highs[0] == 64       # 第 1 帧预约一段
    assert highs[63] == 64      # 1..64 帧内不再写 NVM
    assert highs[64] == 128     # 第 65 帧才扩容
    assert len(set(highs)) <= 2


def test_lease_ok_monotonic_across_boot():
    s = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8, reserve_size=50)
    s.tx_counter = 5
    s.nvm_ctr_reserve_high = 50
    before = s.tx_counter
    s.begin_boot()
    frame = s.next_frame("PING")
    assert frame.counter is not None
    assert lease_ok(before, frame.counter)
