import random

from replay.core.receiver import Receiver
from replay.core.sender import Sender
from replay.core.types import Mode

KEY = "k"


def test_hsw_cr_nonce_response_carries_epoch_round_trip():
    # P2：nonce 应答也必须 stamp current_epoch，否则 epoch 守门会拒 challenge-response
    rcv = Receiver(
        Mode.HSW_CR, shared_key=KEY, mac_length=8, window_size=8,
        command_risk={}, risk_high=0.8,
    )
    rcv.state.epoch = 1
    s = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)
    s.adopt_epoch(1)
    nonce = rcv.issue_nonce(random.Random(1), bits=32, tick=1)
    frame = s.next_frame("PING", nonce=nonce)
    assert frame.epoch == 1
    res = rcv.process(frame)
    assert res.reason != "epoch_mismatch"
    assert res.accepted is True


def test_sender_stamps_current_epoch_on_normal_and_critical():
    s = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)
    s.adopt_epoch(3)
    normal = s.next_frame("PING")
    assert normal.epoch == 3
    prep = s.begin_critical_intent("OPEN", b"data", key_id=0, now_tick=0)
    assert prep.epoch == 3
    assert s.pending_intent is not None
    assert s.pending_intent.epoch == 3


def test_sender_default_epoch_zero():
    s = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)
    assert s.current_epoch == 0
    assert s.next_frame("PING").epoch == 0
