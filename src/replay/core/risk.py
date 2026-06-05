"""Adaptive risk scoring for hybrid replay-defense selection."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskContext:
    command: str
    counter_gap: int
    duplicate_rate: float
    recent_loss_rate: float
    recent_reorder_rate: float
    is_high_value_state: bool


@dataclass(frozen=True)
class RiskWeights:
    command: float = 0.55
    anomaly: float = 0.20
    channel: float = 0.15
    state: float = 0.10


def compute_risk(
    ctx: RiskContext,
    command_risk: dict[str, float],
    weights: RiskWeights | None = None,
) -> float:
    weights = weights or RiskWeights()
    command_score = command_risk.get(ctx.command, 0.0)
    anomaly_score = min(1.0, max(ctx.counter_gap, 0) / 10.0 + ctx.duplicate_rate)
    channel_score = min(1.0, ctx.recent_loss_rate + ctx.recent_reorder_rate)
    state_score = 1.0 if ctx.is_high_value_state else 0.0
    return min(
        1.0,
        command_score * weights.command
        + anomaly_score * weights.anomaly
        + channel_score * weights.channel
        + state_score * weights.state,
    )


def choose_defense_mode(risk: float, low: float = 0.4, high: float = 0.8) -> str:
    if risk >= high:
        return "challenge"
    if risk >= low:
        return "lockdown"
    return "window"
