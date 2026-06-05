"""Defense-parameter advisor for device profiles."""
from __future__ import annotations

from dataclasses import dataclass, field

from replay.contracts import SimulationSpec
from replay.core import Mode
from replay.services.simulation import simulate_batch


@dataclass(frozen=True)
class DeviceProfile:
    commands: list[str]
    command_risk: dict[str, float]
    p_loss: float
    p_reorder: float
    ram_budget_bytes: int
    max_latency_ticks: int
    target_asr: float = 0.05
    seed: int | None = None


@dataclass(frozen=True)
class Recommendation:
    mode: str
    window_size: int
    mac_tag_bits: int
    challenge_for: list[str] = field(default_factory=list)
    predicted_lar: float = 0.0
    predicted_asr: float = 1.0
    energy_proxy: float = 0.0
    state_bytes: float = 0.0
    latency_ticks: float = 0.0
    constraint_status: str = "met"


def recommend(device_profile: DeviceProfile) -> Recommendation:
    high_risk_commands = [
        command for command, risk in device_profile.command_risk.items() if risk >= 0.8
    ]
    candidates: list[Recommendation] = []

    for mode in ["window", "hsw_cr", "oscore_like"]:
        for window_size in [3, 5, 8, 16]:
            for tag_bits in [80, 96, 128]:
                spec = SimulationSpec(
                    modes=[Mode(mode)],
                    runs=50,
                    num_legit=20,
                    num_replay=50,
                    seed=device_profile.seed,
                    p_loss=device_profile.p_loss,
                    p_reorder=device_profile.p_reorder,
                    window_size=window_size,
                    mac_tag_bits=tag_bits,
                    command_set=device_profile.commands,
                    command_risk=device_profile.command_risk,
                    target_commands=high_risk_commands or None,
                    paired=True,
                )
                result = simulate_batch(spec, show_progress=False).results[0]
                rec = Recommendation(
                    mode=mode,
                    window_size=window_size,
                    mac_tag_bits=tag_bits,
                    challenge_for=high_risk_commands if mode == "hsw_cr" else [],
                    predicted_lar=result.avg_legit_rate,
                    predicted_asr=result.avg_attack_rate,
                    energy_proxy=result.energy_proxy,
                    state_bytes=result.state_bytes,
                    latency_ticks=result.latency_ticks,
                    constraint_status="met",
                )
                candidates.append(rec)

    feasible = [
        rec
        for rec in candidates
        if rec.state_bytes <= device_profile.ram_budget_bytes
        and rec.latency_ticks <= device_profile.max_latency_ticks
    ]
    pool = feasible or candidates
    meeting_target = [rec for rec in pool if rec.predicted_asr <= device_profile.target_asr]
    if high_risk_commands:
        hsw_target = [rec for rec in meeting_target if rec.mode == "hsw_cr"]
        if hsw_target:
            return min(hsw_target, key=lambda rec: (rec.energy_proxy, rec.state_bytes))
    if meeting_target:
        return min(meeting_target, key=lambda rec: (rec.energy_proxy, rec.state_bytes))

    best = min(pool, key=lambda rec: (rec.predicted_asr, rec.energy_proxy, rec.state_bytes))
    return Recommendation(
        mode=best.mode,
        window_size=best.window_size,
        mac_tag_bits=best.mac_tag_bits,
        challenge_for=best.challenge_for,
        predicted_lar=best.predicted_lar,
        predicted_asr=best.predicted_asr,
        energy_proxy=best.energy_proxy,
        state_bytes=best.state_bytes,
        latency_ticks=best.latency_ticks,
        constraint_status="best_effort",
    )
