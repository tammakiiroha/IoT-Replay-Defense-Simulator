from __future__ import annotations

import importlib

import pytest

from replay.contracts import (
    SimulationBatchResult,
    SimulationResultRecord,
    SimulationSpec,
    SimulationSpecPublic,
)
from replay.core import AttackMode, Mode

legacy_main = importlib.import_module("main")


def _sample_batch(spec: SimulationSpec) -> SimulationBatchResult:
    return SimulationBatchResult(
        config=SimulationSpecPublic.from_spec(spec),
        results=[
            SimulationResultRecord(
                mode=Mode(spec.modes[0]),
                runs=spec.runs,
                avg_legit_rate=1.0,
                std_legit_rate=0.0,
                avg_attack_rate=0.0,
                std_attack_rate=0.0,
                p_loss=spec.p_loss,
                p_reorder=spec.p_reorder,
                window_size=spec.window_size,
                num_legit=spec.num_legit,
                num_replay=spec.num_replay,
                attack_mode=AttackMode(spec.attack_mode),
                metadata={"source": "test"},
            )
        ],
        metadata={"source": "test"},
    )


def test_main_accepts_commands_file_and_passes_command_sequence(monkeypatch):
    captured: dict[str, object] = {}

    def fake_simulate_batch(
        spec: SimulationSpec,
        *,
        show_progress: bool = False,
    ) -> SimulationBatchResult:
        captured["spec"] = spec
        captured["show_progress"] = show_progress
        return _sample_batch(spec)

    monkeypatch.setattr(legacy_main, "simulate_batch", fake_simulate_batch)

    legacy_main.main(["--commands-file", "traces/sample_trace.txt", "--quiet"])

    spec = captured["spec"]
    assert isinstance(spec, SimulationSpec)
    assert spec.command_sequence == [
        "FWD",
        "FWD",
        "LEFT",
        "FWD",
        "RIGHT",
        "RIGHT",
        "BACK",
        "STOP",
        "FWD",
        "LEFT",
        "STOP",
    ]
    assert captured["show_progress"] is False


def test_main_rejects_invalid_modes_with_cli_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        legacy_main.main(["--modes", "bogus", "--quiet"])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err
    assert "Traceback" not in captured.err
