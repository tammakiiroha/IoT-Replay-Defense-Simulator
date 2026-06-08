"""Controlled Monte-Carlo for the lost-frame replay model (Phase 5 P4).

Reuses the REAL receiver window kernel (``classify`` + ``window_commit``) so the
MC estimates the SAME conditional probability as the analytic ``a_W(r, p_loss, w)``:
``P(replay of an offset-r frame is accepted | sliding window w, channel loss p_loss)``.

Trial model (matches the a_W derivation, §6.2): the receiver has accepted up to
counter ``c-1``; the original frame ``c`` is lost (its window slot stays free);
each of the ``r`` subsequent frames ``c+1..c+r`` is delivered with probability
``1 - p_loss`` and advances the window; finally frame ``c`` is replayed. By the
window kernel the replay is accepted iff none of ``{c+W .. c+r}`` were delivered,
i.e. ``p_loss**(r-w+1)`` for ``r >= w`` and ``1.0`` for ``r < w``.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..kernel.acceptance import SwDecision, classify
from ..kernel.window_commit import window_commit
from ..rng import RandomLike
from ..stats import wilson_ci
from .models import a_W

_ACCEPTED = (SwDecision.ACCEPT_FORWARD, SwDecision.ACCEPT_IN_WINDOW)


def validate_params(r: int, p_loss: float, w: int) -> None:
    """Reject out-of-domain inputs before they reach the analytic/MC code."""
    if r < 0:
        raise ValueError(f"r (offset) must be >= 0, got {r!r}")
    if w < 1:
        raise ValueError(f"w (window size) must be >= 1, got {w!r}")
    if not 0.0 <= p_loss <= 1.0:
        raise ValueError(f"p_loss must be in [0, 1], got {p_loss!r}")


def estimate_accept_rate(
    r: int, p_loss: float, w: int, *, n_trials: int, rng: RandomLike
) -> tuple[int, int]:
    """Estimate ``P(accept | offset=r, window=w, p_loss)`` via the real receiver
    window kernel. Returns ``(accepts, n_trials)`` for downstream Wilson CI."""
    validate_params(r, p_loss, w)
    if n_trials <= 0:
        raise ValueError(f"n_trials must be > 0, got {n_trials!r}")
    c = w  # base counter; c-1 = w-1 >= 0 keeps every counter non-negative
    accepts = 0
    for _ in range(n_trials):
        h = c - 1
        mask = [0] * w
        mask[0] = 1  # receiver accepted counter c-1 (window top); c itself is lost
        for i in range(1, r + 1):
            if rng.random() < p_loss:
                continue  # subsequent legit frame c+i lost on the channel
            n = c + i
            if classify(n, h, mask, w) is SwDecision.ACCEPT_FORWARD:
                h, mask = window_commit(n, h, mask, w)
        # replay the original (lost) frame c through the same window kernel
        if classify(c, h, mask, w) in _ACCEPTED:
            accepts += 1
    return accepts, n_trials


@dataclass(frozen=True)
class VerifyPoint:
    """One (r, w, p_loss) dual-verification sample: analytic vs MC + Wilson CI."""

    r: int
    w: int
    p_loss: float
    analytic: float
    mc_mean: float
    ci_lower: float
    ci_upper: float
    n_trials: int
    within_ci: bool


def verify_point(
    r: int, p_loss: float, w: int, *, n_trials: int, rng: RandomLike
) -> VerifyPoint:
    """Compare analytic ``a_W`` to a controlled MC estimate at one grid point."""
    accepts, n = estimate_accept_rate(r, p_loss, w, n_trials=n_trials, rng=rng)
    ci = wilson_ci(accepts, n)
    analytic = a_W(r, p_loss, w)
    mc_mean = accepts / n
    # Deterministic points (r < w, or p_loss in {0, 1}) agree exactly; the Wilson
    # interval is degenerate at p_hat in {0, 1} (it never reaches the 0/1 boundary),
    # so accept exact agreement OR analytic inside the CI.
    within_ci = mc_mean == analytic or ci.lower <= analytic <= ci.upper
    return VerifyPoint(
        r=r,
        w=w,
        p_loss=p_loss,
        analytic=analytic,
        mc_mean=mc_mean,
        ci_lower=ci.lower,
        ci_upper=ci.upper,
        n_trials=n,
        within_ci=within_ci,
    )


def dual_verification(
    r_grid: Iterable[int],
    w_grid: Iterable[int],
    p_loss_values: Iterable[float],
    *,
    n_trials: int,
    rng: RandomLike,
) -> list[VerifyPoint]:
    """Run ``verify_point`` over the full ``(w, p_loss, r)`` grid."""
    results: list[VerifyPoint] = []
    for w in w_grid:
        for p_loss in p_loss_values:
            for r in r_grid:
                results.append(verify_point(r, p_loss, w, n_trials=n_trials, rng=rng))
    return results
