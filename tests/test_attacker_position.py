"""Attacker position x strength channel mapping (Phase 5 P2).

Default (ind, strong) must be byte-for-byte the legacy baseline; tx/rx/weak are
opt-in. tx/rx recording policy is unit-tested via the paired helper; weak is the
appended attack-only extra drop that never touches the legit path.
"""
import json
from pathlib import Path

from replay.core import (
    Mode,
    SimulationConfig,
    run_paired_experiments,
)
from replay.core.experiment import _should_record_paired
from replay.core.trace import generate_trace
from replay.core.types import AttackMode

_BASELINE = json.loads(Path("tests/fixtures/engine_baseline.json").read_text())
SEED = _BASELINE["seed"]
RUNS = _BASELINE["runs"]
STABLE_MODES = [
    Mode.NO_DEFENSE,
    Mode.ROLLING_MAC,
    Mode.WINDOW,
    Mode.CHALLENGE,
    Mode.OSCORE_LIKE,
]


def _base(**overrides) -> SimulationConfig:
    params = dict(
        mode=Mode.NO_DEFENSE,
        attack_mode=AttackMode.POST_RUN,
        num_legit=20,
        num_replay=30,
        p_loss=0.1,
        p_reorder=0.1,
        window_size=5,
        g_hard=16,
        rng_seed=SEED,
        command_set=["UNLOCK", "LOCK", "PING"],
        command_risk={"UNLOCK": 1.0},
        risk_high=0.8,
    )
    params.update(overrides)
    return SimulationConfig(**params)


def _snap(stats_list) -> dict:
    return {
        str(s.mode): {
            "legit_accepted": s.legit_accepted,
            "legit_total": s.legit_total,
            "attack_accepted": s.attack_accepted,
            "attack_total": s.attack_total,
        }
        for s in stats_list
    }


# --- (1) default ind/strong == legacy frozen baseline ---


def test_default_ind_strong_matches_legacy_baseline():
    cfg = _base(attacker_position="ind", attacker_inject_strength="strong")
    got = _snap(
        run_paired_experiments(
            cfg, modes=STABLE_MODES, runs=RUNS, seed=SEED, show_progress=False
        )
    )
    expected = {m: _BASELINE["cases"]["paired/post"][m] for m in got}
    assert got == expected
    # the new fields must default to ind/strong
    assert SimulationConfig(mode=Mode.NO_DEFENSE).attacker_position == "ind"
    assert SimulationConfig(mode=Mode.NO_DEFENSE).attacker_inject_strength == "strong"


# --- (2) tx records even when the legit frame was lost (P_record=1.0) ---


def test_tx_records_even_when_legit_frame_is_lost():
    # tx ignores both delivery loss and record loss
    assert _should_record_paired("tx", legit_dropped=True, record_dropped=True) is True
    assert _should_record_paired("tx", legit_dropped=False, record_dropped=True) is True
    # ind still honours record loss (sanity: not always-true)
    assert _should_record_paired("ind", legit_dropped=True, record_dropped=True) is False
    assert _should_record_paired("ind", legit_dropped=True, record_dropped=False) is True


# --- (3) rx records only frames the receiver actually got ---


def test_rx_records_only_delivered():
    # delivered + not record-dropped -> recorded
    assert _should_record_paired("rx", legit_dropped=False, record_dropped=False) is True
    # not delivered -> never recorded, regardless of record loss
    assert _should_record_paired("rx", legit_dropped=True, record_dropped=False) is False
    assert _should_record_paired("rx", legit_dropped=True, record_dropped=True) is False
    # delivered but record-dropped -> not recorded
    assert _should_record_paired("rx", legit_dropped=False, record_dropped=True) is False


# --- (4) weak appends an attack-only extra drop; legit path untouched ---


def test_weak_extra_drop_appended_no_baseline_drift():
    cfg = _base(attack_mode=AttackMode.INLINE, num_replay=30)
    trace = generate_trace(cfg, seed=SEED)
    # new appended array exists, correct length, all bool
    assert hasattr(trace, "attack_extra_dropped")
    assert len(trace.attack_extra_dropped) == cfg.num_replay
    assert all(isinstance(x, bool) for x in trace.attack_extra_dropped)

    strong = run_paired_experiments(
        _base(attack_mode=AttackMode.INLINE, attacker_inject_strength="strong"),
        modes=[Mode.NO_DEFENSE],
        runs=RUNS,
        seed=SEED,
        show_progress=False,
    )[0]
    weak = run_paired_experiments(
        _base(attack_mode=AttackMode.INLINE, attacker_inject_strength="weak"),
        modes=[Mode.NO_DEFENSE],
        runs=RUNS,
        seed=SEED,
        show_progress=False,
    )[0]
    # legit path identical (weak only touches attack delivery)
    assert weak.legit_accepted == strong.legit_accepted
    assert weak.legit_total == strong.legit_total
    # extra attack-only drop can only reduce (or equal) delivered attacks
    assert weak.attack_accepted <= strong.attack_accepted
    assert weak.attack_total == strong.attack_total
