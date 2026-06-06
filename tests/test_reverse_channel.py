from replay.core.scheduler import Direction, EventScheduler


def test_r2t_event_delivered_at_tick_to_sender_side():
    s = EventScheduler()
    s.tick()                                       # current_tick=1
    s.submit("RESYNC_CHALLENGE", delivery_tick=2, direction=Direction.R2T)
    assert s.pop_due(direction=Direction.R2T) == []   # tick=1，未到
    s.tick()                                       # current_tick=2
    assert s.pop_due(direction=Direction.R2T) == ["RESYNC_CHALLENGE"]


def test_r2t_does_not_leak_into_t2r_stream():
    s = EventScheduler()
    s.tick()
    s.submit("RESYNC_CHALLENGE", delivery_tick=1, direction=Direction.R2T)
    assert s.pop_due(direction=Direction.T2R) == []     # 正向流不受反向事件污染
    assert s.pop_due(direction=Direction.R2T) == ["RESYNC_CHALLENGE"]


def test_r2t_ttl_expiry_drops_challenge():
    s = EventScheduler()
    s.tick()
    s.tick()                                       # current_tick=2
    # delivery_tick=1, expire_tick=1 -> 1 < 2 过期
    s.submit("RESYNC_CHALLENGE", delivery_tick=1, direction=Direction.R2T, expire_tick=1)
    assert s.pop_due(direction=Direction.R2T) == []
    assert s.expired_count(Direction.R2T) == 1
