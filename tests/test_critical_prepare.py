import random

from replay.core.kernel.critical_commit import payload_digest, pid_for
from replay.core.kernel.mac_domains import crit_prepare_tag
from replay.core.receiver import Receiver
from replay.core.types import Frame, Mode

KEY = "k"
RISK = {"OPEN": 0.9, "PING": 0.0}


def _receiver(*, capacity: int = 2, ttl: int = 16) -> Receiver:
    rcv = Receiver(
        Mode.HSW_CR,
        shared_key=KEY,
        mac_length=8,
        window_size=8,
        command_risk=RISK,
        risk_high=0.8,
        critical_pending_capacity=capacity,
        critical_ttl_ticks=ttl,
    )
    rcv.state.epoch = 1   # 帧用 epoch=1；与 Phase 4 显式 epoch 守门对齐（frame.epoch==state.epoch）
    return rcv


def _prepare_frame(
    *, cmd: str = "OPEN", ctr: int = 5, epoch: int = 1, payload: bytes = b"data"
) -> Frame:
    ph = payload_digest(payload)
    mac = crit_prepare_tag(KEY, 0, 0, epoch, ctr, cmd, ph, Frame.FLAG_CRIT_PREPARE)
    return Frame(
        command=cmd,
        counter=ctr,
        epoch=epoch,
        flags=Frame.FLAG_CRIT_PREPARE,
        payload=payload,
        mac=mac,
    )


def test_critical_prepare_does_not_update_global_window():
    # blocker C1: 合法 prepare 仅登记 pending，不动 H/M_W、不执行命令
    rcv = _receiver()
    before_h = rcv.state.last_counter
    before_mask = list(rcv.state.received_mask)
    res = rcv.process_crit_prepare(_prepare_frame(), random.Random(1), now_tick=0)
    assert res.accepted is False
    assert res.reason == "critical_prepared"
    assert rcv.state.last_counter == before_h
    assert rcv.state.received_mask == before_mask


def test_prepare_registers_pending_with_binding_fields():
    rcv = _receiver()
    rcv.process_crit_prepare(_prepare_frame(ctr=5, payload=b"data"), random.Random(1), now_tick=10)
    pid = pid_for(epoch=1, ctr=5, cmd="OPEN", payload_hash=payload_digest(b"data"))
    assert pid in rcv.state.pending_critical
    p = rcv.state.pending_critical[pid]
    assert p.epoch == 1 and p.ctr == 5 and p.cmd == "OPEN"
    assert p.payload_hash == payload_digest(b"data")
    assert p.nonce_r != "" and p.ttl_ticks == 16
    assert p.expire_tick == 26 and p.sender_id == 0


def test_pending_table_capacity_Np_enforced():
    # blocker C3: N_p=2 时第 3 个不同 prepare 被拒，表大小保持 2
    rcv = _receiver(capacity=2)
    rcv.process_crit_prepare(_prepare_frame(ctr=1), random.Random(1), now_tick=0)
    rcv.process_crit_prepare(_prepare_frame(ctr=2), random.Random(2), now_tick=0)
    res = rcv.process_crit_prepare(_prepare_frame(ctr=3), random.Random(3), now_tick=0)
    assert res.reason == "critical_pending_full"
    assert len(rcv.state.pending_critical) == 2


def test_prepare_bad_mac_rejected_no_pending():
    # C4: MAC 篡改 -> mac_mismatch，pending 不新增
    rcv = _receiver()
    frame = _prepare_frame()
    frame.mac = "deadbeef" * 3
    res = rcv.process_crit_prepare(frame, random.Random(1), now_tick=0)
    assert res.reason == "mac_mismatch"
    assert rcv.state.pending_critical == {}


def test_prepare_non_critical_command_rejected():
    rcv = _receiver()
    frame = _prepare_frame(cmd="PING")
    res = rcv.process_crit_prepare(frame, random.Random(1), now_tick=0)
    assert res.reason == "not_critical"
    assert rcv.state.pending_critical == {}


def test_duplicate_prepare_is_idempotent():
    # 修审查#4: 同 (epoch,ctr,cmd,payload) 重复 prepare -> 同 pid；不增长；nonce/ttl 不刷新
    rcv = _receiver()
    rcv.process_crit_prepare(_prepare_frame(), random.Random(1), now_tick=0)
    pid = pid_for(epoch=1, ctr=5, cmd="OPEN", payload_hash=payload_digest(b"data"))
    first = rcv.state.pending_critical[pid]
    first_nonce = first.nonce_r
    first_expire = first.expire_tick
    first_seq = rcv.state.crit_nonce_seq
    res = rcv.process_crit_prepare(_prepare_frame(), random.Random(99), now_tick=5)
    assert res.reason == "critical_prepared"
    assert len(rcv.state.pending_critical) == 1
    again = rcv.state.pending_critical[pid]
    assert again.nonce_r == first_nonce
    assert again.expire_tick == first_expire
    assert again.nonce_id == first.nonce_id
    assert rcv.state.crit_nonce_seq == first_seq


def test_issue_crit_challenge_is_idempotent_delivery():
    rcv = _receiver()
    rcv.process_crit_prepare(_prepare_frame(ctr=5, payload=b"data"), random.Random(1), now_tick=0)
    pid = pid_for(epoch=1, ctr=5, cmd="OPEN", payload_hash=payload_digest(b"data"))
    ch1 = rcv.issue_crit_challenge(pid)
    p = rcv.state.pending_critical[pid]
    assert ch1.flags == Frame.FLAG_CRIT_CHALLENGE
    assert ch1.pid == pid
    assert ch1.nonce_id == p.nonce_id
    assert ch1.nonce == p.nonce_r
    assert ch1.payload_hash == p.payload_hash
    assert ch1.epoch == 1 and ch1.counter == 5 and ch1.ttl == 16
    # 幂等：再取一次，nonce/nonce_id 不变，pending 不变
    ch2 = rcv.issue_crit_challenge(pid)
    assert ch2.nonce == ch1.nonce and ch2.nonce_id == ch1.nonce_id


def test_prepare_rejected_when_mode_not_hsw_cr():
    rcv = Receiver(Mode.CHALLENGE, shared_key=KEY, mac_length=8, command_risk=RISK, risk_high=0.8)
    res = rcv.process_crit_prepare(_prepare_frame(), random.Random(1), now_tick=0)
    assert res.reason == "unexpected_crit_prepare"
