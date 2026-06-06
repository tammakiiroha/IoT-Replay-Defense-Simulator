from replay.core.kernel.acceptance import needs_resync
from sim.receiver import Receiver
from sim.security import compute_mac
from sim.types import Frame, Mode

SHARED_KEY = "test_key"
MAC_LENGTH = 8


def _frame(counter, command="CMD"):
    mac = compute_mac(counter, command, SHARED_KEY, MAC_LENGTH)
    return Frame(command=command, counter=counter, mac=mac)


def _recv(mode, *, window_size=5, g_hard=8):
    return Receiver(
        mode, shared_key=SHARED_KEY, mac_length=MAC_LENGTH,
        window_size=window_size, g_hard=g_hard,
    )


# --- kernel needs_resync（§5.3：前跳 gap = n - h）---
def test_forward_jump_within_ghard_is_normal():
    # H=10, n=14 -> jump=4 <= g_hard=8 -> 不触发 resync
    assert needs_resync(14, 10, g_hard=8) is False


def test_forward_jump_over_ghard_triggers_resync():
    # H=10, n=25 -> jump=15 > g_hard=8 -> 触发 resync
    assert needs_resync(25, 10, g_hard=8) is True


def test_backward_never_resync():
    assert needs_resync(8, 10, g_hard=8) is False


# --- receiver 级 resync 语义 ---
def test_pure_window_forward_jump_not_resync():
    # WINDOW = 纯 SW baseline：前跳越 g_hard 仍 ACCEPT_FORWARD（不被污染）
    receiver = _recv(Mode.WINDOW)
    receiver.process(_frame(10))
    res = receiver.process(_frame(100))   # jump=90 >> g_hard
    assert res.accepted
    assert res.reason == "window_accept_new"
    assert receiver.state.last_counter == 100


def test_sw_resync_forward_jump_requires_resync():
    receiver = _recv(Mode.SW_RESYNC)
    receiver.process(_frame(10))
    res = receiver.process(_frame(100))   # jump=90 > g_hard
    assert not res.accepted
    assert res.reason == "resync_required"


def test_resync_required_does_not_mutate_state():
    # 修审查 P1-2：resync_required 路径不得先 window_commit 再 reject
    receiver = _recv(Mode.SW_RESYNC)
    receiver.process(_frame(10))
    before_h = receiver.state.last_counter
    before_mask = list(receiver.state.received_mask)
    res = receiver.process(_frame(100))
    assert res.reason == "resync_required"
    assert receiver.state.last_counter == before_h
    assert receiver.state.received_mask == before_mask


def test_hsw_cr_low_risk_forward_jump_requires_resync():
    # HSW_CR 自带 resync：低风险普通帧前跳越 g_hard 同样 resync_required，不污染状态
    receiver = _recv(Mode.HSW_CR)
    receiver.process(_frame(10))
    res = receiver.process(_frame(100))
    assert not res.accepted
    assert res.reason == "resync_required"
    assert receiver.state.last_counter == 10


def test_sw_resync_accepted_by_receiver_process():
    # SW_RESYNC 必须被 Receiver.process 受理，不抛 Unsupported mode
    receiver = _recv(Mode.SW_RESYNC)
    res = receiver.process(_frame(10))
    assert res.accepted
    assert res.reason == "window_accept_initial"


def test_invalid_mac_far_future_does_not_trigger_resync():
    # 修审查 P1：MAC 必须先于 G_hard —— 伪造 MAC 的大 counter 帧不得进入 resync 路径
    receiver = _recv(Mode.SW_RESYNC)
    receiver.process(_frame(10))
    bad = Frame(command="CMD", counter=100, mac="bad")
    res = receiver.process(bad)
    assert not res.accepted
    assert res.reason == "mac_mismatch"        # 不是 resync_required
    assert receiver.state.last_counter == 10   # 状态未被污染
