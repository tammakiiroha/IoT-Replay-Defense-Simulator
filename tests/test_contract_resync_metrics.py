from replay.contracts import SimulationResultRecord
from replay.core.types import AggregateStats, AttackMode, Mode


def _agg(**kw):
    base = dict(
        mode=Mode.SW_RESYNC, runs=1, avg_legit_rate=1.0, std_legit_rate=0.0,
        avg_attack_rate=0.0, std_attack_rate=0.0, p_loss=0.0, p_reorder=0.0,
        window_size=5, num_legit=1, num_replay=0, attack_mode=AttackMode.POST_RUN,
    )
    base.update(kw)
    return AggregateStats(**base)


def test_aggregate_stats_accepts_resync_counters():
    agg = _agg(resync_initiated=5, resync_completed=3, resync_timeout=2)
    assert agg.resync_initiated == 5
    assert agg.resync_completed == 3
    assert agg.resync_timeout == 2


def test_result_record_exposes_resync_counters_from_aggregate():
    rec = SimulationResultRecord.from_aggregate(
        _agg(resync_initiated=5, resync_completed=3, resync_timeout=2)
    )
    assert rec.resync_initiated == 5
    assert rec.resync_completed == 3
    assert rec.resync_timeout == 2


def test_result_record_resync_counters_default_zero():
    rec = SimulationResultRecord.from_aggregate(_agg())
    assert rec.resync_initiated == 0
    assert rec.resync_completed == 0
    assert rec.resync_timeout == 0
