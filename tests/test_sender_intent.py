import random

from replay.core.kernel.critical_commit import payload_digest, pid_for
from replay.core.receiver import Receiver
from replay.core.sender import Sender
from replay.core.types import Frame, Mode

KEY = "k"


def _sender() -> Sender:
    return Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)


def _challenge(
    pid: int, *, key_id: int = 0, epoch: int = 1, nonce_id: int = 0,
    nonce: str = "abc", ttl: int = 16, dev_id: int = 0,
) -> Frame:
    return Frame(
        command="OPEN",
        flags=Frame.FLAG_CRIT_CHALLENGE,
        pid=pid,
        key_id=key_id,
        epoch=epoch,
        nonce_id=nonce_id,
        nonce=nonce,
        ttl=ttl,
        dev_id=dev_id,
    )


def test_begin_intent_emits_prepare_and_records_identity():
    s = _sender()
    prep = s.begin_critical_intent("OPEN", b"data", epoch=1, key_id=0, now_tick=0)
    assert prep.flags == Frame.FLAG_CRIT_PREPARE
    assert prep.counter == 1 and prep.command == "OPEN"
    intent = s.pending_intent
    assert intent is not None
    assert intent.pid == pid_for(epoch=1, ctr=1, cmd="OPEN", payload_hash=payload_digest(b"data"))
    assert intent.consumed is False


def test_sender_confirms_when_intent_matches():
    s = _sender()
    s.begin_critical_intent("OPEN", b"data", epoch=1, key_id=0, now_tick=0)
    intent = s.pending_intent
    confirm = s.confirm_critical_challenge(_challenge(intent.pid), now_tick=1, tau_intent=10)
    assert confirm is not None
    assert confirm.flags == Frame.FLAG_CRIT_CONFIRM
    assert confirm.pid == intent.pid
    assert s.pending_intent.consumed is True


def test_replayed_old_critical_req_no_sender_confirm_without_user_intent():
    # blocker §4.5: 无意图（攻击者重放，真发送端从未发起）-> 不替攻击者 confirm
    s = _sender()
    assert s.confirm_critical_challenge(_challenge(12345), now_tick=1, tau_intent=10) is None


def test_intent_expires_after_tau():
    s = _sender()
    s.begin_critical_intent("OPEN", b"data", epoch=1, key_id=0, now_tick=0)
    intent = s.pending_intent
    assert s.confirm_critical_challenge(_challenge(intent.pid), now_tick=100, tau_intent=10) is None


def test_intent_consumed_once():
    s = _sender()
    s.begin_critical_intent("OPEN", b"data", epoch=1, key_id=0, now_tick=0)
    intent = s.pending_intent
    ch = _challenge(intent.pid)
    assert s.confirm_critical_challenge(ch, now_tick=1, tau_intent=10) is not None
    assert s.confirm_critical_challenge(ch, now_tick=2, tau_intent=10) is None


def test_challenge_wrong_epoch_or_keyid_rejected():
    s = _sender()
    s.begin_critical_intent("OPEN", b"data", epoch=1, key_id=0, now_tick=0)
    intent = s.pending_intent
    assert s.confirm_critical_challenge(
        _challenge(intent.pid, epoch=2), now_tick=1, tau_intent=10
    ) is None
    # 前一次因 epoch 不匹配被拒，intent 未消费，可继续验 key_id 分支
    assert s.confirm_critical_challenge(
        _challenge(intent.pid, key_id=9), now_tick=1, tau_intent=10
    ) is None


def test_old_prepare_same_cmd_payload_rejected_by_pid():
    # 修审查#1: 用户已发新 intent；攻击者重放旧 prepare challenge（同 cmd/payload，旧 ctr->旧 pid）
    s = _sender()
    s.begin_critical_intent("OPEN", b"data", epoch=1, key_id=0, now_tick=0)  # ctr=1 -> new pid
    new_intent = s.pending_intent
    old_pid = pid_for(epoch=1, ctr=999, cmd="OPEN", payload_hash=payload_digest(b"data"))
    assert old_pid != new_intent.pid
    ch = _challenge(old_pid, epoch=1, key_id=0)   # 同 cmd/payload，但 pid 是旧的
    assert s.confirm_critical_challenge(ch, now_tick=1, tau_intent=10) is None


def test_full_round_trip_sender_receiver_commits_once():
    # 端到端：sender prepare -> receiver prepare -> challenge -> sender confirm -> receiver commit
    s = _sender()
    rcv = Receiver(
        Mode.HSW_CR, shared_key=KEY, mac_length=8, window_size=8,
        command_risk={"OPEN": 0.9}, risk_high=0.8,
    )
    prep = s.begin_critical_intent("OPEN", b"data", epoch=1, key_id=0, now_tick=0)
    r1 = rcv.process_crit_prepare(prep, random.Random(1), now_tick=0)
    assert r1.reason == "critical_prepared"
    challenge = rcv.issue_crit_challenge(s.pending_intent.pid)
    confirm = s.confirm_critical_challenge(challenge, now_tick=1, tau_intent=10)
    assert confirm is not None
    r2 = rcv.process_crit_confirm(confirm, now_tick=2)
    assert r2.accepted is True and r2.reason == "critical_committed"
    assert rcv.state.last_counter == 1
