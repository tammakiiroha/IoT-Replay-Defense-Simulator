from replay.contracts import SimulationResultRecord, render_typescript_contracts
from replay.contracts.models import SimulationSpec
from replay.core.types import AggregateStats, AttackMode, Mode


def _agg(**kw):
    base = dict(
        mode=Mode.HSW_CR, runs=1, avg_legit_rate=1.0, std_legit_rate=0.0,
        avg_attack_rate=0.0, std_attack_rate=0.0, p_loss=0.0, p_reorder=0.0,
        window_size=5, num_legit=1, num_replay=0, attack_mode=AttackMode.POST_RUN,
    )
    base.update(kw)
    return AggregateStats(**base)


def test_simulation_spec_policy_defaults():
    spec = SimulationSpec()
    assert spec.profile == "standard"
    assert spec.policy_source == "legacy"


def test_spec_to_config_threads_policy():
    spec = SimulationSpec(profile="strict", policy_source="default_table")
    cfg = spec.to_runtime_config()
    assert cfg.profile == "strict"
    assert cfg.policy_source == "default_table"


def test_aggregate_stats_accepts_critical_command_count():
    assert _agg(critical_command_count=4).critical_command_count == 4


def test_result_record_exposes_critical_command_count_from_aggregate():
    rec = SimulationResultRecord.from_aggregate(_agg(critical_command_count=4))
    assert rec.critical_command_count == 4


def test_result_record_critical_command_count_default_zero():
    assert SimulationResultRecord.from_aggregate(_agg()).critical_command_count == 0


def test_aggregate_as_dict_includes_critical_command_count():
    # 导出面（P5 教训）：as_dict 必须带该计数
    assert _agg(critical_command_count=4).as_dict()["critical_command_count"] == 4


def test_typescript_contract_includes_policy_fields():
    src = render_typescript_contracts()
    assert "critical_command_count: number;" in src
    assert "profile" in src
    assert "policy_source" in src
