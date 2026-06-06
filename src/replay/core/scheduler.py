"""单一事件调度器：统一 Channel/trace 的 (tick, seq) 堆，加 Direction/TTL 基座（§1.5）。"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import Enum


class Direction(str, Enum):
    T2R = "t2r"   # transmitter -> receiver（现有正向）
    R2T = "r2t"   # receiver -> transmitter（resync/challenge 反向，Phase 2 生产者）


@dataclass(order=True)
class Event:
    delivery_tick: int
    seq: int
    direction: Direction = field(default=Direction.T2R, compare=False)
    frame: object = field(default=None, compare=False)
    expire_tick: int | None = field(default=None, compare=False)


class EventScheduler:
    """按方向分队的 (delivery_tick, seq) 优先队列。tick 每次发送尝试 +1；seq 仅入队 +1。"""

    def __init__(self) -> None:
        self.current_tick = 0
        self._seq = 0
        self._queues: dict[Direction, list[Event]] = {Direction.T2R: [], Direction.R2T: []}
        self._expired: dict[Direction, int] = {Direction.T2R: 0, Direction.R2T: 0}

    def tick(self) -> int:
        self.current_tick += 1
        return self.current_tick

    def submit(
        self,
        frame: object,
        *,
        delivery_tick: int,
        direction: Direction = Direction.T2R,
        expire_tick: int | None = None,
    ) -> None:
        heapq.heappush(
            self._queues[direction],
            Event(delivery_tick, self._seq, direction, frame, expire_tick),
        )
        self._seq += 1

    def _drain(self, direction: Direction, due_only: bool) -> list:
        queue = self._queues[direction]
        arrived: list = []
        while queue and (not due_only or queue[0].delivery_tick <= self.current_tick):
            event = heapq.heappop(queue)
            if event.expire_tick is not None and event.expire_tick < self.current_tick:
                self._expired[direction] += 1
                continue
            arrived.append(event.frame)
        return arrived

    def pop_due(self, *, direction: Direction = Direction.T2R) -> list:
        return self._drain(direction, due_only=True)

    def flush(self, *, direction: Direction = Direction.T2R) -> list:
        return self._drain(direction, due_only=False)

    def expired_count(self, direction: Direction = Direction.T2R) -> int:
        return self._expired[direction]
