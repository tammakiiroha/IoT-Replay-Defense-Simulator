from sim.types import Frame


def test_new_fields_default_and_clone():
    f = Frame(command="OPEN", counter=7, epoch=1, dev_id=2, key_id=0, flags=0, payload=b"\x01")
    assert f.epoch == 1 and f.dev_id == 2 and f.flags == 0 and f.payload == b"\x01"
    c = f.clone()
    assert c.epoch == 1 and c.dev_id == 2 and c.payload == b"\x01"
    assert c == f


def test_backward_compatible_minimal_frame():
    f = Frame(command="PING")
    assert f.epoch == 0 and f.dev_id == 0 and f.key_id == 0 and f.flags == 0 and f.payload == b""
