import random

from replay.core.kernel.critical_commit import payload_digest
from replay.core.kernel.mac_domains import crit_prepare_tag
from replay.core.receiver import Receiver
from replay.core.types import CriticalPending, Frame, Mode, ResyncPending

KEY = "k"
RISK = {"OPEN": 1.0}


def _receiver() -> Receiver:
    return Receiver(
        Mode.HSW_CR, shared_key=KEY, mac_length=8, window_size=8,
        command_risk=RISK, risk_high=0.8,
    )


def _prepare_frame(*, epoch: int, ctr: int = 5, payload: bytes = b"data") -> Frame:
    ph = payload_digest(payload)
    mac = crit_prepare_tag(KEY, 0, 0, epoch, ctr, "OPEN", ph, Frame.FLAG_CRIT_PREPARE)
    return Frame(
        command="OPEN", counter=ctr, epoch=epoch,
        flags=Frame.FLAG_CRIT_PREPARE, payload=payload, mac=mac,
    )


def test_reboot_bumps_epoch_and_enters_locked_safe():
    rcv = _receiver()
    rcv.state.epoch = 3
    rcv.reboot()
    assert rcv.state.epoch == 4
    assert rcv.state.nvm_epoch == 4
    assert rcv.state.boot_counter == 1
    assert rcv.state.locked_safe is True


def test_reboot_clears_pending_tables():
    rcv = _receiver()
    rcv.state.last_counter = 50
    rcv.state.received_mask = [1, 0, 0, 0, 0, 0, 0, 0]
    rcv.state.resync_pending = ResyncPending(
        nonce_r="r", trigger_counter=5, epoch=0, h_at_challenge=4, ttl_ticks=16, expire_tick=20,
    )
    rcv.state.pending_critical = {
        123: CriticalPending(
            epoch=0, ctr=5, cmd="OPEN", payload_hash=b"x", nonce_id=0, nonce_r="r",
            ttl_ticks=16, expire_tick=20, sender_id=0, key_id=0,
        )
    }
    rcv.state.committed_critical = {999}
    rcv.state.outstanding_nonces = {"x": 1}
    rcv.state.expected_nonce = "x"
    rcv.state.crit_nonce_seq = 5
    rcv.reboot()
    assert rcv.state.last_counter == -1
    assert rcv.state.received_mask == []
    assert rcv.state.resync_pending is None
    assert rcv.state.pending_critical == {}
    assert rcv.state.committed_critical == set()
    assert rcv.state.outstanding_nonces == {}
    assert rcv.state.expected_nonce is None
    assert rcv.state.crit_nonce_seq == 0


def test_reboot_clears_used_nonces_and_issue_tick():
    # P3：reboot 也应清易失 challenge 状态 used_nonces，并复位 _issue_tick
    rcv = _receiver()
    rcv.state.used_nonces = {"a", "b"}
    rcv._issue_tick = 7
    rcv.reboot()
    assert rcv.state.used_nonces == set()
    assert rcv._issue_tick == 0


def test_old_epoch_frame_rejected_by_explicit_gate():
    # 非 LOCKED_SAFE，但 frame.epoch != state.epoch -> epoch_mismatch（D7 显式守门），状态不变
    rcv = _receiver()  # state.epoch=0, locked_safe=False
    normal = Frame(command="PING", counter=1, epoch=5)
    assert rcv.process(normal).reason == "epoch_mismatch"
    prep = _prepare_frame(epoch=5)
    res = rcv.process_crit_prepare(prep, random.Random(1), now_tick=0)
    assert res.reason == "epoch_mismatch"
    assert rcv.state.pending_critical == {}
    confirm = Frame(command="OPEN", flags=Frame.FLAG_CRIT_CONFIRM, pid=1, epoch=5, mac="00" * 12)
    assert rcv.process_crit_confirm(confirm, now_tick=0).reason == "epoch_mismatch"


def test_locked_safe_rejects_normal_and_critical():
    rcv = _receiver()
    rcv.reboot()  # locked_safe=True, epoch bumped 0->1
    # 即便 epoch 匹配（=1），LOCKED_SAFE 闸门先于 epoch 闸门拒
    normal = Frame(command="PING", counter=1, epoch=1)
    assert rcv.process(normal).reason == "locked_safe_reject"
    prep = _prepare_frame(epoch=1)
    prep_res = rcv.process_crit_prepare(prep, random.Random(1), now_tick=0)
    assert prep_res.reason == "locked_safe_reject"
    confirm = Frame(command="OPEN", flags=Frame.FLAG_CRIT_CONFIRM, pid=1, epoch=1, mac="00" * 12)
    assert rcv.process_crit_confirm(confirm, now_tick=0).reason == "locked_safe_reject"
