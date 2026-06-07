import pytest

from replay.core.policy import (
    DEFAULT_COMMAND_IMPACT,
    PROFILE_PARAMS,
    PolicyTable,
    classify_critical,
    impact_index,
)


def test_impact_index_is_max():
    assert impact_index((1, 3, 0, 2, 4, 1)) == 4
    assert impact_index((0, 0, 0, 1, 0, 0)) == 1


def test_profile_params_frozen_values():
    assert PROFILE_PARAMS["strict"].theta_i == 2
    assert PROFILE_PARAMS["standard"].theta_i == 3
    assert PROFILE_PARAMS["permissive"].theta_i == 4
    assert PROFILE_PARAMS["standard"].theta_r == 0.01
    assert PROFILE_PARAMS["standard"].lam == 1


def test_classify_legacy_matches_risk_threshold():
    # legacy：完全等于旧 command_risk>=risk_high；profile/impact 不生效
    assert classify_critical(
        "OPEN", policy_source="legacy", profile="standard",
        command_impact={"OPEN": (4, 4, 4, 4, 4, 4)},
        command_risk={"OPEN": 0.9}, risk_high=0.8,
    ) is True
    assert classify_critical(
        "PING", policy_source="legacy", profile="standard",
        command_impact=None, command_risk={"PING": 0.1}, risk_high=0.8,
    ) is False


def test_classify_default_table_by_theta_i():
    kw = dict(
        policy_source="default_table", profile="standard",
        command_impact=None, command_risk=None, risk_high=0.8,
    )
    assert classify_critical("SET_SPEED", **kw) is True
    assert classify_critical("FWD", **kw) is False
    # 默认表里有 SET_SPEED / FWD
    assert "SET_SPEED" in DEFAULT_COMMAND_IMPACT and "FWD" in DEFAULT_COMMAND_IMPACT


def test_classify_profile_ordering():
    kw = dict(policy_source="default_table", command_impact=None, command_risk=None, risk_high=0.8)
    # SET_SPEED I=3：strict/standard critical，permissive normal
    assert classify_critical("SET_SPEED", profile="standard", **kw) is True
    assert classify_critical("SET_SPEED", profile="permissive", **kw) is False
    # LOCK I=2：strict critical，standard normal
    assert classify_critical("LOCK", profile="strict", **kw) is True
    assert classify_critical("LOCK", profile="standard", **kw) is False


def test_classify_custom_requires_impact():
    with pytest.raises(ValueError):
        classify_critical("X", policy_source="custom", profile="standard",
                          command_impact=None, command_risk=None, risk_high=0.8)
    assert classify_critical(
        "X", policy_source="custom", profile="standard",
        command_impact={"X": (3, 0, 0, 0, 0, 0)}, command_risk=None, risk_high=0.8,
    ) is True


def test_optional_risk_sw_delta_u_reserved_interface():
    # D3=A 预留接口：θ_I 不满足时 risk_sw>=θ_R 或 ΔU>0 仍可升 critical（Phase 5 用）
    kw = dict(policy_source="default_table", profile="standard", command_impact=None,
              command_risk=None, risk_high=0.8)
    assert classify_critical("FWD", **kw) is False           # I=1 < θ_I=3
    assert classify_critical("FWD", risk_sw=0.5, **kw) is True   # 0.5 >= θ_R=0.01
    assert classify_critical("FWD", delta_u=0.1, **kw) is True   # ΔU>0


def test_policy_table_is_critical_matches_and_frozenset():
    pt = PolicyTable.from_config(
        policy_source="default_table", profile="standard", command_impact=None,
        command_risk=None, risk_high=0.8,
    )
    assert pt.is_critical("SET_SPEED") is True
    assert pt.is_critical("FWD") is False
    assert pt.is_critical("UNLOCK") is True
    assert pt.is_critical("UNKNOWN_CMD") is False   # 域外命令 -> normal
    assert isinstance(pt.critical, frozenset)


def test_policy_table_legacy_matches_old_threshold():
    pt = PolicyTable.from_config(
        policy_source="legacy", profile="standard", command_impact=None,
        command_risk={"A": 0.9, "B": 0.1}, risk_high=0.8,
    )
    assert pt.is_critical("A") is True
    assert pt.is_critical("B") is False
