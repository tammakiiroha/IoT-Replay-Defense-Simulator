from replay.core.types import CriticalPending, ReceiverState


def test_defaults_empty_tables():
    s = ReceiverState()
    assert s.pending_critical == {}
    assert s.committed_critical == set()
    assert s.crit_nonce_seq == 0


def test_critical_pending_holds_confirm_binding_fields():
    p = CriticalPending(
        epoch=1,
        ctr=7,
        cmd="OPEN",
        payload_hash=b"ab",
        nonce_id=3,
        nonce_r="rr",
        ttl_ticks=20,
        expire_tick=25,
        sender_id=2,
        key_id=5,
    )
    assert p.cmd == "OPEN" and p.payload_hash == b"ab"
    assert p.nonce_id == 3 and p.nonce_r == "rr"
    assert p.expire_tick == 25 and p.sender_id == 2
    assert p.key_id == 5
