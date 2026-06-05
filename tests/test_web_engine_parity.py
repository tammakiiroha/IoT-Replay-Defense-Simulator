import shutil
from pathlib import Path

from replay.services import build_demo_artifacts, load_artifact_manifest, load_experiment_artifact

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _copy_fixture_file(root: Path, relative_path: Path) -> None:
    source = PROJECT_ROOT / relative_path
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _artifact_project_root(tmp_path: Path) -> Path:
    root = tmp_path / "artifact-project"
    for relative_path in [
        Path("results/p_loss_sweep.json"),
        Path("results/p_reorder_sweep.json"),
        Path("results/window_sweep.json"),
    ]:
        _copy_fixture_file(root, relative_path)

    latest_validation = sorted(
        (PROJECT_ROOT / "physical_experiment" / "results").glob("validation_*.json")
    )[-1]
    _copy_fixture_file(root, latest_validation.relative_to(PROJECT_ROOT))

    (root / "web" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "web" / "public" / "data" / "artifacts").mkdir(parents=True, exist_ok=True)
    return root


def test_contracts_and_manifest_are_generated_for_web(tmp_path):
    root = _artifact_project_root(tmp_path)
    manifest = build_demo_artifacts(root)

    contracts_path = root / "web" / "lib" / "contracts.ts"
    schema_path = root / "web" / "public" / "data" / "contracts.json"
    manifest_path = root / "web" / "public" / "data" / "manifest.json"

    assert contracts_path.exists()
    assert schema_path.exists()
    assert manifest_path.exists()
    assert "SimulationSpec" in contracts_path.read_text(encoding="utf-8")
    assert manifest.artifacts


def test_manifest_loader_reads_generated_manifest(tmp_path):
    root = _artifact_project_root(tmp_path)
    build_demo_artifacts(root)

    manifest = load_artifact_manifest(root)

    assert manifest.schema_version == "2026-03-16"
    assert any(artifact.kind == "simulation_dataset" for artifact in manifest.artifacts)


def test_simulation_artifacts_include_reproducibility_metadata(tmp_path):
    root = _artifact_project_root(tmp_path)
    manifest = build_demo_artifacts(root)
    simulation_summary = next(
        artifact for artifact in manifest.artifacts if artifact.kind == "simulation_dataset"
    )

    artifact = load_experiment_artifact(simulation_summary.artifact_id, root)

    assert artifact.config_snapshot
    assert "seed" in artifact.config_snapshot
    assert "provenance" in artifact.metadata
    assert artifact.metadata["provenance"]["source_path"] == artifact.source_path


def test_lab_artifacts_include_reproducibility_metadata(tmp_path):
    root = _artifact_project_root(tmp_path)
    manifest = build_demo_artifacts(root)
    lab_summary = next(
        artifact for artifact in manifest.artifacts if artifact.kind == "lab_validation"
    )

    artifact = load_experiment_artifact(lab_summary.artifact_id, root)

    assert artifact.config_snapshot
    assert "environment" in artifact.metadata
    assert "provenance" in artifact.metadata
    assert artifact.metadata["provenance"]["source_path"] == artifact.source_path
