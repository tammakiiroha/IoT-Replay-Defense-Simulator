"""Thin wrappers around the existing physical validation scripts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from replay.contracts import (
    LabValidationArtifact,
    LabValidationSpec,
    SimVsHardwareArtifact,
    normalize_artifact_id,
)


class LabValidationPathError(ValueError):
    """Raised when a lab artifact path falls outside the project boundary."""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _python_bin(root: Path) -> Path:
    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path("python3")


def _latest_validation_path(root: Path) -> Path:
    candidates = sorted((root / "physical_experiment" / "results").glob("validation_*.json"))
    if not candidates:
        raise FileNotFoundError("No validation artifact found in physical_experiment/results")
    return candidates[-1]


def _resolve_validation_path(root: Path, output_path: str) -> Path:
    root_resolved = root.resolve()
    candidate = Path(output_path).expanduser()
    if not candidate.is_absolute():
        candidate = root_resolved / candidate

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise LabValidationPathError(
            f"output_path must be within project root: {root_resolved}"
        ) from exc
    return resolved


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_jsonable(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(inner) for inner in value]
    return value


def _lab_provenance(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    environment = payload.get("environment", {})
    return {
        "source_path": str(path.relative_to(_project_root())),
        "source_file": path.name,
        "source_format": "lab_validation_json",
        "validation_time": payload.get("validation_time"),
        "git_commit": environment.get("git_commit"),
        "hardware_info_available": bool(environment.get("hackrf_info")),
    }


def load_lab_validation_artifact(path: Path) -> LabValidationArtifact:
    payload = json.loads(path.read_text(encoding="utf-8"))
    artifact_id = normalize_artifact_id(path)
    return LabValidationArtifact(
        artifact_id=artifact_id,
        title="Physical Validation",
        source_path=str(path.relative_to(_project_root())),
        summary=_to_jsonable(payload.get("summary", {})),
        environment=_to_jsonable(payload.get("environment", {})),
        config=_to_jsonable(payload.get("config", {})),
        results=_to_jsonable(payload.get("results", [])),
        metadata={
            "counting_rules": _to_jsonable(payload.get("counting_rules", {})),
            "conclusion_scope": _to_jsonable(payload.get("conclusion_scope", {})),
            "provenance": _lab_provenance(path, payload),
        },
    )


def validate_lab_run(spec: LabValidationSpec, *, execute: bool = True) -> LabValidationArtifact:
    root = _project_root()
    resolved_output_path = (
        _resolve_validation_path(root, spec.output_path) if spec.output_path else None
    )
    display_output_path = (
        str(resolved_output_path.relative_to(root)) if resolved_output_path else None
    )

    if execute:
        command = [
            str(_python_bin(root)),
            str(root / "physical_experiment" / "scripts" / "run_validation.py"),
        ]
        if spec.loopback:
            command.append("--loopback")
        if spec.quick:
            command.append("--quick")
        if spec.goal_check:
            command.append("--goal-check")
        if spec.loss_samples:
            command.extend(["--loss-samples", ",".join(str(value) for value in spec.loss_samples)])
        if spec.output_path:
            command.extend(["--output", str(resolved_output_path)])
        command.extend(spec.extra_args)
        subprocess.run(command, cwd=root, check=True, timeout=spec.timeout_seconds)
        if resolved_output_path and not resolved_output_path.exists():
            raise RuntimeError(
                f"Validation run did not produce artifact: {display_output_path}"
            )
    elif resolved_output_path and not resolved_output_path.exists():
        raise FileNotFoundError(
            f"Validation artifact not found: {display_output_path}"
        )

    path = resolved_output_path if resolved_output_path else _latest_validation_path(root)
    return load_lab_validation_artifact(path)


def compare_sim_vs_hardware(spec: LabValidationSpec | None = None) -> SimVsHardwareArtifact:
    artifact = validate_lab_run(spec or LabValidationSpec(), execute=False)
    metadata = dict(artifact.metadata)
    metadata["comparison_type"] = "simulation_vs_hardware"
    return SimVsHardwareArtifact(
        artifact_id=f"sim-vs-hardware-{artifact.artifact_id}",
        source_path=artifact.source_path,
        summary=artifact.summary,
        environment=artifact.environment,
        config=artifact.config,
        results=artifact.results,
        metadata=metadata,
    )
