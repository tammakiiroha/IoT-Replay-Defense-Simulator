from replay.contracts import SimulationResultRecord
from replay.core.types import AggregateStats, AttackMode, Mode


def _agg(**kw):
    base = dict(
        mode=Mode.HSW_CR, runs=1, avg_legit_rate=1.0, std_legit_rate=0.0,
        avg_attack_rate=0.0, std_attack_rate=0.0, p_loss=0.0, p_reorder=0.0,
        window_size=5, num_legit=1, num_replay=0, attack_mode=AttackMode.POST_RUN,
    )
    base.update(kw)
    return AggregateStats(**base)


def test_aggregate_stats_accepts_critical_counters():
    agg = _agg(crit_prepared=4, crit_committed=3, crit_rejected=1)
    assert agg.crit_prepared == 4
    assert agg.crit_committed == 3
    assert agg.crit_rejected == 1


def test_result_record_exposes_critical_counters_from_aggregate():
    rec = SimulationResultRecord.from_aggregate(
        _agg(crit_prepared=4, crit_committed=3, crit_rejected=1)
    )
    assert rec.crit_prepared == 4
    assert rec.crit_committed == 3
    assert rec.crit_rejected == 1


def test_result_record_critical_counters_default_zero():
    rec = SimulationResultRecord.from_aggregate(_agg())
    assert rec.crit_prepared == 0
    assert rec.crit_committed == 0
    assert rec.crit_rejected == 0


def test_aggregate_as_dict_includes_critical_counters():
    # 导出面（Phase 2 教训）：凡走 entry.as_dict() 的导出都必须带这三指标
    d = _agg(crit_prepared=4, crit_committed=3, crit_rejected=1).as_dict()
    assert d["crit_prepared"] == 4
    assert d["crit_committed"] == 3
    assert d["crit_rejected"] == 1


def test_typescript_contract_includes_critical_counters():
    from replay.contracts import render_typescript_contracts

    src = render_typescript_contracts()
    assert "crit_prepared: number;" in src
    assert "crit_committed: number;" in src
    assert "crit_rejected: number;" in src
