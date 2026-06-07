import random

from sim.receiver import Receiver
from sim.security import compute_mac
from sim.types import Frame, Mode

KEY = "test_key"
MAC_LEN = 8


def _frame(ctr, command="CMD"):
    return Frame(command=command, counter=ctr, mac=compute_mac(ctr, command, KEY, MAC_LEN))


def _recv():
    return Receiver(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN, window_size=5, g_hard=8)


def test_trigger_enters_pending_without_window_mutation():
    r = _recv()
    r.process(_frame(10))                      # H=10
    before_h = r.state.last_counter
    before_mask = list(r.state.received_mask)
    res = r.process(_frame(100))               # jump=90 > g_hard -> resync_required
    assert not res.accepted and res.reason == "resync_required"
    assert r.state.last_counter == before_h           # H1：状态未变
    assert r.state.received_mask == before_mask
    assert r.state.resync_pending is not None          # 进 PENDING
    assert r.state.resync_pending.trigger_counter == 100


def test_issue_resync_challenge_emits_r2t_frame_with_nonce_and_ttl():
    r = _recv()
    r.process(_frame(10))
    r.process(_frame(100))                     # 进 pending
    challenge = r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)
    assert challenge.flags == Frame.FLAG_RESYNC_CHALLENGE
    assert challenge.ttl == 20                            # 同一 TTL 必须随挑战带给 sender
    assert challenge.counter == 10                        # 携带 receiver 当前 H（old_h）
    assert r.state.resync_pending.nonce_r == challenge.nonce
    assert r.state.resync_pending.ttl_ticks == 20
    assert r.state.resync_pending.expire_tick == 25     # now_tick + ttl_ticks


def test_repeated_issue_does_not_overwrite_inflight_challenge():
    # 防 in-flight 失效化：已签发的挑战，重复 issue 必须幂等（不换 nonce、不移 TTL 截止）
    r = _recv()
    r.process(_frame(10))
    r.process(_frame(100))
    c1 = r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)
    expire1 = r.state.resync_pending.expire_tick
    c2 = r.issue_resync_challenge(random.Random(999), now_tick=50, ttl_ticks=99)
    assert c2.nonce == c1.nonce                            # 同一 in-flight nonce
    assert r.state.resync_pending.expire_tick == expire1   # 截止不变
    assert r.state.resync_pending.ttl_ticks == 20
