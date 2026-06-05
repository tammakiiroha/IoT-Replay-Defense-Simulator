import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from replay.api import create_app
from replay.contracts import (
    ArtifactManifest,
    ExperimentArtifact,
    LabValidationArtifact,
    SimulationBatchResult,
    SimulationResultRecord,
    SimulationSpec,
    SimulationSpecPublic,
    SimVsHardwareArtifact,
    SweepPoint,
)
from replay.core import DEFAULT_ATTACK_MODE, AttackMode, Mode
from replay.services import simulate_batch

app_module = importlib.import_module("replay.api.app")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VALIDATION_OUTPUT_PATH = "tests/fixtures/lab/validation_sample.json"


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


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


def _sample_lab_validation() -> LabValidationArtifact:
    return LabValidationArtifact(
        artifact_id="validation-test",
        title="Validation Test",
        source_path="physical_experiment/results/validation_test.json",
        summary={"ok": True},
        environment={"profile": "loopback"},
        config={"quick": True},
        results=[{"loss": 0.0, "legit_rate": 1.0}],
        metadata={"source": "test"},
    )


def _sample_sim_vs_hardware() -> SimVsHardwareArtifact:
    return SimVsHardwareArtifact(
        artifact_id="compare-test",
        source_path="physical_experiment/results/validation_test.json",
        summary={"ok": True},
        environment={"profile": "loopback"},
        config={"quick": True},
        results=[{"sim_legit_rate": 1.0, "physical_legit_rate": 0.95}],
        metadata={"source": "test"},
    )


def _sample_experiment_artifact() -> ExperimentArtifact:
    return ExperimentArtifact(
        artifact_id="artifact-test",
        kind="simulation_dataset",
        title="Artifact Test",
        description="Synthetic artifact for route tests.",
        source_path="results/p_loss_sweep.json",
        config_snapshot={"seed": 42},
        summary={"records": 1},
        metrics=[{"mode": "window", "avg_legit_rate": 1.0}],
        metadata={"source": "test"},
    )


def _sample_manifest() -> ArtifactManifest:
    return ArtifactManifest(
        title="Replay Research Showcase",
        description="Synthetic manifest for route tests.",
        artifacts=[],
        highlights=[{"label": "Authority", "value": "Python"}],
        navigation=[{"href": "/", "label": "Overview"}],
    )


def _integration_spec() -> SimulationSpec:
    return SimulationSpec(
        modes=["no_def"],
        runs=1,
        num_legit=3,
        num_replay=2,
        seed=123,
    )


def _integration_sweep_payload() -> dict[str, object]:
    return {
        "sweep_type": "p_loss",
        "values": [0.0],
        "simulation": _integration_spec().model_dump(mode="json"),
        "fixed_p_reorder": 0.0,
    }


def _stable_result_view(result: dict[str, object]) -> dict[str, object]:
    stable = dict(result)
    metadata_value = stable.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else {}
    stable["metadata"] = {"total_runs": metadata.get("total_runs")}
    return stable


def test_api_validation_rejects_negative_runs():
    with pytest.raises(ValidationError):
        SimulationSpec(modes=["no_def"], runs=-1)


def test_api_validation_requires_window_size_for_window_mode():
    with pytest.raises(ValidationError):
        SimulationSpec(modes=["window"], window_size=0)


def test_api_default_attack_mode_uses_centralized_default():
    req = SimulationSpec(modes=["no_def"])
    assert req.attack_mode == DEFAULT_ATTACK_MODE


def test_post_simulations_route_returns_batch_payload(monkeypatch, client):
    captured = {}

    def fake_simulate_batch(spec, show_progress=False):
        captured["spec"] = spec
        captured["show_progress"] = show_progress
        return _sample_batch(spec)

    monkeypatch.setattr(app_module, "simulate_batch", fake_simulate_batch)

    response = client.post(
        "/api/v1/simulations",
        json={"modes": ["window"], "runs": 9, "window_size": 5, "seed": 123},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "2026-03-16"
    assert body["config"]["seed"] == 123
    assert body["results"][0]["mode"] == "window"
    assert captured["spec"].runs == 9
    assert captured["show_progress"] is False


def test_post_simulations_route_smoke_uses_real_service(client):
    spec = _integration_spec()
    expected = simulate_batch(spec, show_progress=False).model_dump(mode="json")

    response = client.post("/api/v1/simulations", json=spec.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == expected["schema_version"]
    assert body["config"] == expected["config"]
    assert body["metadata"] == expected["metadata"]
    assert body["generated_at"]
    assert [_stable_result_view(result) for result in body["results"]] == [
        _stable_result_view(result) for result in expected["results"]
    ]


def test_legacy_simulate_route_returns_compat_payload(monkeypatch, client):
    def fake_simulate_batch(spec, show_progress=False):
        return _sample_batch(spec)

    monkeypatch.setattr(app_module, "simulate_batch", fake_simulate_batch)

    response = client.post("/simulate", json={"modes": ["no_def"], "runs": 2, "seed": 42})

    assert response.status_code == 200
    body = response.json()
    assert "schema_version" not in body
    assert body["config"]["modes"] == ["no_def"]
    assert body["results"][0]["mode"] == "no_def"


def test_legacy_simulate_route_smoke_uses_real_service(client):
    spec = _integration_spec()
    expected_batch = simulate_batch(spec, show_progress=False).model_dump(mode="json")

    response = client.post("/simulate", json=spec.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["config"] == expected_batch["config"]
    assert body["metadata"] == expected_batch["metadata"]
    assert [_stable_result_view(result) for result in body["results"]] == [
        _stable_result_view(result) for result in expected_batch["results"]
    ]


def test_post_simulations_route_returns_422_for_invalid_body(client):
    response = client.post("/api/v1/simulations", json={"modes": ["no_def"], "runs": -1})

    assert response.status_code == 422


def test_post_sweeps_route_returns_points(monkeypatch, client):
    def fake_run_sweep(spec, show_progress=False):
        return [
            SweepPoint(
                sweep_type=spec.sweep_type,
                sweep_value=0.1,
                result=_sample_batch(spec.simulation).results[0],
            )
        ]

    monkeypatch.setattr(app_module, "run_sweep", fake_run_sweep)

    response = client.post(
        "/api/v1/sweeps",
        json={
            "sweep_type": "p_loss",
            "values": [0.1],
            "simulation": {"modes": ["no_def"], "runs": 3},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "2026-03-16"
    assert body["points"][0]["sweep_type"] == "p_loss"


def test_post_sweeps_route_smoke_uses_real_service(client):
    response = client.post("/api/v1/sweeps", json=_integration_sweep_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "2026-03-16"
    assert body["generated_at"] is None
    assert len(body["points"]) == 1
    assert body["points"][0]["sweep_type"] == "p_loss"
    assert body["points"][0]["sweep_value"] == 0.0
    assert body["points"][0]["result"]["mode"] == "no_def"
    assert body["points"][0]["result"]["runs"] == 1
    assert body["points"][0]["result"]["metadata"]["total_runs"] == 1


def test_post_lab_validations_route_returns_payload(monkeypatch, client):
    monkeypatch.setattr(app_module, "validate_lab_run", lambda spec: _sample_lab_validation())

    response = client.post("/api/v1/lab/validations", json={})

    assert response.status_code == 200
    assert response.json()["artifact_id"] == "validation-test"


def test_post_lab_validations_route_wraps_errors(monkeypatch, client):
    def fake_validate_lab_run(spec):
        raise RuntimeError("hardware unavailable")

    monkeypatch.setattr(app_module, "validate_lab_run", fake_validate_lab_run)

    response = client.post("/api/v1/lab/validations", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "hardware unavailable"


def test_post_lab_validations_route_smoke_uses_existing_artifact(monkeypatch, client):
    captured = {}

    def fake_run(command, cwd, check, timeout):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        captured["timeout"] = timeout

    monkeypatch.setattr("replay.services.lab.subprocess.run", fake_run)

    response = client.post(
        "/api/v1/lab/validations",
        json={"output_path": FIXTURE_VALIDATION_OUTPUT_PATH},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["artifact_id"].startswith("validation-")
    assert body["title"] == "Physical Validation"
    assert body["source_path"] == FIXTURE_VALIDATION_OUTPUT_PATH
    assert body["metadata"]["provenance"]["source_format"] == "lab_validation_json"
    assert body["metadata"]["provenance"]["source_path"] == FIXTURE_VALIDATION_OUTPUT_PATH
    assert captured["check"] is True
    assert captured["timeout"] == 600
    assert "--output" in captured["command"]
    assert str(PROJECT_ROOT / FIXTURE_VALIDATION_OUTPUT_PATH) in captured["command"]


def test_post_lab_validations_route_rejects_output_path_outside_project(monkeypatch, client):
    captured = {"called": False}

    def fake_run(command, cwd, check):
        captured["called"] = True

    monkeypatch.setattr("replay.services.lab.subprocess.run", fake_run)

    response = client.post("/api/v1/lab/validations", json={"output_path": "/tmp/outside.json"})

    assert response.status_code == 400
    assert "within project root" in response.json()["detail"]
    assert captured["called"] is False


def test_post_lab_validations_route_preserves_500_for_non_path_value_error(monkeypatch, client):
    def fake_validate_lab_run(spec):
        raise json.JSONDecodeError("malformed validation payload", "{}", 0)

    monkeypatch.setattr(app_module, "validate_lab_run", fake_validate_lab_run)

    response = client.post("/api/v1/lab/validations", json={})

    assert response.status_code == 500
    assert "malformed validation payload" in response.json()["detail"]


def test_post_lab_validations_route_preserves_500_for_execution_file_not_found(
    monkeypatch, client
):
    def fake_validate_lab_run(spec):
        raise FileNotFoundError("validation runner output missing")

    monkeypatch.setattr(app_module, "validate_lab_run", fake_validate_lab_run)

    response = client.post("/api/v1/lab/validations", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "validation runner output missing"


def test_post_lab_compare_route_returns_payload(monkeypatch, client):
    monkeypatch.setattr(
        app_module,
        "compare_sim_vs_hardware",
        lambda spec: _sample_sim_vs_hardware(),
    )

    response = client.post("/api/v1/lab/compare", json={})

    assert response.status_code == 200
    assert response.json()["artifact_id"] == "compare-test"


def test_post_lab_compare_route_wraps_errors(monkeypatch, client):
    def fake_compare_sim_vs_hardware(spec):
        raise RuntimeError("comparison failed")

    monkeypatch.setattr(app_module, "compare_sim_vs_hardware", fake_compare_sim_vs_hardware)

    response = client.post("/api/v1/lab/compare", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "comparison failed"


def test_post_lab_compare_route_smoke_uses_real_artifact(client):
    response = client.post(
        "/api/v1/lab/compare",
        json={"output_path": FIXTURE_VALIDATION_OUTPUT_PATH},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["artifact_id"].startswith("sim-vs-hardware-")
    assert body["source_path"] == FIXTURE_VALIDATION_OUTPUT_PATH
    assert body["metadata"]["comparison_type"] == "simulation_vs_hardware"
    assert body["metadata"]["provenance"]["source_format"] == "lab_validation_json"


def test_post_lab_compare_route_rejects_output_path_outside_project(client):
    response = client.post("/api/v1/lab/compare", json={"output_path": "/tmp/outside.json"})

    assert response.status_code == 400
    assert "within project root" in response.json()["detail"]


def test_post_lab_compare_route_returns_404_for_missing_artifact(client):
    response = client.post(
        "/api/v1/lab/compare",
        json={"output_path": "tests/fixtures/lab/missing_validation_sample.json"},
    )

    assert response.status_code == 404
    assert "Validation artifact not found" in response.json()["detail"]
    assert "missing_validation_sample.json" in response.json()["detail"]


def test_get_artifact_route_returns_payload(monkeypatch, client):
    monkeypatch.setattr(
        app_module,
        "load_experiment_artifact",
        lambda artifact_id: _sample_experiment_artifact(),
    )

    response = client.get("/api/v1/artifacts/artifact-test")

    assert response.status_code == 200
    assert response.json()["artifact_id"] == "artifact-test"


def test_get_artifact_route_returns_404(monkeypatch, client):
    def fake_load_experiment_artifact(artifact_id):
        raise FileNotFoundError("missing artifact")

    monkeypatch.setattr(app_module, "load_experiment_artifact", fake_load_experiment_artifact)

    response = client.get("/api/v1/artifacts/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "missing artifact"


def test_get_demo_manifest_route_returns_payload(monkeypatch, client):
    monkeypatch.setattr(app_module, "load_artifact_manifest", lambda: _sample_manifest())

    response = client.get("/api/v1/demo/manifest")

    assert response.status_code == 200
    assert response.json()["schema_version"] == "2026-03-16"
    assert response.json()["title"] == "Replay Research Showcase"


def test_get_demo_manifest_route_builds_fallback(monkeypatch, client):
    def fake_load_manifest():
        raise FileNotFoundError

    monkeypatch.setattr(app_module, "load_artifact_manifest", fake_load_manifest)
    monkeypatch.setattr(app_module, "build_demo_artifacts", lambda: _sample_manifest())

    response = client.get("/api/v1/demo/manifest")

    assert response.status_code == 200
    assert response.json()["description"] == "Synthetic manifest for route tests."


def test_get_demo_manifest_route_smoke_uses_real_manifest(client):
    response = client.get("/api/v1/demo/manifest")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "2026-03-16"
    assert body["artifacts"]
    assert "simulation_dataset" in {artifact["kind"] for artifact in body["artifacts"]}
