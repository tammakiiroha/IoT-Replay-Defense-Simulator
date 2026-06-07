import random

from sim.receiver import Receiver
from sim.security import compute_mac
from sim.sender import Sender
from sim.types import Frame, Mode

KEY = "test_key"
MAC_LEN = 8
W = 5


def _frame(ctr, command="CMD"):
    return Frame(command=command, counter=ctr, mac=compute_mac(ctr, command, KEY, MAC_LEN))


def test_sender_confirm_uses_tx_counter_as_new_h_and_receiver_commits():
    # guard #1：confirm 的 new_h 必须取 sender.tx_counter，不是 challenge.counter(=receiver old_h)
    r = Receiver(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN, window_size=W, g_hard=8)
    r.process(_frame(10))
    r.process(_frame(200))                                   # 触发 -> PENDING
    challenge = r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)
    assert challenge.counter == 10                           # challenge 携带 old_h

    sender = Sender(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN)
    sender.tx_counter = 200                                  # 发送端当前 counter
    confirm = sender.respond_resync_challenge(challenge)
    assert confirm.counter == 200                            # new_h == tx_counter
    assert confirm.flags == Frame.FLAG_RESYNC_CONFIRM
    assert confirm.nonce == challenge.nonce
    assert confirm.ttl == challenge.ttl

    res = r.process_resync_confirm(confirm, now_tick=10)
    assert res.reason == "resync_committed"                  # 两侧 tag 输入对齐 -> 通过
    assert r.state.last_counter == 200
    assert r.state.received_mask == [1] * W


def test_sender_confirm_does_not_borrow_old_h_as_new_h():
    # 若错误地用 challenge.counter(=10) 当 new_h，则 new_h=10 < trigger=200 会被拒
    r = Receiver(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN, window_size=W, g_hard=8)
    r.process(_frame(10))
    r.process(_frame(200))
    challenge = r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)
    sender = Sender(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN)
    sender.tx_counter = 200
    confirm = sender.respond_resync_challenge(challenge)
    assert confirm.counter != challenge.counter             # 不等于 old_h=10
