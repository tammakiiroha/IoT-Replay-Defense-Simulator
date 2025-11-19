"""Simple lossy and reordering channel model."""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field
from typing import List, Tuple

from .types import Frame


@dataclass(order=True)
class ScheduledFrame:
    delivery_tick: int
    # We use a sequence number to ensure stable sort for same tick (FIFO by default)
    seq: int
    frame: Frame = field(compare=False)


class Channel:
    def __init__(self, p_loss: float, p_reorder: float, rng: random.Random):
        self.p_loss = p_loss
        self.p_reorder = p_reorder
        self.rng = rng
        self.pq: List[ScheduledFrame] = []
        self.current_tick = 0
        self.seq_counter = 0

    def send(self, frame: Frame) -> List[Frame]:
        """
        Process a frame transmission.
        Returns a list of frames that arrive at the receiver at this tick.
        """
        self.current_tick += 1
        
        # 1. Loss model
        if self.p_loss > 0 and self.rng.random() < self.p_loss:
            # Dropped
            pass
        else:
            # 2. Delay/Reorder model
            delay = 0
            if self.p_reorder > 0 and self.rng.random() < self.p_reorder:
                # Simple reordering: delay by 1 to 3 ticks
                delay = self.rng.randint(1, 3)
            
            delivery_tick = self.current_tick + delay
            heapq.heappush(
                self.pq, 
                ScheduledFrame(delivery_tick, self.seq_counter, frame)
            )
            self.seq_counter += 1

        # 3. Deliver frames due now (or in the past)
        arrived = []
        while self.pq and self.pq[0].delivery_tick <= self.current_tick:
            sf = heapq.heappop(self.pq)
            arrived.append(sf.frame)
        
        return arrived

    def flush(self) -> List[Frame]:
        """Force deliver all remaining frames (e.g., at end of run)."""
        arrived = []
        while self.pq:
            sf = heapq.heappop(self.pq)
            arrived.append(sf.frame)
        return arrived


def should_drop(probability: float, rng: random.Random) -> bool:
    """Legacy helper for backward compatibility or simple checks."""
    if probability <= 0.0:
        return False
    if probability >= 1.0:
        return True
    return rng.random() < probability
