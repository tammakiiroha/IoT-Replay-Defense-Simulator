import random

from replay.core.kernel.mac_domains import resync_confirm_tag
from sim.receiver import Receiver
from sim.security import compute_mac
from sim.types import Frame, Mode

KEY = "test_key"
MAC_LEN = 8
W = 5


def _frame(ctr, command="CMD"):
    return Frame(command=command, counter=ctr, mac=compute_mac(ctr, command, KEY, MAC_LEN))


def _pending_recv(trigger=200):
    r = Receiver(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN, window_size=W, g_hard=8)
    r.process(_frame(10))
    r.process(_frame(trigger))                          # resync_required -> pending
    r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)   # expire_tick=25
    return r


def _valid_confirm(r, new_h):
    p = r.state.resync_pending
    tag = resync_confirm_tag(
        KEY, 0, 0, p.epoch, p.epoch, p.h_at_challenge, new_h, p.nonce_r, p.ttl_ticks,
        Frame.FLAG_RESYNC_CONFIRM,
    )
    return Frame(
        command="RESYNC_CONFIRM", flags=Frame.FLAG_RESYNC_CONFIRM, counter=new_h,
        epoch=p.epoch, nonce=p.nonce_r, ttl=p.ttl_ticks, mac=tag,
    )


def test_resync_confirm_does_not_execute_original_command():  # H1
    r = _pending_recv(200)
    res = r.process_resync_confirm(_valid_confirm(r, 200), now_tick=10)
    assert res.accepted is False
    assert res.reason == "resync_committed"


def test_resync_seals_skipped_window_counters():  # H2
    r = _pending_recv(200)
    r.process_resync_confirm(_valid_confirm(r, 200), now_tick=10)
    assert r.state.last_counter == 200
    assert r.state.received_mask == [1] * W
    assert r.state.resync_pending is None


def test_old_in_window_frame_rejected_after_resync():  # H2
    r = _pending_recv(200)
    r.process_resync_confirm(_valid_confirm(r, 200), now_tick=10)
    res = r.process(_frame(198))   # 198 ∈ [196,200]，封窗 -> dup 拒绝
    assert not res.accepted


def test_bad_mac_confirm_keeps_pending():
    r = _pending_recv(200)
    bad = _valid_confirm(r, 200)
    bad.mac = "deadbeefdeadbeefdeadbeef"
    res = r.process_resync_confirm(bad, now_tick=10)
    assert res.reason == "mac_mismatch"
    assert r.state.resync_pending is not None
    assert r.state.last_counter == 10            # 窗口未变


def test_wrong_nonce_confirm_keeps_pending():
    r = _pending_recv(200)
    p = r.state.resync_pending
    tag = resync_confirm_tag(
        KEY, 0, 0, p.epoch, p.epoch, p.h_at_challenge, 200, p.nonce_r, p.ttl_ticks,
        Frame.FLAG_RESYNC_CONFIRM,
    )
    f = Frame(
        command="RESYNC_CONFIRM", flags=Frame.FLAG_RESYNC_CONFIRM, counter=200,
        epoch=p.epoch, nonce="ffff", ttl=p.ttl_ticks, mac=tag,   # nonce 与 pending 不符
    )
    res = r.process_resync_confirm(f, now_tick=10)
    assert res.reason == "resync_nonce_mismatch"
    assert r.state.resync_pending is not None


def test_expired_confirm_clears_pending():
    r = _pending_recv(200)   # expire_tick = 25
    res = r.process_resync_confirm(_valid_confirm(r, 200), now_tick=26)   # 26 > 25 过期
    assert res.reason == "resync_ttl_expired"
    assert r.state.resync_pending is None


def test_confirm_with_new_h_below_trigger_rejected():
    # 防状态回退：new_h 必须 >= 触发 resync 的 counter；MAC 合法的 new_h=11 也要拒
    r = _pending_recv(200)                                       # trigger_counter=200, H=10
    res = r.process_resync_confirm(_valid_confirm(r, 11), now_tick=10)   # new_h=11 < 200
    assert res.reason == "resync_counter_mismatch"
    assert r.state.resync_pending is not None                   # 保持 PENDING
    assert r.state.last_counter == 10                           # 窗口未回退
    assert r.state.received_mask == [1, 0, 0, 0, 0]
