import random

from replay.core.auth import HmacAuthenticator
from replay.core.kernel.critical_commit import payload_digest
from replay.core.kernel.mac_domains import crit_prepare_tag
from replay.core.receiver import Receiver
from replay.core.sender import Sender
from replay.core.types import Frame, Mode

KEY = "k"
RISK = {"OPEN": 1.0}


def _pair() -> tuple[Receiver, Sender]:
    rcv = Receiver(
        Mode.HSW_CR, shared_key=KEY, mac_length=8, window_size=8,
        command_risk=RISK, risk_high=0.8,
    )
    sender = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)
    sender.tx_counter = 40
    return rcv, sender


def _recover(rcv: Receiver, sender: Sender, *, now_tick: int = 0) -> str:
    sender.adopt_epoch(rcv.state.epoch)
    challenge = rcv.begin_locked_safe_resync(random.Random(1), now_tick=now_tick, ttl_ticks=16)
    confirm = sender.respond_resync_challenge(challenge)
    return rcv.process_resync_confirm(confirm, now_tick=now_tick + 1).reason


def test_sender_adopt_epoch():
    s = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)
    s.adopt_epoch(5)
    assert s.current_epoch == 5


def test_brownout_enters_locked_safe():
    rcv, _ = _pair()
    rcv.reboot()   # brownout == reboot
    assert rcv.state.locked_safe is True
    frame = Frame(command="PING", counter=1, epoch=rcv.state.epoch)
    assert rcv.process(frame).reason == "locked_safe_reject"


def test_locked_safe_recovers_via_authenticated_resync():
    rcv, sender = _pair()
    rcv.reboot()   # epoch 0->1, locked_safe=True, H lost
    assert rcv.state.locked_safe is True
    challenge_epoch = rcv.state.epoch
    reason = _recover(rcv, sender)
    assert reason == "resync_committed"
    assert rcv.state.locked_safe is False
    assert rcv.state.last_counter == 40   # H 重建到 sender.tx_counter
    assert challenge_epoch == 1
    # 恢复后正常高位帧可被接受
    auth = HmacAuthenticator(KEY, 8 * 4)
    frame = Frame(command="PING", counter=41, epoch=1, mac=auth.tag(41, "PING"))
    assert rcv.process(frame).accepted is True


def test_locked_safe_not_recovered_by_old_epoch_confirm():
    rcv, sender = _pair()
    rcv.reboot()   # epoch=1
    sender.adopt_epoch(rcv.state.epoch)
    challenge = rcv.begin_locked_safe_resync(random.Random(1), now_tick=0, ttl_ticks=16)
    bogus = Frame(
        command="RESYNC_CONFIRM", flags=Frame.FLAG_RESYNC_CONFIRM,
        counter=40, epoch=0, nonce=challenge.nonce, ttl=16, mac="00" * 12,
    )
    res = rcv.process_resync_confirm(bogus, now_tick=1)
    assert res.reason != "resync_committed"
    assert rcv.state.locked_safe is True


def test_old_epoch_replay_rejected_after_recovery():
    rcv, sender = _pair()
    rcv.reboot()
    assert _recover(rcv, sender) == "resync_committed"   # 回 NORMAL, epoch=1, H=40
    # 旧 epoch normal replay
    auth = HmacAuthenticator(KEY, 8 * 4)
    old_normal = Frame(command="PING", counter=5, epoch=0, mac=auth.tag(5, "PING"))
    assert rcv.process(old_normal).reason == "epoch_mismatch"
    # 旧 epoch critical replay
    ph = payload_digest(b"data")
    old_prep = Frame(
        command="OPEN", counter=5, epoch=0, flags=Frame.FLAG_CRIT_PREPARE, payload=b"data",
        mac=crit_prepare_tag(KEY, 0, 0, 0, 5, "OPEN", ph, Frame.FLAG_CRIT_PREPARE),
    )
    res = rcv.process_crit_prepare(old_prep, random.Random(2), now_tick=2)
    assert res.reason == "epoch_mismatch"


def test_tampered_epoch_old_normal_rejected_by_sw_window_after_recovery():
    # D7(a) 纵深：攻击者把旧 normal 帧 epoch 篡改为当前(1) 绕过 epoch 守门，
    # 但 counter=5 落在 sealed/old window 内 -> SW 窗口仍 REJECT_OLD（counter_too_old）
    rcv, sender = _pair()
    rcv.reboot()
    assert _recover(rcv, sender) == "resync_committed"   # H=40, epoch=1
    auth = HmacAuthenticator(KEY, 8 * 4)
    # normal MAC 不含 epoch，篡改 epoch 不破坏 MAC（D7=a 前提）
    tampered = Frame(command="PING", counter=5, epoch=1, mac=auth.tag(5, "PING"))
    res = rcv.process(tampered)
    assert res.accepted is False
    assert res.reason == "counter_too_old"
