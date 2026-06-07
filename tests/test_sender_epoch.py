from replay.core.sender import Sender
from replay.core.types import Mode

KEY = "k"


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
