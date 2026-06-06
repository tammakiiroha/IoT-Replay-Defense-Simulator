"""Energy/bandwidth/latency proxy model for low-cost IoT constraints."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    tx_energy_per_byte: float = 1.0
    rx_energy_per_byte: float = 0.8
    hmac_energy: float = 5.0
    ascon_energy: float = 4.0
    state_byte_cost: float = 0.01


@dataclass
class CostStats:
    tx_bytes: int = 0
    rx_bytes: int = 0
    hmac_ops: int = 0
    ascon_ops: int = 0
    state_bytes_peak: int = 0
    challenge_round_trips: int = 0
    latency_ticks_sum: int = 0
    accepted_frames: int = 0
    resync_initiated: int = 0
    resync_completed: int = 0
    resync_timeout: int = 0
    crit_prepared: int = 0
    crit_committed: int = 0
    crit_rejected: int = 0


def estimate_energy(stats: CostStats, model: CostModel | None = None) -> float:
    model = model or CostModel()
    return (
        stats.tx_bytes * model.tx_energy_per_byte
        + stats.rx_bytes * model.rx_energy_per_byte
        + stats.hmac_ops * model.hmac_energy
        + stats.ascon_ops * model.ascon_energy
        + stats.state_bytes_peak * model.state_byte_cost
    )
