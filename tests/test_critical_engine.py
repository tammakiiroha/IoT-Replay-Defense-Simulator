import dataclasses
import random

from replay.core.cost import CostStats
from replay.core.experiment import (
    _resolve_critical,
    simulate_one_run,
    simulate_one_run_with_trace,
)
from replay.core.receiver import Receiver
from replay.core.sender import Sender
from replay.core.trace import generate_trace
from replay.core.types import AttackMode, Mode, SimulationConfig

KEY = "sim_shared_key"


def _cfg(**kw) -> SimulationConfig:
    base = SimulationConfig(
        mode=Mode.HSW_CR,
        attack_mode=AttackMode.POST_RUN,
        num_legit=1,
        num_replay=0,
        p_loss=0.0,
        p_reorder=0.0,
        window_size=8,
        g_hard=16,
        rng_seed=7,
        command_sequence=["OPEN"],
        command_set=["OPEN"],
        command_risk={"OPEN": 1.0},
        risk_high=0.8,
    )
    return dataclasses.replace(base, **kw)


def test_hsw_cr_critical_command_commits_once_clean_channel():
    res = simulate_one_run(_cfg())
    assert res.crit_prepared == 1
    assert res.crit_committed == 1
    assert res.legit_accepted == 1   # 命令执行一次


def test_replayed_critical_prepare_does_not_commit():
    # blocker（引擎级）：attacker 重放 prepare -> 不 commit、attack_success==0
    res = simulate_one_run(_cfg(num_replay=5))
    assert res.crit_committed == 1
    assert res.attack_success == 0
    assert res.attack_attempts >= 1


def test_resolve_critical_confirm_lost_times_out():
    # confirm 丢失 -> 不 commit、crit_rejected 计数、pending 清理
    sender = Sender(mode=Mode.HSW_CR, shared_key=KEY, mac_length=8)
    rcv = Receiver(
        Mode.HSW_CR, shared_key=KEY, mac_length=8, window_size=8,
        command_risk={"OPEN": 1.0}, risk_high=0.8,
    )
    cost = CostStats()
    prep = sender.begin_critical_intent("OPEN", b"OPEN", key_id=0, now_tick=0)
    committed = _resolve_critical(
        rcv, sender, cost,
        frame=prep, rng=random.Random(1), now_tick=0,
        ttl_ticks=16, rtt_ticks=1, tau_intent=16,
        transport=lambda: (False, 0, True, 0),   # confirm dropped
    )
    assert committed is False
    assert cost.crit_prepared == 1
    assert cost.crit_committed == 0
    assert cost.crit_rejected == 1
    assert rcv.state.pending_critical == {}


def test_paired_critical_round_trip_commits():
    cfg = _cfg()
    trace = generate_trace(cfg, seed=7)
    res = simulate_one_run_with_trace(cfg, trace, nonce_seed=7)
    assert res.crit_committed == 1
    assert res.legit_accepted == 1


def test_non_hsw_cr_mode_has_no_critical_activity():
    # 隔离：非 HSW_CR 模式不触发任何 critical 逻辑
    res = simulate_one_run(_cfg(mode=Mode.WINDOW, command_risk={"OPEN": 1.0}))
    assert res.crit_prepared == 0
    assert res.crit_committed == 0
    assert res.crit_rejected == 0
