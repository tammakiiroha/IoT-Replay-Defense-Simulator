import dataclasses

from replay.core.experiment import simulate_one_run
from replay.core.types import AttackMode, Mode, SimulationConfig


def _cfg(**kw) -> SimulationConfig:
    base = SimulationConfig(
        mode=Mode.HSW_CR,
        attack_mode=AttackMode.POST_RUN,
        num_legit=2,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.0,
        window_size=8,
        g_hard=16,
        rng_seed=7,
        command_sequence=["SET_SPEED"],
        command_set=["SET_SPEED", "FWD"],
        policy_source="default_table",
        profile="standard",
    )
    return dataclasses.replace(base, **kw)


def test_policy_routes_critical_by_impact():
    # default_table standard: SET_SPEED(I=3>=θ_I=3) critical -> 两阶段；FWD(I=1) normal -> window
    r_crit = simulate_one_run(_cfg(command_sequence=["SET_SPEED"]))
    assert r_crit.crit_committed == 2
    r_norm = simulate_one_run(_cfg(command_sequence=["FWD"]))
    assert r_norm.crit_committed == 0


def test_profile_strict_upgrades_more_commands():
    # SET_SPEED I=3：standard/strict critical（θ_I<=3），permissive(θ_I=4) normal
    std = simulate_one_run(_cfg(command_sequence=["SET_SPEED"], profile="standard"))
    strict = simulate_one_run(_cfg(command_sequence=["SET_SPEED"], profile="strict"))
    perm = simulate_one_run(_cfg(command_sequence=["SET_SPEED"], profile="permissive"))
    assert std.crit_committed == 2
    assert strict.crit_committed == 2
    assert perm.crit_committed == 0


def test_legacy_default_matches_old_risk_threshold():
    # legacy（默认）：command_risk 阈值决定；OPEN risk 0.9>=0.8 -> 两阶段
    cfg = _cfg(
        policy_source="legacy", profile="standard",
        command_sequence=["OPEN"], command_set=["OPEN"],
        command_risk={"OPEN": 0.9},
    )
    assert simulate_one_run(cfg).crit_committed == 2
