from replay.core.types import Frame


def test_frame_has_critical_flag_constants():
    assert Frame.FLAG_NORMAL_REQ == 0
    assert Frame.FLAG_CRIT_PREPARE == 1
    assert Frame.FLAG_CRIT_CONFIRM == 2
    assert Frame.FLAG_RESYNC_CHALLENGE == 3
    assert Frame.FLAG_RESYNC_CONFIRM == 4
    assert Frame.FLAG_CRIT_CHALLENGE == 5


def test_frame_carrier_fields_default_empty():
    f = Frame(command="OPEN")
    assert f.pid == 0
    assert f.nonce_id == 0
    assert f.payload_hash == b""


def test_clone_copies_critical_carrier_fields():
    f = Frame(
        command="OPEN",
        counter=7,
        flags=Frame.FLAG_CRIT_CHALLENGE,
        pid=12345,
        nonce_id=3,
        payload_hash=b"\x01\x02\x03",
    )
    c = f.clone()
    assert c.pid == 12345
    assert c.nonce_id == 3
    assert c.payload_hash == b"\x01\x02\x03"
    assert c.flags == Frame.FLAG_CRIT_CHALLENGE
