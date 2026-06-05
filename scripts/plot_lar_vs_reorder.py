#!/usr/bin/env python3
"""Generate LAR-vs-reordering benchmark figure."""
from __future__ import annotations

from pathlib import Path

from replay.contracts import SimulationSpec, SweepSpec
from replay.services.simulation import run_sweep


def main() -> int:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("Install matplotlib or run `pip install -e '.[figures]'`.") from exc

    spec = SweepSpec(
        sweep_type="p_reorder",
        values=[0.0, 0.1, 0.2, 0.3],
        fixed_p_loss=0.0,
        simulation=SimulationSpec(
            modes=["rolling", "window", "challenge", "hsw_cr", "oscore_like"],
            runs=40,
            seed=11,
            window_size=8,
            num_legit=20,
            num_replay=30,
            command_risk={"UNLOCK": 1.0},
            command_set=["PING", "STATUS", "LOCK", "UNLOCK"],
            paired=True,
        ),
    )
    points = run_sweep(spec, show_progress=False)
    modes = sorted({point.result.mode for point in points})

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for mode in modes:
        rows = [point for point in points if point.result.mode == mode]
        xs = [point.sweep_value for point in rows]
        ys = [point.result.avg_legit_rate for point in rows]
        low = [max(0.0, y - point.result.lar_ci_low) for y, point in zip(ys, rows)]
        high = [max(0.0, point.result.lar_ci_high - y) for y, point in zip(ys, rows)]
        ax.errorbar(xs, ys, yerr=[low, high], marker="o", linewidth=1.8, label=mode)

    ax.set_title("Legitimate acceptance under reordering")
    ax.set_xlabel("Reorder probability")
    ax.set_ylabel("LAR")
    ax.set_ylim(-0.03, 1.03)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    output = Path("docs/figures/lar_vs_reorder.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
