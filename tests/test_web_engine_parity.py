from pathlib import Path

from replay.services import build_demo_artifacts, load_artifact_manifest, load_experiment_artifact

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_contracts_and_manifest_are_generated_for_web():
    manifest = build_demo_artifacts(PROJECT_ROOT)

    contracts_path = PROJECT_ROOT / "web" / "lib" / "contracts.ts"
    schema_path = PROJECT_ROOT / "web" / "public" / "data" / "contracts.json"
    manifest_path = PROJECT_ROOT / "web" / "public" / "data" / "manifest.json"

    assert contracts_path.exists()
    assert schema_path.exists()
    assert manifest_path.exists()
    assert "SimulationSpec" in contracts_path.read_text(encoding="utf-8")
    assert manifest.artifacts


def test_manifest_loader_reads_generated_manifest():
    manifest = load_artifact_manifest(PROJECT_ROOT)

    assert manifest.schema_version == "2026-03-16"
    assert any(artifact.kind == "simulation_dataset" for artifact in manifest.artifacts)


def test_simulation_artifacts_include_reproducibility_metadata():
    manifest = build_demo_artifacts(PROJECT_ROOT)
    simulation_summary = next(
        artifact for artifact in manifest.artifacts if artifact.kind == "simulation_dataset"
    )

    artifact = load_experiment_artifact(simulation_summary.artifact_id, PROJECT_ROOT)

    assert artifact.config_snapshot
    assert "seed" in artifact.config_snapshot
    assert "provenance" in artifact.metadata
    assert artifact.metadata["provenance"]["source_path"] == artifact.source_path


def test_lab_artifacts_include_reproducibility_metadata():
    manifest = build_demo_artifacts(PROJECT_ROOT)
    lab_summary = next(
        artifact for artifact in manifest.artifacts if artifact.kind == "lab_validation"
    )

    artifact = load_experiment_artifact(lab_summary.artifact_id, PROJECT_ROOT)

    assert artifact.config_snapshot
    assert "environment" in artifact.metadata
    assert "provenance" in artifact.metadata
    assert artifact.metadata["provenance"]["source_path"] == artifact.source_path
