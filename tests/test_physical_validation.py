from types import SimpleNamespace

import physical_experiment.scripts.run_validation as validation
from physical_experiment.scripts.experiment_runner import ExperimentResult
from physical_experiment.scripts.run_validation import ValidationResult, evaluate_goal_criteria
from sim.types import AttackMode, Mode


def _make_result(
    mode: str,
    window_size: int,
    *,
    lar: float,
    asr: float,
    p_loss: float = 0.0,
    lar_valid: bool = True,
    asr_valid: bool = True,
) -> ValidationResult:
    return ValidationResult(
        mode=mode,
        window_size=window_size,
        p_loss_injected=p_loss,
        loss_seed=42,
        physical_lar=lar,
        physical_asr=asr,
        physical_runs=3,
        sim_lar=lar,
        sim_asr=asr,
        sim_runs=3,
        lar_error=0.0,
        asr_error=0.0,
        lar_valid=lar_valid,
        asr_valid=asr_valid,
    )


def test_goal_criteria_passes_for_expected_behavior():
    results = [
        _make_result("no_def", 1, lar=1.0, asr=1.0),
        _make_result("rolling", 1, lar=1.0, asr=0.0),
        _make_result("window", 5, lar=1.0, asr=0.0),
        _make_result("challenge", 1, lar=1.0, asr=0.0),
    ]

    goal = evaluate_goal_criteria(results)

    assert goal["passed"]
    assert goal["ordering_check_passed"]
    assert all(item["passed"] for item in goal["modes"].values())


def test_goal_criteria_requires_each_window_sample_to_meet_threshold():
    # Window mode has two samples; mean equals threshold, but one sample exceeds it.
    results = [
        _make_result("no_def", 1, lar=1.0, asr=1.0),
        _make_result("rolling", 1, lar=1.0, asr=0.0),
        _make_result("challenge", 1, lar=1.0, asr=0.0),
        _make_result("window", 3, lar=1.0, asr=0.0),
        _make_result("window", 5, lar=1.0, asr=0.2),
    ]

    goal = evaluate_goal_criteria(results, defended_asr_max=0.10)

    assert not goal["passed"]
    assert not goal["modes"]["window"]["behavior_passed"]


def test_goal_criteria_uses_strict_ordering_floor_vs_ceiling():
    # no_def has high mean ASR, but worst no_def sample is below best defended sample.
    results = [
        _make_result("no_def", 1, lar=1.0, asr=0.9),
        _make_result("no_def", 1, lar=1.0, asr=0.02),
        _make_result("rolling", 1, lar=1.0, asr=0.03),
        _make_result("window", 5, lar=1.0, asr=0.01),
        _make_result("challenge", 1, lar=1.0, asr=0.01),
    ]

    goal = evaluate_goal_criteria(results, no_def_asr_min=0.0, defended_asr_max=0.1)

    assert not goal["passed"]
    assert not goal["ordering_check_passed"]


def test_run_simulation_reuses_core_simulate_one_run_with_full_config(monkeypatch):
    captured_configs = []

    def fake_simulate_one_run(config, rng=None):
        captured_configs.append(config)
        return SimpleNamespace(
            legit_accepted=3,
            attack_success=1,
            legit_sent=5,
            attack_attempts=4,
        )

    monkeypatch.setattr(validation, "simulate_one_run", fake_simulate_one_run)

    result = validation.run_simulation(
        mode=Mode.WINDOW,
        window_size=7,
        num_runs=4,
        num_legit=12,
        num_attack=34,
        p_loss=0.2,
        p_reorder=0.1,
        seed=123,
        attacker_record_loss=0.25,
        attack_mode=AttackMode.INLINE,
        inline_attack_probability=0.55,
        inline_attack_burst=3,
        challenge_nonce_bits=64,
        shared_key="k_test",
        mac_length=12,
        command_set=["A", "B"],
    )

    assert len(captured_configs) == 4
    for cfg in captured_configs:
        assert cfg.mode is Mode.WINDOW
        assert cfg.num_legit == 12
        assert cfg.num_replay == 34
        assert cfg.p_loss == 0.2
        assert cfg.p_reorder == 0.1
        assert cfg.window_size == 7
        assert cfg.attack_mode is AttackMode.INLINE
        assert cfg.attacker_record_loss == 0.25
        assert cfg.inline_attack_probability == 0.55
        assert cfg.inline_attack_burst == 3
        assert cfg.challenge_nonce_bits == 64
        assert cfg.shared_key == "k_test"
        assert cfg.mac_length == 12
        assert cfg.command_set == ["A", "B"]

    assert result.total_legit_accepted == 12
    assert result.total_legit_sent == 20
    assert result.total_attack_success == 4
    assert result.total_attack_sent == 16
    assert result.avg_lar == 0.6
    assert result.avg_asr == 0.25


def test_link_selftest_uses_no_defense_mode(monkeypatch):
    calls = []

    class FakeHardwareExperiment:
        def __init__(self, config):
            self.transport = None

        def connect(self, loopback, p_loss, p_reorder, rng):
            return True

        def run_single_experiment(
            self,
            mode,
            window_size,
            run_id,
            rng,
            num_legit_override,
            num_attack_override,
        ):
            calls.append((mode, window_size, num_attack_override))
            return SimpleNamespace(legit_accepted=num_legit_override)

        def disconnect(self):
            pass

    monkeypatch.setattr(validation, "HardwareExperiment", FakeHardwareExperiment)
    passed, stats = validation.run_link_selftest(config={}, loopback=True, num_frames=9, seed=7)

    assert passed
    assert calls == [(Mode.NO_DEFENSE, 1, 0)]
    assert stats["frames_sent"] == 9
    assert stats["frames_received"] == 9
    assert stats["loss_rate"] == 0.0


def test_experiment_result_exposes_canonical_and_legacy_metric_keys():
    exp = ExperimentResult(
        config_name="window_w5",
        mode="window",
        window_size=5,
        num_runs=10,
        avg_legit_accept_rate=0.91,
        std_legit_accept_rate=0.03,
        avg_attack_success_rate=0.07,
        std_attack_success_rate=0.01,
        total_timeouts=2,
    )

    payload = exp.as_dict()

    assert payload["avg_legit_rate"] == 0.91
    assert payload["std_legit_rate"] == 0.03
    assert payload["avg_attack_rate"] == 0.07
    assert payload["std_attack_rate"] == 0.01
    assert payload["avg_legit_accept_rate"] == 0.91
    assert payload["std_legit_accept_rate"] == 0.03
    assert payload["avg_attack_success_rate"] == 0.07
    assert payload["std_attack_success_rate"] == 0.01
