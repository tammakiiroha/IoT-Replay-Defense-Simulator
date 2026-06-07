from replay.core.types import Mode, ReceiverState, SimulationConfig


def test_receiver_state_reboot_defaults():
    s = ReceiverState()
    assert s.locked_safe is False
    assert s.boot_counter == 0
    assert s.nvm_epoch == 0


def test_simulation_config_reboot_default_none():
    c = SimulationConfig(mode=Mode.HSW_CR)
    assert c.reboot_at_legit_index is None


def test_simulation_config_reboot_settable():
    c = SimulationConfig(mode=Mode.HSW_CR, reboot_at_legit_index=5)
    assert c.reboot_at_legit_index == 5
