from replay.core import Mode, SimulationConfig
from replay.core.trace import generate_trace


def _cfg():
    return SimulationConfig(
        mode=Mode.SW_RESYNC, num_legit=20, num_replay=30, p_loss=0.1, p_reorder=0.1,
        window_size=5, command_set=["A", "B"],
    )


def test_resync_sequences_present_and_sized():
    t = generate_trace(_cfg(), seed=42)
    assert len(t.resync_challenge_dropped) == 20
    assert len(t.resync_challenge_delay) == 20
    assert len(t.resync_confirm_dropped) == 20
    assert len(t.resync_confirm_delay) == 20


def test_resync_sequences_deterministic():
    a = generate_trace(_cfg(), seed=42)
    b = generate_trace(_cfg(), seed=42)
    assert a.resync_challenge_dropped == b.resync_challenge_dropped
    assert a.resync_challenge_delay == b.resync_challenge_delay
    assert a.resync_confirm_dropped == b.resync_confirm_dropped
    assert a.resync_confirm_delay == b.resync_confirm_delay
