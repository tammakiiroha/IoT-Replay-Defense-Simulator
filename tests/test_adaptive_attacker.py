"""AdaptiveReplay strategies (Phase 5 P3).

Capability boundary (A2): adaptive strategies only ever pick/reorder
ALREADY-RECORDED legitimate frames — never forge fields. Each strategy filters
candidates via the injected AttackContext (window/mask, g_hard, policy table).
Default (attacker_strategy="random") must stay byte-for-byte the legacy baseline.
"""
import json
from pathlib import Path

from replay.core import Mode, SimulationConfig, run_paired_experiments
from replay.core.attacker import AdaptiveReplay, AttackContext
from replay.core.types import AttackMode, Frame

_BASELINE = json.loads(Path("tests/fixtures/engine_baseline.json").read_text())


def _frame(counter: int, command: str = "PING", flags: int = 0) -> Frame:
    f = Frame(command=command, counter=counter, mac=f"m{counter}", nonce=None)
    f.flags = flags
    return f


# --- adaptive_lostframe: in-window UNACCEPTED slot only ---


def test_adaptive_lostframe_targets_unaccepted_window_slot():
    # h=10, W=5; mask offset0 (counter10)=accepted, offset2 (counter8)=free
    ctx = AttackContext(window_size=5, g_hard=16, last_counter=10, received_mask=(1, 0, 0, 0, 0))
    f_dup = _frame(10)   # offset 0, mask[0]=1 -> excluded (already accepted)
    f_slot = _frame(8)   # offset 2, mask[2]=0 -> candidate
    f_old = _frame(3)    # offset 7 >= W -> excluded
    strat = AdaptiveReplay("adaptive_lostframe")
    strat._recorded = [f_dup, f_slot, f_old]
    picked = strat.pick_recorded(0, strat._recorded, context=ctx)
    assert picked is not None
    assert picked.counter == 8


def test_adaptive_lostframe_none_when_all_slots_filled():
    ctx = AttackContext(window_size=3, g_hard=16, last_counter=5, received_mask=(1, 1, 1))
    strat = AdaptiveReplay("adaptive_lostframe")
    strat._recorded = [_frame(5), _frame(4), _frame(3)]
    assert strat.pick_recorded(0, strat._recorded, context=ctx) is None


# --- adaptive_resync: recorded frame with counter gap > g_hard, normal only ---


def test_adaptive_resync_only_picks_recorded_gap_frames():
    ctx = AttackContext(window_size=5, g_hard=4, last_counter=10)
    f_near = _frame(13)  # gap 3, not > 4 -> excluded
    f_gap = _frame(20)   # gap 10 > 4 -> candidate
    strat = AdaptiveReplay("adaptive_resync")
    strat._recorded = [f_near]
    assert strat.pick_recorded(0, strat._recorded, context=ctx) is None  # never forges a gap frame
    strat._recorded = [f_near, f_gap]
    picked = strat.pick_recorded(0, strat._recorded, context=ctx)
    assert picked is not None
    assert picked.counter == 20


def test_adaptive_resync_skips_critical_frames():
    ctx = AttackContext(window_size=5, g_hard=4, last_counter=10)
    # flag-based critical: excluded even though gap qualifies
    crit_flag = _frame(20, command="OPEN", flags=Frame.FLAG_CRIT_PREPARE)
    strat = AdaptiveReplay("adaptive_resync")
    strat._recorded = [crit_flag]
    assert strat.pick_recorded(0, strat._recorded, context=ctx) is None

    # policy-based critical: normal flags but policy_table says critical -> excluded
    class _Policy:
        def is_critical(self, cmd: str) -> bool:
            return cmd == "OPEN"

    ctx2 = AttackContext(window_size=5, g_hard=4, last_counter=10, policy_table=_Policy())
    crit_cmd = _frame(20, command="OPEN", flags=0)
    strat._recorded = [crit_cmd]
    assert strat.pick_recorded(0, strat._recorded, context=ctx2) is None


# --- adaptive_critical: only recorded FLAG_CRIT_PREPARE frames ---


def test_adaptive_critical_only_uses_recorded_critical_frames():
    ctx = AttackContext(window_size=5, g_hard=4, last_counter=10)
    normal = _frame(5, command="PING", flags=0)
    crit = _frame(7, command="OPEN", flags=Frame.FLAG_CRIT_PREPARE)
    strat = AdaptiveReplay("adaptive_critical")
    strat._recorded = [normal]
    assert strat.pick_recorded(0, strat._recorded, context=ctx) is None  # no critical recorded
    strat._recorded = [normal, crit]
    picked = strat.pick_recorded(0, strat._recorded, context=ctx)
    assert picked is not None
    assert picked.flags == Frame.FLAG_CRIT_PREPARE
    assert picked.counter == 7


# --- paired engine wiring + default zero-drift ---


def _paired(strategy: str):
    cfg = SimulationConfig(
        mode=Mode.WINDOW,
        attack_mode=AttackMode.INLINE,
        num_legit=20,
        num_replay=30,
        p_loss=0.3,
        p_reorder=0.1,
        window_size=5,
        g_hard=16,
        rng_seed=123,
        command_set=["UNLOCK", "LOCK", "PING"],
        attacker_strategy=strategy,
    )
    return run_paired_experiments(
        cfg, modes=[Mode.WINDOW], runs=10, seed=123, show_progress=False
    )[0]


def test_adaptive_works_in_paired_path():
    adaptive = _paired("adaptive_lostframe")
    rnd = _paired("random")
    # paired wiring intact: valid aggregate stats
    assert 0 <= adaptive.attack_accepted <= adaptive.attack_total
    # adaptive lost-frame selection actually lands accepted replays in-window
    assert adaptive.attack_accepted > 0
    # and it engages differently from random selection
    assert (adaptive.attack_accepted, adaptive.attack_total) != (
        rnd.attack_accepted,
        rnd.attack_total,
    )


def test_random_default_still_matches_baseline_after_adaptive_added():
    cfg = SimulationConfig(
        mode=Mode.NO_DEFENSE,
        attack_mode=AttackMode.POST_RUN,
        num_legit=20,
        num_replay=30,
        p_loss=0.1,
        p_reorder=0.1,
        window_size=5,
        g_hard=16,
        rng_seed=_BASELINE["seed"],
        command_set=["UNLOCK", "LOCK", "PING"],
        command_risk={"UNLOCK": 1.0},
        risk_high=0.8,
    )  # attacker_strategy defaults to "random"
    modes = [
        Mode.NO_DEFENSE,
        Mode.ROLLING_MAC,
        Mode.WINDOW,
        Mode.CHALLENGE,
        Mode.OSCORE_LIKE,
    ]
    stats = run_paired_experiments(
        cfg, modes=modes, runs=_BASELINE["runs"], seed=_BASELINE["seed"], show_progress=False
    )
    got = {
        str(s.mode): {
            "legit_accepted": s.legit_accepted,
            "legit_total": s.legit_total,
            "attack_accepted": s.attack_accepted,
            "attack_total": s.attack_total,
        }
        for s in stats
    }
    expected = {m: _BASELINE["cases"]["paired/post"][m] for m in got}
    assert got == expected
    assert SimulationConfig(mode=Mode.NO_DEFENSE).attacker_strategy == "random"
