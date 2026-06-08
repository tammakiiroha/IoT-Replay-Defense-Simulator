#!/usr/bin/env python
"""Dual-verification artifact: analytic a_W vs controlled Monte-Carlo (Phase 5 P4).

Writes a machine-checkable JSON (always) and, when matplotlib is available, an
overlay plot (analytic curve vs MC scatter with 95% Wilson CI). The JSON's
``all_within_ci`` flag is the falsifiable acceptance signal.

Run: PYTHONPATH=src:. python scripts/plot_analytic_vs_mc.py --out artifacts/analytic_vs_mc
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from replay.core.analytic.mc import VerifyPoint, dual_verification
from replay.core.rng import DeterministicRNG

R_GRID = [0, 1, 2, 3, 4, 6, 8]
W_GRID = [1, 2, 3, 4, 5, 6, 8, 12]
P_LOSS_VALUES = [0.1, 0.3, 0.5]
DEFAULT_N_TRIALS = 4000
DEFAULT_SEED = 20240608


def run(
    out_dir,
    *,
    r_grid=R_GRID,
    w_grid=W_GRID,
    p_loss_values=P_LOSS_VALUES,
    n_trials=DEFAULT_N_TRIALS,
    seed=DEFAULT_SEED,
):
    """Run the dual verification grid and write JSON (+ optional plot). Returns the JSON path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = DeterministicRNG(seed)
    points = dual_verification(
        list(r_grid), list(w_grid), list(p_loss_values), n_trials=n_trials, rng=rng
    )
    n_within = sum(1 for p in points if p.within_ci)
    n_points = len(points)
    payload = {
        "n_trials": n_trials,
        "seed": seed,
        "r_grid": list(r_grid),
        "w_grid": list(w_grid),
        "p_loss_values": list(p_loss_values),
        "points": [asdict(p) for p in points],
        "all_within_ci": n_within == n_points,
        "within_ci_count": n_within,
        "within_ci_fraction": n_within / n_points if n_points else 1.0,
        # A correct 95% CI is EXPECTED to miss ~5% of points; over a grid require the
        # empirical coverage to be statistically consistent with 95% (>= 0.90 leaves
        # ample room for binomial spread, while catching a genuinely broken model).
        "verified": (n_within / n_points if n_points else 1.0) >= 0.90,
    }
    json_path = out_dir / "analytic_vs_mc.json"
    json_path.write_text(json.dumps(payload, indent=2))
    _maybe_plot(out_dir, points, list(w_grid), list(p_loss_values))
    return json_path


def _maybe_plot(out_dir: Path, points: list[VerifyPoint], w_grid, p_loss_values) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return  # matplotlib is an optional ("figures") extra; JSON is the core artifact
    w_focus = w_grid[len(w_grid) // 2]
    fig, axes = plt.subplots(
        1, len(p_loss_values), figsize=(5 * len(p_loss_values), 4), squeeze=False
    )
    for ax, p_loss in zip(axes[0], p_loss_values):
        sel = sorted(
            (pt for pt in points if pt.w == w_focus and pt.p_loss == p_loss),
            key=lambda pt: pt.r,
        )
        rs = [pt.r for pt in sel]
        ax.plot(rs, [pt.analytic for pt in sel], "-", label="analytic a_W")
        ax.errorbar(
            rs,
            [pt.mc_mean for pt in sel],
            yerr=[
                # Wilson CI is not centered on p_hat (and rounds at the 0/1 boundary),
                # so clamp the asymmetric error bars to non-negative for matplotlib.
                [max(0.0, pt.mc_mean - pt.ci_lower) for pt in sel],
                [max(0.0, pt.ci_upper - pt.mc_mean) for pt in sel],
            ],
            fmt="o",
            capsize=3,
            label="MC (95% CI)",
        )
        ax.set_title(f"p_loss={p_loss}, W={w_focus}")
        ax.set_xlabel("offset r")
        ax.set_ylabel("accept prob")
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "analytic_vs_mc.png", dpi=150)
    fig.savefig(out_dir / "analytic_vs_mc.svg")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analytic vs Monte-Carlo dual verification")
    parser.add_argument("--out", default="artifacts/analytic_vs_mc", help="output directory")
    parser.add_argument("--n-trials", type=int, default=DEFAULT_N_TRIALS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    json_path = run(args.out, n_trials=args.n_trials, seed=args.seed)
    payload = json.loads(json_path.read_text())
    status = "PASS" if payload["verified"] else "FAIL"
    print(
        f"[{status}] wrote {json_path} "
        f"({payload['within_ci_count']}/{len(payload['points'])} within 95% CI, "
        f"fraction={payload['within_ci_fraction']:.3f})"
    )


if __name__ == "__main__":
    main()
