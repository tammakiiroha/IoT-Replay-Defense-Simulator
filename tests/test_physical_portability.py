from pathlib import Path
from types import SimpleNamespace

from physical_experiment.runtime import resolve_hackrf_device_args
from physical_experiment.scripts.run_full_experiment import ExperimentOrchestrator, FlowgraphManager
from physical_experiment.scripts.run_hardware_validation import HardwareOrchestrator


def _make_config(tmp_path: Path) -> dict:
    return {
        "hardware": {
            "tx": {"device_serial": "TX123", "device_args": ""},
            "rx": {"device_serial": "RX456", "device_args": ""},
        },
        "output": {
            "results_dir": str(tmp_path / "results"),
            "logs_dir": str(tmp_path / "logs"),
            "figures_dir": str(tmp_path / "figures"),
            "reports_dir": str(tmp_path / "reports"),
        },
        "flowgraph": {
            "tx_script": "physical_experiment/flowgraphs/tx_flowgraph.py",
            "rx_script": "physical_experiment/flowgraphs/rx_flowgraph.py",
            "startup_timeout_s": 1,
            "shutdown_timeout_s": 1,
        },
        "phases": {
            "calibration": {"enabled": True, "packets": 10, "distances": ["lab"]},
            "defense_comparison": {"enabled": True, "modes": ["window"], "runs_per_mode": 2},
            "window_sweep": {"enabled": True, "window_sizes": [5], "runs_per_size": 1},
            "analysis": {"enabled": False},
        },
        "experiment": {"runs_per_config": 2},
        "traffic": {"num_legit_frames": 10, "num_replay_attempts": 5},
    }


def test_resolve_hackrf_device_args_prefers_overrides():
    config = {
        "hardware": {
            "tx": {"device_serial": "CONFIG_TX", "device_args": "biastee=1"},
        }
    }

    assert resolve_hackrf_device_args(config, "tx") == "hackrf=CONFIG_TX biastee=1"
    assert (
        resolve_hackrf_device_args(config, "tx", serial_override="CLI_TX")
        == "hackrf=CLI_TX biastee=1"
    )
    assert (
        resolve_hackrf_device_args(config, "tx", device_args_override="amp=0")
        == "hackrf=CONFIG_TX amp=0"
    )


def test_flowgraph_manager_uses_runtime_config_and_serials(tmp_path):
    config = _make_config(tmp_path)
    runtime_config = tmp_path / "runtime.yaml"
    runtime_config.write_text("hardware: {}\n", encoding="utf-8")

    manager = FlowgraphManager(config, config_path=runtime_config, verbose=False)

    rx_cmd = manager._build_flowgraph_command("rx")
    tx_cmd = manager._build_flowgraph_command("tx")

    assert rx_cmd[0]
    assert rx_cmd[1].endswith("rx_flowgraph.py")
    assert rx_cmd[2:4] == ["--config", str(runtime_config)]
    assert rx_cmd[-2:] == ["--hackrf-serial", "RX456"]

    assert tx_cmd[1].endswith("tx_flowgraph.py")
    assert tx_cmd[2:4] == ["--config", str(runtime_config)]
    assert tx_cmd[-2:] == ["--hackrf-serial", "TX123"]


def test_experiment_orchestrator_phases_use_runtime_config(tmp_path, monkeypatch):
    config = _make_config(tmp_path)
    orchestrator = ExperimentOrchestrator(config, verbose=False)
    captured = []

    def fake_run_command(cmd, description):
        captured.append((cmd, description))
        return True

    monkeypatch.setattr(orchestrator, "run_command", fake_run_command)

    assert orchestrator.phase_calibration()
    assert orchestrator.phase_defense_comparison()
    assert orchestrator.phase_window_sweep()

    assert orchestrator.runtime_config_path.exists()
    for cmd, _ in captured:
        assert "--config" in cmd
        config_index = cmd.index("--config")
        assert cmd[config_index + 1] == str(orchestrator.runtime_config_path)


def test_hardware_orchestrator_validation_commands_include_runtime_config(tmp_path, monkeypatch):
    config = _make_config(tmp_path)
    runtime_config = tmp_path / "runtime.yaml"
    runtime_config.write_text("hardware: {}\n", encoding="utf-8")

    orchestrator = HardwareOrchestrator(
        config=config,
        config_path=runtime_config,
        tx_serial="TX123",
        rx_serial="RX456",
        attenuation_db=50.0,
    )

    commands = []

    def fake_run(cmd, *args, **kwargs):
        commands.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "physical_experiment.scripts.run_hardware_validation.subprocess.run",
        fake_run,
    )

    assert orchestrator.run_link_selftest(selftest_frames=50)
    assert orchestrator.run_validation(quick=True, loss_samples="0,0.1", goal_check=True) == 0

    assert len(commands) == 2
    for cmd in commands:
        assert "--config" in cmd
        config_index = cmd.index("--config")
        assert cmd[config_index + 1] == str(runtime_config)


def test_zmq_sources_default_to_localhost():
    root = Path(__file__).resolve().parents[1] / "physical_experiment"
    checked = [
        root / "scripts" / "experiment_runner.py",
        root / "flowgraphs" / "tx_flowgraph.py",
        root / "flowgraphs" / "attacker_flowgraph.py",
        root / "flowgraphs" / "grc_generator.py",
        root / "flowgraphs" / "iot_rx.grc",
        root / "flowgraphs" / "rx_flowgraph.grc",
        Path(__file__).resolve().parents[1] / "scripts" / "attacker_relay.py",
        Path(__file__).resolve().parents[1] / "scripts" / "hardware_experiment.py",
    ]
    for path in checked:
        source = path.read_text(encoding="utf-8")
        assert 'bind("tcp://*:' not in source
        assert "bind('tcp://*:" not in source
        assert 'bind(f"tcp://*:' not in source
        assert "bind(f'tcp://*:" not in source
        assert "127.0.0.1" in source

    runner_source = (root / "scripts" / "experiment_runner.py").read_text(encoding="utf-8")
    assert "--bind-all" in runner_source
