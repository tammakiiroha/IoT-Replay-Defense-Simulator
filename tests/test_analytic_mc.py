"""Analytic vs controlled Monte-Carlo dual verification (Phase 5 P4).

The MC harness reuses the REAL receiver window kernel (classify + window_commit)
so it estimates the SAME conditional probability as the analytic a_W(r, p_loss, w).
Model: receiver accepted up to c-1; frame c is lost; c+1..c+r delivered with
prob (1-p_loss); then c is replayed. Accept iff none of {c+W..c+r} delivered.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from replay.core.analytic.mc import estimate_accept_rate
from replay.core.analytic.models import a_W
from replay.core.rng import DeterministicRNG
from replay.core.stats import wilson_ci


def test_mc_harness_nonzero_for_r_ge_W():
    # r >= W must NOT be a guaranteed reject (the fixed-h bug gave 0); ~ p_loss^(r-w+1)
    accepts, n = estimate_accept_rate(6, 0.5, 4, n_trials=3000, rng=DeterministicRNG(1))
    assert n == 3000
    assert accepts > 0


def test_mc_harness_matches_a_w_within_95ci():
    points = [
        (0, 0.3, 3),  # r < w -> 1.0
        (3, 0.3, 5),  # r < w -> 1.0
        (1, 0.6, 1),  # r == w -> p_loss
        (4, 0.4, 4),  # r == w -> p_loss
        (5, 0.5, 3),  # r > w -> p_loss**(r-w+1)
        (6, 0.3, 4),  # r > w
    ]
    rng = DeterministicRNG(20240608)
    for r, p, w in points:
        accepts, n = estimate_accept_rate(r, p, w, n_trials=4000, rng=rng)
        ci = wilson_ci(accepts, n)
        analytic = a_W(r, p, w)
        mc_mean = accepts / n
        # exact agreement (deterministic points) OR analytic within the Wilson 95% CI
        within = mc_mean == analytic or ci.lower <= analytic <= ci.upper
        assert within, (r, p, w, analytic, mc_mean, ci.lower, ci.upper, accepts)


def test_mc_harness_rejects_invalid_parameters():
    rng = DeterministicRNG(0)
    with pytest.raises(ValueError):
        estimate_accept_rate(-1, 0.3, 4, n_trials=10, rng=rng)
    with pytest.raises(ValueError):
        estimate_accept_rate(2, 0.3, 0, n_trials=10, rng=rng)
    with pytest.raises(ValueError):
        estimate_accept_rate(2, 1.5, 4, n_trials=10, rng=rng)
    with pytest.raises(ValueError):
        estimate_accept_rate(2, -0.1, 4, n_trials=10, rng=rng)


def test_plot_analytic_vs_mc_smoke_outputs_file(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "plot_analytic_vs_mc", "scripts/plot_analytic_vs_mc.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    json_path = Path(
        mod.run(
            tmp_path,
            r_grid=[0, 2, 4],
            w_grid=[3],
            p_loss_values=[0.3],
            n_trials=200,
            seed=7,
        )
    )
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["points"]
    assert data["all_within_ci"] is True
