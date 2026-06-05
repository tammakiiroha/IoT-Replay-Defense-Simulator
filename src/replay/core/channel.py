"""Simple lossy and reordering channel model."""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from .channel_models import DelayModel, IidLoss, LossModel, ReorderDelay
from .rng import RandomLike
from .types import Frame


@dataclass(order=True)
class ScheduledFrame:
    delivery_tick: int
    seq: int
    frame: Frame = field(compare=False)


class Channel:
    def __init__(
        self,
        p_loss: float = 0.0,
        p_reorder: float = 0.0,
        rng: RandomLike | None = None,
        *,
        loss_model: LossModel | None = None,
        delay_model: DelayModel | None = None,
    ):
        self.p_loss = p_loss
        self.p_reorder = p_reorder
        self.rng = rng
        self.loss_model = loss_model if loss_model is not None else IidLoss(p_loss)
        self.delay_model = delay_model if delay_model is not None else ReorderDelay(p_reorder)
        self.pq: list[ScheduledFrame] = []
        self.current_tick = 0
        self.seq_counter = 0

    def send(self, frame: Frame) -> list[Frame]:
        """Process a frame transmission and return frames delivered at this tick."""

        self.current_tick += 1
        if self.rng is None:
            raise ValueError("Channel requires an RNG")
        if self.loss_model.dropped(self.rng):
            pass
        else:
            delay = self.delay_model.delay(self.rng)
            delivery_tick = self.current_tick + delay
            heapq.heappush(self.pq, ScheduledFrame(delivery_tick, self.seq_counter, frame))
            self.seq_counter += 1

        arrived: list[Frame] = []
        while self.pq and self.pq[0].delivery_tick <= self.current_tick:
            arrived.append(heapq.heappop(self.pq).frame)
        return arrived

    def flush(self) -> list[Frame]:
        """Force deliver all remaining frames."""

        arrived: list[Frame] = []
        while self.pq:
            arrived.append(heapq.heappop(self.pq).frame)
        return arrived


def should_drop(probability: float, rng: RandomLike) -> bool:
    """Legacy helper for backward compatibility or simple checks."""

    if probability <= 0.0:
        return False
    if probability >= 1.0:
        return True
    return rng.random() < probability
