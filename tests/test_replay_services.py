from pathlib import Path

import pytest

from replay.contracts import LabValidationSpec, SimulationSpec, SweepSpec
from replay.services import (
    compare_sim_vs_hardware,
    load_lab_validation_artifact,
    run_sweep,
    simulate_batch,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAB_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "lab" / "validation_sample.json"


def test_simulate_batch_returns_authoritative_contract():
    batch = simulate_batch(
        SimulationSpec(modes=["window"], runs=4, seed=42, window_size=5),
        show_progress=False,
    )

    assert batch.schema_version == "2026-03-16"
    assert batch.config.modes == ["window"]
    assert batch.results[0].mode == "window"


def test_run_sweep_returns_points():
    points = run_sweep(
        SweepSpec(
            sweep_type="p_loss",
            values=[0.0, 0.1],
            simulation=SimulationSpec(modes=["no_def"], runs=3, seed=42),
            fixed_p_reorder=0.0,
        ),
        show_progress=False,
    )

    assert len(points) == 2
    assert all(point.sweep_type == "p_loss" for point in points)


def test_load_lab_validation_artifact_preserves_provenance():
    artifact = load_lab_validation_artifact(LAB_FIXTURE_PATH)

    assert artifact.source_path == str(LAB_FIXTURE_PATH.relative_to(PROJECT_ROOT))
    assert artifact.metadata["provenance"]["source_path"] == artifact.source_path
    assert artifact.metadata["provenance"]["source_file"] == LAB_FIXTURE_PATH.name
    assert artifact.metadata["provenance"]["source_format"] == "lab_validation_json"
    assert "counting_rules" in artifact.metadata
    assert "conclusion_scope" in artifact.metadata


def test_compare_sim_vs_hardware_uses_canonical_metadata():
    artifact = compare_sim_vs_hardware(
        LabValidationSpec(output_path=str(LAB_FIXTURE_PATH.relative_to(PROJECT_ROOT)))
    )

    assert artifact.artifact_id.startswith("sim-vs-hardware-")
    assert artifact.title == "Simulation vs Hardware Validation"
    assert artifact.metadata["comparison_type"] == "simulation_vs_hardware"
    assert artifact.metadata["provenance"]["source_path"] == artifact.source_path


def test_load_lab_validation_artifact_rejects_output_path_outside_project():
    with pytest.raises(ValueError, match="within project root"):
        compare_sim_vs_hardware(LabValidationSpec(output_path="/tmp/outside-validation.json"))


def test_lab_spec_has_timeout_default():
    assert LabValidationSpec().timeout_seconds == 600


def test_run_sweep_supports_mac_tag_bits():
    spec = SweepSpec(
        sweep_type="mac_tag_bits",
        values=[32, 48, 64, 80, 96, 128],
        simulation=SimulationSpec(
            modes=["window"],
            runs=2,
            num_legit=3,
            num_replay=3,
            seed=1,
            window_size=5,
        ),
    )

    points = run_sweep(spec, show_progress=False)

    assert len(points) == 6
    assert [point.result.mac_tag_bits for point in points] == [32, 48, 64, 80, 96, 128]
