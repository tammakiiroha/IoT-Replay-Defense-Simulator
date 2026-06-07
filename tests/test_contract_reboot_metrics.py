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


def test_aggregate_stats_accepts_reboot_counters():
    agg = _agg(reboots=2, locked_safe_rejects=3, epoch_recoveries=1)
    assert agg.reboots == 2
    assert agg.locked_safe_rejects == 3
    assert agg.epoch_recoveries == 1


def test_result_record_exposes_reboot_counters_from_aggregate():
    rec = SimulationResultRecord.from_aggregate(
        _agg(reboots=2, locked_safe_rejects=3, epoch_recoveries=1)
    )
    assert rec.reboots == 2
    assert rec.locked_safe_rejects == 3
    assert rec.epoch_recoveries == 1


def test_result_record_reboot_counters_default_zero():
    rec = SimulationResultRecord.from_aggregate(_agg())
    assert rec.reboots == 0
    assert rec.locked_safe_rejects == 0
    assert rec.epoch_recoveries == 0


def test_aggregate_as_dict_includes_reboot_counters():
    # 导出面（P5 教训）：as_dict 必须带这三计数
    d = _agg(reboots=2, locked_safe_rejects=3, epoch_recoveries=1).as_dict()
    assert d["reboots"] == 2
    assert d["locked_safe_rejects"] == 3
    assert d["epoch_recoveries"] == 1


def test_typescript_contract_includes_reboot_counters():
    from replay.contracts import render_typescript_contracts

    src = render_typescript_contracts()
    assert "reboots: number;" in src
    assert "locked_safe_rejects: number;" in src
    assert "epoch_recoveries: number;" in src
