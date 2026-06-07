from replay.core.scheduler import Direction, EventScheduler


def _sched():
    return EventScheduler()


def test_tick_monotonic():
    s = _sched()
    assert s.tick() == 1
    assert s.tick() == 2
    assert s.current_tick == 2


def test_due_order_by_tick_then_seq():
    # 同一 current_tick 下，按 (delivery_tick, seq) 升序弹出
    s = _sched()
    s.tick()  # current_tick=1
    s.submit("a", delivery_tick=3)   # seq0
    s.submit("b", delivery_tick=2)   # seq1
    s.submit("c", delivery_tick=2)   # seq2
    assert s.pop_due() == []          # 没有 <=1 的
    s.tick()
    s.tick()                          # current_tick=3
    assert s.pop_due() == ["b", "c", "a"]  # tick2(seq1,seq2) 先于 tick3(seq0)


def test_seq_only_advances_on_submit_not_tick():
    # tick 不推进 seq；两次 submit 的 seq 必须连续
    s = _sched()
    s.tick()
    s.tick()
    s.submit("x", delivery_tick=1)
    s.submit("y", delivery_tick=1)
    # 同 tick，seq 升序 -> x 在 y 前
    assert s.pop_due() == ["x", "y"]


def test_flush_drains_all_remaining():
    s = _sched()
    s.tick()
    s.submit("a", delivery_tick=99)
    s.submit("b", delivery_tick=50)
    assert s.flush() == ["b", "a"]
    assert s.flush() == []


def test_direction_isolation():
    # T2R 与 R2T 互不串扰
    s = _sched()
    s.tick()
    s.submit("down", delivery_tick=1, direction=Direction.T2R)
    s.submit("up", delivery_tick=1, direction=Direction.R2T)
    assert s.pop_due(direction=Direction.T2R) == ["down"]
    assert s.pop_due(direction=Direction.R2T) == ["up"]


def test_ttl_expired_event_dropped_and_counted():
    # expire_tick < current_tick 即过期：不投递，计入 expired_count
    s = _sched()
    s.tick()                                  # current_tick=1
    s.submit("stale", delivery_tick=1, expire_tick=0)   # 0 < 1 -> 过期
    s.submit("fresh", delivery_tick=1, expire_tick=5)
    assert s.pop_due() == ["fresh"]
    assert s.expired_count() == 1


def test_ttl_boundary_not_expired_when_equal():
    # expire_tick == current_tick 仍可投递（过期判定是严格小于）
    s = _sched()
    s.tick()
    s.submit("edge", delivery_tick=1, expire_tick=1)
    assert s.pop_due() == ["edge"]
    assert s.expired_count() == 0
