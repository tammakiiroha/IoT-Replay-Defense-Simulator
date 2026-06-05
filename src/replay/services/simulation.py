"""Simulation-facing application services."""
from __future__ import annotations

from datetime import datetime, timezone

from replay.contracts import (
    SimulationBatchResult,
    SimulationResultRecord,
    SimulationSpec,
    SimulationSpecPublic,
    SweepPoint,
    SweepSpec,
)
from replay.core import Mode, run_many_experiments, run_paired_experiments, run_until_precision


def simulate_batch(spec: SimulationSpec, *, show_progress: bool = False) -> SimulationBatchResult:
    base_config = spec.to_runtime_config()
    modes = [Mode(mode) for mode in spec.modes]
    if spec.target_ci_half_width is not None:
        stats = [
            run_until_precision(
                base_config,
                mode=mode,
                target_half_width=spec.target_ci_half_width,
                max_runs=spec.max_runs,
                seed=spec.seed,
            )[0]
            for mode in modes
        ]
    elif spec.paired:
        stats = run_paired_experiments(
            base_config=base_config,
            modes=modes,
            runs=spec.runs,
            seed=spec.seed,
            show_progress=show_progress,
        )
    else:
        stats = run_many_experiments(
            base_config=base_config,
            modes=modes,
            runs=spec.runs,
            seed=spec.seed,
            show_progress=show_progress,
        )
    return SimulationBatchResult(
        generated_at=datetime.now(timezone.utc),
        config=SimulationSpecPublic.from_spec(spec),
        results=[SimulationResultRecord.from_aggregate(entry) for entry in stats],
        metadata={"mode_count": len(spec.modes)},
    )


def run_sweep(spec: SweepSpec, *, show_progress: bool = False) -> list[SweepPoint]:
    points: list[SweepPoint] = []
    simulation = spec.simulation
    for value in spec.values:
        if spec.sweep_type == "p_loss":
            scenario = simulation.model_copy(
                update={
                    "p_loss": float(value),
                    "p_reorder": (
                        spec.fixed_p_reorder if spec.fixed_p_reorder is not None else 0.0
                    ),
                }
            )
        elif spec.sweep_type == "p_reorder":
            scenario = simulation.model_copy(
                update={
                    "p_reorder": float(value),
                    "p_loss": (
                        spec.fixed_p_loss if spec.fixed_p_loss is not None else 0.10
                    ),
                }
            )
        elif spec.sweep_type == "mac_tag_bits":
            scenario = simulation.model_copy(update={"mac_tag_bits": int(value)})
        else:
            scenario = simulation.model_copy(update={"window_size": int(value)})

        batch = simulate_batch(scenario, show_progress=show_progress)
        for result in batch.results:
            points.append(
                SweepPoint(
                    sweep_type=spec.sweep_type,
                    sweep_value=value,
                    result=result,
                )
            )
    return points
