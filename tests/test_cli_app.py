import json

from replay.cli import app as cli_app
from replay.contracts import SimulationBatchResult, SimulationResultRecord, SimulationSpecPublic
from replay.core import AttackMode, Mode


def test_cli_sim_run_uses_preset_and_allows_run_override(monkeypatch, capsys):
    captured = {}

    def fake_simulate_batch(spec, *, show_progress):
        captured["spec"] = spec
        captured["show_progress"] = show_progress
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
                )
            ],
        )

    monkeypatch.setattr(cli_app, "simulate_batch", fake_simulate_batch)

    assert cli_app.main(["sim", "run", "--preset", "smart_lock", "--runs", "3"]) == 0
    body = json.loads(capsys.readouterr().out)
    spec = captured["spec"]

    assert captured["show_progress"] is True
    assert spec.runs == 3
    assert spec.modes == ["hsw_cr"]
    assert (spec.command_risk or {})["UNLOCK"] == 1.0
    assert body["config"]["runs"] == 3


def test_cli_advise_reads_profile(capsys):
    assert cli_app.main(["advise", "--profile", "presets/smart_lock.yaml"]) == 0

    body = json.loads(capsys.readouterr().out)
    assert body["mode"] == "hsw_cr"
    assert "UNLOCK" in body["challenge_for"]
