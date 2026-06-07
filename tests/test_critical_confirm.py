import random

from replay.core.kernel.critical_commit import payload_digest, pid_for
from replay.core.kernel.mac_domains import crit_confirm_tag, crit_prepare_tag
from replay.core.receiver import Receiver
from replay.core.types import Frame, Mode

KEY = "k"
RISK = {"OPEN": 0.9}
W = 8


def _receiver(*, capacity: int = 2, ttl: int = 16) -> Receiver:
    rcv = Receiver(
        Mode.HSW_CR,
        shared_key=KEY,
        mac_length=8,
        window_size=W,
        command_risk=RISK,
        risk_high=0.8,
        critical_pending_capacity=capacity,
        critical_ttl_ticks=ttl,
    )
    rcv.state.epoch = 1   # 帧用 epoch=1；与 Phase 4 显式 epoch 守门对齐
    return rcv


def _prepare_frame(*, ctr: int = 5, epoch: int = 1, payload: bytes = b"data") -> Frame:
    ph = payload_digest(payload)
    mac = crit_prepare_tag(KEY, 0, 0, epoch, ctr, "OPEN", ph, Frame.FLAG_CRIT_PREPARE)
    return Frame(
        command="OPEN",
        counter=ctr,
        epoch=epoch,
        flags=Frame.FLAG_CRIT_PREPARE,
        payload=payload,
        mac=mac,
    )


def _confirm_for(rcv: Receiver, pid: int, *, nonce_override: str | None = None) -> Frame:
    p = rcv.state.pending_critical[pid]
    nonce_r = nonce_override if nonce_override is not None else p.nonce_r
    mac = crit_confirm_tag(
        KEY, 0, 0, p.epoch, p.ctr, p.cmd, p.payload_hash, pid,
        p.nonce_id, nonce_r, p.ttl_ticks, Frame.FLAG_CRIT_CONFIRM,
    )
    return Frame(
        command=p.cmd,
        counter=p.ctr,
        epoch=p.epoch,
        flags=Frame.FLAG_CRIT_CONFIRM,
        pid=pid,
        nonce_id=p.nonce_id,
        nonce=nonce_r,
        payload_hash=p.payload_hash,
        ttl=p.ttl_ticks,
        mac=mac,
    )


def _prime(payload: bytes = b"data", *, ctr: int = 5) -> tuple[Receiver, int]:
    rcv = _receiver()
    rcv.process_crit_prepare(_prepare_frame(ctr=ctr, payload=payload), random.Random(1), now_tick=0)
    pid = pid_for(epoch=1, ctr=ctr, cmd="OPEN", payload_hash=payload_digest(payload))
    return rcv, pid


def test_critical_commit_updates_window_and_executes_once():
    # blocker C2/C6: 合法 confirm -> 原子 commit、执行一次、删 pending、记 committed
    rcv, pid = _prime(ctr=5)
    res = rcv.process_crit_confirm(_confirm_for(rcv, pid), now_tick=5)
    assert res.accepted is True
    assert res.reason == "critical_committed"
    assert rcv.state.last_counter == 5
    assert pid in rcv.state.committed_critical
    assert pid not in rcv.state.pending_critical


def test_duplicate_confirm_does_not_recommit():
    # C2: 同 pid 第二次 confirm 不二次执行、窗口不再变
    rcv, pid = _prime(ctr=5)
    confirm = _confirm_for(rcv, pid)
    rcv.process_crit_confirm(confirm, now_tick=5)
    h_after = rcv.state.last_counter
    res = rcv.process_crit_confirm(confirm, now_tick=6)
    assert res.accepted is False
    assert res.reason == "critical_already_committed"
    assert rcv.state.last_counter == h_after


def test_fake_challenge_does_not_commit():
    # blocker: pid 不在 pending（伪造/未 prepare）-> 不 commit
    rcv = _receiver()
    # epoch=1 匹配 receiver（过 epoch 守门），但 pid 不在 pending -> critical_no_pending
    fake = Frame(command="OPEN", flags=Frame.FLAG_CRIT_CONFIRM, pid=999, epoch=1, mac="00" * 12)
    res = rcv.process_crit_confirm(fake, now_tick=1)
    assert res.accepted is False
    assert res.reason == "critical_no_pending"
    assert rcv.state.last_counter == -1


def test_confirm_bad_mac_keeps_pending():
    # C4: 篡改 tag -> mac_mismatch；pending 保留、窗口不变
    rcv, pid = _prime(ctr=5)
    confirm = _confirm_for(rcv, pid)
    confirm.mac = "deadbeef" * 3
    res = rcv.process_crit_confirm(confirm, now_tick=5)
    assert res.reason == "mac_mismatch"
    assert pid in rcv.state.pending_critical
    assert rcv.state.last_counter == -1


def test_confirm_wrong_nonce_is_mac_mismatch():
    # nonce_r 绑进 confirm tag：篡改 nonce -> mac 对不上 -> mac_mismatch，保留 pending
    rcv, pid = _prime(ctr=5)
    confirm = _confirm_for(rcv, pid, nonce_override="ffff")
    res = rcv.process_crit_confirm(confirm, now_tick=5)
    assert res.reason == "mac_mismatch"
    assert pid in rcv.state.pending_critical


def test_confirm_ttl_expired_clears_pending():
    rcv, pid = _prime(ctr=5)   # prepare now_tick=0, ttl=16 -> expire=16
    res = rcv.process_crit_confirm(_confirm_for(rcv, pid), now_tick=17)
    assert res.reason == "critical_ttl_expired"
    assert pid not in rcv.state.pending_critical
    assert pid not in rcv.state.committed_critical
    assert rcv.state.last_counter == -1


def test_confirm_sw_reject_when_ctr_old():
    # 窗口已前进到 10；旧 ctr=1 的 confirm 不被借道提交
    rcv = _receiver()
    rcv.state.last_counter = 10
    rcv.state.received_mask = [1] + [0] * (W - 1)
    rcv.process_crit_prepare(_prepare_frame(ctr=1), random.Random(1), now_tick=0)
    pid = pid_for(epoch=1, ctr=1, cmd="OPEN", payload_hash=payload_digest(b"data"))
    res = rcv.process_crit_confirm(_confirm_for(rcv, pid), now_tick=5)
    assert res.accepted is False
    assert res.reason == "critical_sw_reject"
    assert rcv.state.last_counter == 10
    assert pid not in rcv.state.pending_critical


def test_confirm_rejected_when_mode_not_hsw_cr():
    rcv = Receiver(Mode.CHALLENGE, shared_key=KEY, mac_length=8, command_risk=RISK, risk_high=0.8)
    fake = Frame(command="OPEN", flags=Frame.FLAG_CRIT_CONFIRM, pid=1, mac="00" * 12)
    res = rcv.process_crit_confirm(fake, now_tick=1)
    assert res.reason == "unexpected_crit_confirm"
