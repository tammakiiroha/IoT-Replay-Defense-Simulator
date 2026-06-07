from replay.core.types import ResyncPending
from sim.types import ReceiverState


def test_receiver_state_defaults_epoch_zero_no_pending():
    s = ReceiverState()
    assert s.epoch == 0
    assert s.resync_pending is None


def test_resync_pending_holds_challenge_context():
    p = ResyncPending(
        nonce_r="ab", trigger_counter=200, epoch=1, h_at_challenge=10,
        ttl_ticks=20, expire_tick=42,
    )
    assert p.nonce_r == "ab" and p.trigger_counter == 200
    assert p.epoch == 1 and p.h_at_challenge == 10
    assert p.ttl_ticks == 20 and p.expire_tick == 42
