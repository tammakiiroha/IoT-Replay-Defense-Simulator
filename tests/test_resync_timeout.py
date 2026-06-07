"""锁死 resync 异常路径 + 有界子泵近似。

有界子泵近似（§4.3 Option A，2.4c 实现）：resync 往返在【触发帧那一步内】解算——
challenge 或 confirm 任一丢失即【立即】归 timeout 并清 pending；pending 不跨多个 legit tick 存活。
迟到的 confirm（arrival > expire_tick）同样判 timeout。边界 now_tick == expire_tick 视为未过期。
"""
import random

from replay.core.cost import CostStats
from replay.core.experiment import _resolve_resync
from replay.core.kernel.mac_domains import resync_confirm_tag
from sim.receiver import Receiver
from sim.security import compute_mac
from sim.sender import Sender
from sim.types import Frame, Mode

KEY = "test_key"
MAC_LEN = 8
W = 5


def _frame(ctr, command="CMD"):
    return Frame(command=command, counter=ctr, mac=compute_mac(ctr, command, KEY, MAC_LEN))


def _triggered_recv(trigger=200):
    # 触发后进 PENDING，但尚未签发挑战（nonce_r == ""）—— 供 _resolve_resync 接管
    r = Receiver(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN, window_size=W, g_hard=8)
    r.process(_frame(10))
    r.process(_frame(trigger))
    return r


def _sender():
    s = Sender(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN)
    s.tx_counter = 200
    return s


# --- time_out_resync / pending 清理 ---
def test_time_out_resync_clears_pending():
    r = _triggered_recv(200)
    assert r.state.resync_pending is not None
    r.time_out_resync()
    assert r.state.resync_pending is None


# --- 有界子泵：丢包立即归 timeout，pending 不跨 tick 存活 ---
def test_bounded_pump_dropped_challenge_times_out_immediately():
    r = _triggered_recv(200)
    cost = CostStats()
    _resolve_resync(
        r, _sender(), cost, rng=random.Random(0), now_tick=5, ttl_ticks=20, rtt_ticks=1,
        transport=lambda: (True, 0, False, 0),   # challenge 丢失
    )
    assert cost.resync_initiated == 1
    assert cost.resync_timeout == 1
    assert cost.resync_completed == 0
    assert r.state.resync_pending is None        # 立即清，不跨 tick


def test_bounded_pump_dropped_confirm_times_out_immediately():
    r = _triggered_recv(200)
    cost = CostStats()
    _resolve_resync(
        r, _sender(), cost, rng=random.Random(0), now_tick=5, ttl_ticks=20, rtt_ticks=1,
        transport=lambda: (False, 0, True, 0),   # confirm 丢失
    )
    assert cost.resync_timeout == 1 and cost.resync_completed == 0
    assert r.state.resync_pending is None


def test_bounded_pump_clean_round_trip_completes():
    r = _triggered_recv(200)
    cost = CostStats()
    _resolve_resync(
        r, _sender(), cost, rng=random.Random(0), now_tick=5, ttl_ticks=20, rtt_ticks=1,
        transport=lambda: (False, 0, False, 0),  # 无损往返
    )
    assert cost.resync_completed == 1 and cost.resync_timeout == 0
    assert r.state.last_counter == 200
    assert r.state.received_mask == [1] * W
    assert r.state.resync_pending is None


def test_bounded_pump_late_confirm_expires():
    # delays 把 arrival 推过 expire：now=5, ttl=2 -> expire=7；arrival=5+1+5+5=16 > 7
    r = _triggered_recv(200)
    cost = CostStats()
    _resolve_resync(
        r, _sender(), cost, rng=random.Random(0), now_tick=5, ttl_ticks=2, rtt_ticks=1,
        transport=lambda: (False, 5, False, 5),
    )
    assert cost.resync_timeout == 1 and cost.resync_completed == 0
    assert r.state.resync_pending is None


# --- process_resync_confirm 的 TTL 边界 ---
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


def test_confirm_at_ttl_boundary_still_commits():
    r = _triggered_recv(200)
    r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)   # expire_tick=25
    res = r.process_resync_confirm(_valid_confirm(r, 200), now_tick=25)    # == expire 未过期
    assert res.reason == "resync_committed"


def test_confirm_one_past_ttl_expires():
    r = _triggered_recv(200)
    r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)   # expire_tick=25
    res = r.process_resync_confirm(_valid_confirm(r, 200), now_tick=26)    # > expire 过期
    assert res.reason == "resync_ttl_expired"
    assert r.state.resync_pending is None
