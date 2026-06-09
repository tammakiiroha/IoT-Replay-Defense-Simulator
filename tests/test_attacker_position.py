"""Attacker position x strength channel mapping (Phase 5 P2).

Default (ind, strong) must be byte-for-byte the legacy baseline; tx/rx/weak are
opt-in. tx/rx recording policy is unit-tested via the paired helper; weak is the
appended attack-only extra drop that never touches the legit path.
"""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from replay.core import (
    Mode,
    SimulationConfig,
    run_paired_experiments,
)
from replay.core.experiment import _should_record_paired, simulate_one_run_with_trace
from replay.core.trace import ScenarioTrace, generate_trace
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
    cfg = _base(attack_mode=AttackMode.INLINE, num_replay=30, attacker_inject_strength="weak")
    trace = generate_trace(cfg, seed=SEED)
    # weak appends the attack-only extra-drop array
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


# --- (5) paired rx records at DELIVERY, not at send (delayed frame must wait) ---


def _single_frame_trace(*, legit_delay: int) -> ScenarioTrace:
    return ScenarioTrace(
        commands=["PING"],
        legit_dropped=[False],
        legit_delay=[legit_delay],
        attacker_record_dropped=[False],
        inline_attempt=[True],
        replay_pick=[0],
        replay_dropped=[False],
        replay_delay=[0],
    )


def _rx_inline_cfg() -> SimulationConfig:
    return SimulationConfig(
        mode=Mode.NO_DEFENSE,
        attack_mode=AttackMode.INLINE,
        num_legit=1,
        num_replay=1,
        window_size=0,
        g_hard=16,
        command_set=["PING"],
        attacker_position="rx",
    )


def test_paired_rx_does_not_record_delayed_frame_before_delivery():
    # delayed legit frame is not yet delivered at the inline replay -> nothing to replay
    delayed = simulate_one_run_with_trace(_rx_inline_cfg(), _single_frame_trace(legit_delay=3))
    assert delayed.attack_attempts == 0
    # control: same-tick delivery -> recorded at delivery, replay can attempt
    immediate = simulate_one_run_with_trace(_rx_inline_cfg(), _single_frame_trace(legit_delay=0))
    assert immediate.attack_attempts == 1


# --- (6) default/strong trace keeps legacy digest shape (no attack_extra_dropped) ---


def test_strong_trace_digest_omits_attack_extra_drop_field():
    tr = generate_trace(_base(attacker_inject_strength="strong"), seed=SEED)
    assert tr.attack_extra_dropped == []
    # digest must equal the legacy-shape digest (empty field popped from the payload)
    data = asdict(tr)
    data.pop("attack_extra_dropped")
    expected = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    assert tr.digest() == expected


def test_weak_trace_has_attack_extra_drop_field():
    cfg = _base(attacker_inject_strength="weak", num_replay=12)
    tr = generate_trace(cfg, seed=SEED)
    assert len(tr.attack_extra_dropped) == cfg.num_replay
    assert all(isinstance(x, bool) for x in tr.attack_extra_dropped)
    # weak includes the populated field, so its digest differs from the strong shape
    strong = generate_trace(_base(attacker_inject_strength="strong", num_replay=12), seed=SEED)
    assert tr.digest() != strong.digest()
