"""Build and load static artifacts for the standalone web experience."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from replay.contracts import (
    ArtifactManifest,
    ArtifactSummary,
    ExperimentArtifact,
    normalize_artifact_id,
    write_contract_artifacts,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _data_root(project_root: Path | None = None) -> Path:
    root = project_root or _project_root()
    return root / "web" / "public" / "data"


def _artifact_dir(project_root: Path | None = None) -> Path:
    return _data_root(project_root) / "artifacts"


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_jsonable(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(inner) for inner in value]
    return value


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _unique_values(payload: list[dict[str, Any]], key: str) -> list[Any]:
    values = {item[key] for item in payload if key in item}
    return sorted(values)


def _constant_value(payload: list[dict[str, Any]], key: str) -> Any:
    values = _unique_values(payload, key)
    if len(values) == 1:
        return values[0]
    return None


def _source_path(path: Path, project_root: Path) -> str:
    return str(path.relative_to(project_root))


def _simulation_config_snapshot(
    path: Path,
    payload: list[dict[str, Any]],
    project_root: Path,
) -> dict[str, Any]:
    source_path = _source_path(path, project_root)
    snapshot: dict[str, Any] = {
        "seed": None,
        "source_path": source_path,
        "modes": _unique_values(payload, "mode"),
        "runs": _constant_value(payload, "runs"),
        "num_legit": _constant_value(payload, "num_legit"),
        "num_replay": _constant_value(payload, "num_replay"),
        "attack_mode": _constant_value(payload, "attack_mode"),
        "fixed_parameters": {
            "p_loss": _constant_value(payload, "p_loss"),
            "p_reorder": _constant_value(payload, "p_reorder"),
            "window_size": _constant_value(payload, "window_size"),
        },
    }
    sweep_type = _constant_value(payload, "sweep_type")
    if sweep_type is not None:
        snapshot["sweep"] = {
            "type": sweep_type,
            "values": _unique_values(payload, "sweep_value"),
        }
    return _to_jsonable(snapshot)


def _simulation_provenance(
    path: Path,
    payload: list[dict[str, Any]],
    project_root: Path,
) -> dict[str, Any]:
    return {
        "source_path": _source_path(path, project_root),
        "source_file": path.name,
        "source_format": "legacy_aggregate_rows",
        "row_count": len(payload),
        "config_inference": "inferred_from_dataset_rows",
        "seed": None,
        "seed_note": "Legacy aggregate rows do not encode the RNG seed.",
    }


def _lab_provenance(path: Path, payload: dict[str, Any], project_root: Path) -> dict[str, Any]:
    environment = payload.get("environment", {})
    return {
        "source_path": _source_path(path, project_root),
        "source_file": path.name,
        "source_format": "lab_validation_json",
        "validation_time": payload.get("validation_time"),
        "git_commit": environment.get("git_commit"),
        "hardware_info_available": bool(environment.get("hackrf_info")),
    }


def _summarize_simulation_dataset(
    path: Path,
    payload: list[dict[str, Any]],
    project_root: Path,
) -> ExperimentArtifact:
    top_legit = max(payload, key=lambda item: item.get("avg_legit_rate", 0.0), default={})
    lowest_attack = min(payload, key=lambda item: item.get("avg_attack_rate", 1.0), default={})
    artifact_id = normalize_artifact_id(path)
    return ExperimentArtifact(
        artifact_id=artifact_id,
        kind="simulation_dataset",
        title=path.stem.replace("_", " ").title(),
        description=f"Versioned simulation dataset exported from {path.name}.",
        source_path=_source_path(path, project_root),
        config_snapshot=_simulation_config_snapshot(path, payload, project_root),
        summary={
            "records": len(payload),
            "best_legit_mode": top_legit.get("mode"),
            "best_legit_rate": top_legit.get("avg_legit_rate"),
            "lowest_attack_mode": lowest_attack.get("mode"),
            "lowest_attack_rate": lowest_attack.get("avg_attack_rate"),
        },
        metrics=_to_jsonable(payload),
        metadata={
            "dataset_type": "simulation",
            "provenance": _simulation_provenance(path, payload, project_root),
        },
    )


def _summarize_lab_dataset(
    path: Path,
    payload: dict[str, Any],
    project_root: Path,
) -> ExperimentArtifact:
    results = payload.get("results", [])
    artifact_id = normalize_artifact_id(path)
    return ExperimentArtifact(
        artifact_id=artifact_id,
        kind="lab_validation",
        title=path.stem.replace("_", " ").title(),
        description=f"Physical validation artifact derived from {path.name}.",
        source_path=_source_path(path, project_root),
        config_snapshot=_to_jsonable(payload.get("config", {})),
        summary=_to_jsonable(payload.get("summary", {})),
        metrics=_to_jsonable(results),
        metadata={
            "dataset_type": "lab_validation",
            "environment": _to_jsonable(payload.get("environment", {})),
            "counting_rules": _to_jsonable(payload.get("counting_rules", {})),
            "conclusion_scope": _to_jsonable(payload.get("conclusion_scope", {})),
            "provenance": _lab_provenance(path, payload, project_root),
        },
    )


def build_demo_artifacts(project_root: Path | None = None) -> ArtifactManifest:
    root = project_root or _project_root()
    data_root = _data_root(root)
    artifact_dir = _artifact_dir(root)
    data_root.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    write_contract_artifacts(root)

    source_files = [
        root / "results" / "p_loss_sweep.json",
        root / "results" / "p_reorder_sweep.json",
        root / "results" / "window_sweep.json",
    ]
    latest_validation = sorted((root / "physical_experiment" / "results").glob("validation_*.json"))
    if latest_validation:
        source_files.append(latest_validation[-1])

    artifacts: list[ExperimentArtifact] = []
    summaries: list[ArtifactSummary] = []

    for source in source_files:
        if not source.exists():
            continue
        payload = _load_json(source)
        artifact = (
            _summarize_simulation_dataset(source, payload, root)
            if isinstance(payload, list)
            else _summarize_lab_dataset(source, payload, root)
        )
        artifact_path = artifact_dir / f"{artifact.artifact_id}.json"
        artifact_path.write_text(
            json.dumps(artifact.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        summaries.append(
            ArtifactSummary(
                artifact_id=artifact.artifact_id,
                title=artifact.title,
                kind=artifact.kind,
                path=f"/data/artifacts/{artifact_path.name}",
                description=artifact.description,
                updated_at=datetime.now(timezone.utc),
            )
        )
        artifacts.append(artifact)

    if not any(artifact.kind == "lab_validation" for artifact in artifacts):
        # Raw hardware outputs are local-only; preserve checked-in lab artifacts.
        for artifact_path in sorted(artifact_dir.glob("*.json")):
            try:
                artifact = ExperimentArtifact.model_validate(_load_json(artifact_path))
            except ValueError:
                continue
            if artifact.kind != "lab_validation":
                continue
            summaries.append(
                ArtifactSummary(
                    artifact_id=artifact.artifact_id,
                    title=artifact.title,
                    kind=artifact.kind,
                    path=f"/data/artifacts/{artifact_path.name}",
                    description=artifact.description,
                    updated_at=datetime.fromtimestamp(artifact_path.stat().st_mtime, timezone.utc),
                )
            )
            artifacts.append(artifact)

    manifest = ArtifactManifest(
        title="Replay Research Showcase",
        description="Static artifacts and experiment evidence backing the replay-defense thesis.",
        artifacts=summaries,
        highlights=[
            {
                "label": "Authority",
                "value": "Python core is the sole simulation source of truth",
            },
            {
                "label": "Modes",
                "value": "Hybrid local runtime plus static public showcase",
            },
            {
                "label": "Evidence",
                "value": "Simulation sweeps and physical validation artifacts are versioned",
            },
        ],
        navigation=[
            {"href": "/", "label": "Overview"},
            {"href": "/simulator", "label": "Simulator"},
            {"href": "/results", "label": "Results"},
            {"href": "/methodology", "label": "Methodology"},
            {"href": "/hardware", "label": "Hardware"},
            {"href": "/reproducibility", "label": "Reproducibility"},
        ],
    )
    (data_root / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for source in [
        root / "figures" / "p_loss_dual.png",
        root / "figures" / "p_reorder_dual.png",
        root / "figures" / "sim_vs_hw_legit.png",
        root / "figures" / "sim_vs_hw_attack.png",
    ]:
        if source.exists():
            shutil.copy2(source, data_root / source.name)

    return manifest


def load_artifact_manifest(project_root: Path | None = None) -> ArtifactManifest:
    data_root = _data_root(project_root)
    payload = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    return ArtifactManifest.model_validate(payload)


def load_experiment_artifact(
    artifact_id: str,
    project_root: Path | None = None,
) -> ExperimentArtifact:
    artifact_dir = _artifact_dir(project_root)
    payload = json.loads((artifact_dir / f"{artifact_id}.json").read_text(encoding="utf-8"))
    return ExperimentArtifact.model_validate(payload)
