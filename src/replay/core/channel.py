"""Simple lossy and reordering channel model."""
from __future__ import annotations

from dataclasses import dataclass, field

from .channel_models import DelayModel, IidLoss, LossModel, ReorderDelay
from .rng import RandomLike
from .scheduler import EventScheduler
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
        self._scheduler = EventScheduler()

    @property
    def current_tick(self) -> int:
        """Read-only view of the internal scheduler tick (backward-compatible attribute)."""
        return self._scheduler.current_tick

    def send(self, frame: Frame) -> list[Frame]:
        """Process a frame transmission and return frames delivered at this tick."""

        tick = self._scheduler.tick()
        if self.rng is None:
            raise ValueError("Channel requires an RNG")
        if self.loss_model.dropped(self.rng):
            pass
        else:
            delay = self.delay_model.delay(self.rng)
            self._scheduler.submit(frame, delivery_tick=tick + delay)
        return self._scheduler.pop_due()

    def flush(self) -> list[Frame]:
        """Force deliver all remaining frames."""

        return self._scheduler.flush()


def should_drop(probability: float, rng: RandomLike) -> bool:
    """Legacy helper for backward compatibility or simple checks."""

    if probability <= 0.0:
        return False
    if probability >= 1.0:
        return True
    return rng.random() < probability
