"""Closed-form analytic models for HSW-CR (§6.2/§7).

Pure functions with zero engine/state coupling — they take scalar inputs and
return scalar probabilities/window sizes. Used by the dual-verification harness
(`scripts/plot_analytic_vs_mc.py`) and reasoning about window sizing.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping


def a_W(r: int, p_loss: float, w: int) -> float:
    """Lost-frame replay acceptance probability for offset ``r`` (§6.2).

    A frame replayed ``r`` behind the receiver's sliding window of size ``w``:
    - within the window (``0 <= r < w``) it is always acceptable -> ``1.0``;
    - beyond the window it is accepted only if every intervening frame from
      ``w`` through ``r`` was lost -> ``p_loss ** (r - w + 1)``.
    """
    if 0 <= r < w:
        return 1.0
    return p_loss ** (r - w + 1)


def lar_w(w: int, q_reorder: float) -> float:
    """Geometric reorder availability for window size ``w`` -> ``1 - q_reorder**w``."""
    return 1.0 - q_reorder ** w


def p_forge(q: int, tag_bits: int) -> float:
    """MAC forgery ceiling for ``q`` queries against a ``tag_bits``-bit tag."""
    return q / 2 ** tag_bits


def p_compromise(asr: float, n_attack: int) -> float:
    """Probability of at least one success over ``n_attack`` independent attempts."""
    return 1.0 - (1.0 - asr) ** n_attack


def w_star(
    candidate_windows: Iterable[int],
    *,
    q_reorder: float,
    lar_target: float,
    r_normal_by_w: Mapping[int, float],
    r_crit_by_w: Mapping[int, float],
    r_norm_target: float,
    r_crit_target: float,
) -> int | None:
    """Smallest window meeting the LAR floor and the normal/critical risk budgets.

    Iterates ``candidate_windows`` in the given (ascending) order and returns the
    first ``W`` satisfying all three constraints:
    ``lar_w(W, q_reorder) >= lar_target`` and ``r_normal_by_w[W] <= r_norm_target``
    and ``r_crit_by_w[W] <= r_crit_target``. Returns ``None`` if none qualifies.

    ``r_normal_by_w`` / ``r_crit_by_w`` are ``{W: risk}`` maps supplied by the
    caller (risk budgeted from the policy table); this function stays pure.
    """
    for w in candidate_windows:
        if (
            lar_w(w, q_reorder) >= lar_target
            and r_normal_by_w[w] <= r_norm_target
            and r_crit_by_w[w] <= r_crit_target
        ):
            return w
    return None
