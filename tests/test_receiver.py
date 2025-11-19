import pytest
from sim.receiver import Receiver, VerificationResult
from sim.types import Mode, Frame

# Helper constants
SHARED_KEY = "test_key"
MAC_LENGTH = 8

@pytest.fixture
def receiver_rolling():
    return Receiver(Mode.ROLLING_MAC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)

@pytest.fixture
def receiver_window():
    return Receiver(Mode.WINDOW, shared_key=SHARED_KEY, mac_length=MAC_LENGTH, window_size=5)

def create_frame(counter, command="CMD", key=SHARED_KEY):
    from sim.security import compute_mac
    mac = compute_mac(counter, command, key, MAC_LENGTH)
    return Frame(command=command, counter=counter, mac=mac)

def test_rolling_mac_basic(receiver_rolling):
    # 1. First frame should be accepted
    f1 = create_frame(10)
    res = receiver_rolling.process(f1)
    assert res.accepted
    assert receiver_rolling.state.last_counter == 10

    # 2. Higher counter should be accepted
    f2 = create_frame(11)
    res = receiver_rolling.process(f2)
    assert res.accepted
    assert receiver_rolling.state.last_counter == 11

    # 3. Lower counter (replay) should be rejected
    f3 = create_frame(10)
    res = receiver_rolling.process(f3)
    assert not res.accepted
    assert res.reason == "counter_replay"

def test_window_basic(receiver_window):
    # Window size is 5. Initial state is -1.
    
    # 1. Accept initial
    f1 = create_frame(10)
    res = receiver_window.process(f1)
    assert res.accepted
    assert receiver_window.state.last_counter == 10

    # 2. Accept within window (e.g., 10 + 5 = 15 is max allowed jump? No, diff > window_size is rejected)
    # If last is 10, window is 5.
    # 15 - 10 = 5. 5 > 5 is False. So 15 is accepted.
    # 16 - 10 = 6. 6 > 5 is True. So 16 is rejected.
    f2 = create_frame(15)
    res = receiver_window.process(f2)
    assert res.accepted
    assert receiver_window.state.last_counter == 15

    # 3. Reject replay (exact duplicate)
    f3 = create_frame(15)
    res = receiver_window.process(f3)
    assert not res.accepted
    assert res.reason == "counter_replay"

def test_window_out_of_order(receiver_window):
    # This is the key feature of Window mode!
    
    # 1. Start at 10
    receiver_window.process(create_frame(10))
    
    # 2. Receive 12 (updates last_counter to 12)
    receiver_window.process(create_frame(12))
    assert receiver_window.state.last_counter == 12
    
    # 3. Receive 11 (OLD but valid)
    # 12 - 11 = 1. Offset is 1. Window is 5. 1 < 5.
    # Mask check: bit 1 should be 0.
    f_old = create_frame(11)
    res = receiver_window.process(f_old)
    
    assert res.accepted
    assert res.reason == "window_accept_old"
    
    # 4. Receive 11 AGAIN (Replay)
    res_replay = receiver_window.process(f_old)
    assert not res_replay.accepted
    assert res_replay.reason == "counter_replay"

def test_window_too_far_ahead(receiver_window):
    # Start at 10
    receiver_window.process(create_frame(10))
    
    # Window is 5. Max allowed jump is 5.
    # 10 + 6 = 16.
    f_far = create_frame(16)
    res = receiver_window.process(f_far)
    assert not res.accepted
    assert res.reason == "counter_out_of_window"

def test_window_too_old(receiver_window):
    # Start at 20
    receiver_window.process(create_frame(20))
    
    # Window is 5.
    # Valid range: [20 - 5 + 1, 20] = [16, 20] for old packets?
    # Logic: offset = last - counter. if offset >= window_size: reject.
    # 20 - 15 = 5. 5 >= 5 is True. Reject.
    # 20 - 16 = 4. 4 >= 5 is False. Accept.
    
    f_old = create_frame(15)
    res = receiver_window.process(f_old)
    assert not res.accepted
    assert res.reason == "counter_too_old"
    
    f_valid = create_frame(16)
    res = receiver_window.process(f_valid)
    assert res.accepted
