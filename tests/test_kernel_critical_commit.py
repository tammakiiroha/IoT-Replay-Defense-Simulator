from replay.core.kernel.critical_commit import critical_commit, payload_digest, pid_for


def test_payload_digest_is_16_bytes_and_stable():
    assert isinstance(payload_digest(b"x"), bytes)
    assert payload_digest(b"x") == payload_digest(b"x")
    assert payload_digest(b"x") != payload_digest(b"y")
    assert len(payload_digest(b"x")) == 16


def test_pid_is_deterministic_int_for_same_request():
    ph = payload_digest(b"p")
    a = pid_for(epoch=1, ctr=7, cmd="OPEN", payload_hash=ph)
    b = pid_for(epoch=1, ctr=7, cmd="OPEN", payload_hash=ph)
    assert isinstance(a, int) and a == b
    assert pid_for(epoch=1, ctr=8, cmd="OPEN", payload_hash=ph) != a  # 不同 ctr -> 不同 pid


def test_critical_commit_uses_same_window_commit():
    # critical commit 的窗口更新与 normal accept 完全一致（同 window_commit）
    new_h, mask = critical_commit(n=12, h=10, mask=[1, 0, 0, 0, 0], w=5)
    assert (new_h, mask) == (12, [1, 0, 1, 0, 0])
