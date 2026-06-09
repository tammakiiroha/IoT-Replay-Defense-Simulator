"""Closed-form analytic models — pure-function math boundaries (Phase 5 P0)."""
import pytest

from replay.core.analytic.models import (
    a_W,
    lar_w,
    p_compromise,
    p_forge,
    w_star,
)

# --- a_W: lost-frame replay acceptance probability (§6.2) ---


def test_a_w_within_window_is_one():
    # 0 <= r < w  ->  always acceptable
    assert a_W(0, 0.3, 5) == 1.0
    assert a_W(4, 0.3, 5) == 1.0


def test_a_w_at_window_edge_equals_p_loss():
    # r == w  ->  p_loss**(r-w+1) == p_loss**1
    assert a_W(5, 0.3, 5) == pytest.approx(0.3)


def test_a_w_beyond_window_is_p_loss_power():
    # r > w  ->  p_loss**(r-w+1)
    assert a_W(7, 0.3, 5) == pytest.approx(0.3 ** 3)


def test_a_w_monotone_non_increasing_in_r():
    vals = [a_W(r, 0.4, 4) for r in range(0, 10)]
    assert all(earlier >= later for earlier, later in zip(vals, vals[1:]))


def test_a_w_p_loss_zero_rejects_beyond_window():
    # p_loss == 0  ->  no lost subsequent frame  ->  0 beyond window
    assert a_W(6, 0.0, 4) == 0.0
    assert a_W(3, 0.0, 4) == 1.0


# --- lar_w: geometric reorder availability ---


def test_lar_w_monotone_increasing_in_w():
    vals = [lar_w(w, 0.5) for w in range(1, 8)]
    assert all(earlier < later for earlier, later in zip(vals, vals[1:]))


def test_lar_w_values():
    assert lar_w(1, 0.5) == pytest.approx(0.5)
    assert lar_w(3, 0.5) == pytest.approx(0.875)


def test_lar_w_zero_window_is_zero():
    assert lar_w(0, 0.5) == pytest.approx(0.0)


# --- p_forge: MAC forgery ceiling ---


def test_p_forge_dimensional():
    assert p_forge(1, 64) == pytest.approx(1.0 / 2 ** 64)
    assert p_forge(8, 32) == pytest.approx(8.0 / 2 ** 32)


# --- p_compromise: at-least-one success over N attempts ---


def test_p_compromise_single_attempt_equals_asr():
    assert p_compromise(0.2, 1) == pytest.approx(0.2)


def test_p_compromise_increases_with_n():
    vals = [p_compromise(0.2, n) for n in range(1, 8)]
    assert all(earlier < later for earlier, later in zip(vals, vals[1:]))


def test_p_compromise_zero_asr_is_zero():
    assert p_compromise(0.0, 100) == 0.0


# --- w_star: smallest window meeting LAR + risk constraints ---

_CANDS = [1, 2, 3, 4, 5]
_R_NORMAL = {1: 0.1, 2: 0.2, 3: 0.3, 4: 0.4, 5: 0.5}
_R_CRIT = {1: 0.01, 2: 0.02, 3: 0.03, 4: 0.04, 5: 0.05}


def test_w_star_returns_smallest_feasible():
    # lar(>=0.85) -> w>=3 ; r_normal(<=0.45) -> w<=4 ; r_crit(<=0.035) -> w<=3  => 3
    assert (
        w_star(
            _CANDS,
            q_reorder=0.5,
            lar_target=0.85,
            r_normal_by_w=_R_NORMAL,
            r_crit_by_w=_R_CRIT,
            r_norm_target=0.45,
            r_crit_target=0.035,
        )
        == 3
    )


def test_w_star_lar_constraint_binds():
    # lar(>=0.93) -> w>=4 ; risks allow up to 4  => 4
    assert (
        w_star(
            _CANDS,
            q_reorder=0.5,
            lar_target=0.93,
            r_normal_by_w=_R_NORMAL,
            r_crit_by_w=_R_CRIT,
            r_norm_target=0.45,
            r_crit_target=0.045,
        )
        == 4
    )


def test_w_star_no_feasible_returns_none():
    # lar(>=0.96) -> w>=5 ; r_crit(<=0.035) -> w<=3  => conflict => None
    assert (
        w_star(
            _CANDS,
            q_reorder=0.5,
            lar_target=0.96,
            r_normal_by_w=_R_NORMAL,
            r_crit_by_w=_R_CRIT,
            r_norm_target=0.45,
            r_crit_target=0.035,
        )
        is None
    )


def test_w_star_crit_constraint_binds():
    # lar(>=0.85) -> w>=3 ; r_crit(<=0.025) -> w<=2  => conflict => None
    assert (
        w_star(
            _CANDS,
            q_reorder=0.5,
            lar_target=0.85,
            r_normal_by_w=_R_NORMAL,
            r_crit_by_w=_R_CRIT,
            r_norm_target=0.5,
            r_crit_target=0.025,
        )
        is None
    )
