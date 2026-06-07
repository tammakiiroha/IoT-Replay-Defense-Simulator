from replay.core.policy import PolicyTable
from replay.core.receiver import Receiver
from replay.core.types import Mode, SimulationConfig


def test_simulation_config_policy_defaults():
    c = SimulationConfig(mode=Mode.HSW_CR)
    assert c.policy_source == "legacy"
    assert c.profile == "standard"
    assert c.command_impact is None


def test_receiver_prebuilds_legacy_policy_table():
    rcv = Receiver(
        Mode.HSW_CR, shared_key="k", mac_length=8, window_size=8,
        command_risk={"UNLOCK": 1.0}, risk_high=0.8,
        policy_source="legacy", profile="standard",
    )
    assert isinstance(rcv.policy_table, PolicyTable)
    assert rcv.policy_table.is_critical("UNLOCK") is True   # legacy: risk 1.0>=0.8
    assert rcv.policy_table.is_critical("PING") is False


def test_receiver_prebuilds_default_table_policy():
    rcv = Receiver(
        Mode.HSW_CR, shared_key="k", mac_length=8, window_size=8,
        policy_source="default_table", profile="standard",
    )
    assert rcv.policy_table.is_critical("SET_SPEED") is True
    assert rcv.policy_table.is_critical("FWD") is False
