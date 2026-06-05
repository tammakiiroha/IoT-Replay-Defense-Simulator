"""Primary FastAPI app for the Replay platform."""
from __future__ import annotations

import os
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from replay.contracts import LabValidationSpec, SimulationSpec, SweepSpec
from replay.services import (
    build_demo_artifacts,
    compare_sim_vs_hardware,
    load_artifact_manifest,
    load_experiment_artifact,
    run_sweep,
    simulate_batch,
    validate_lab_run,
)
from replay.services.lab import LabValidationPathError


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_cors_allow_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


def create_app() -> FastAPI:
    app = FastAPI(title="Replay Research Platform", version="0.1.0")

    cors_allow_origins = _parse_cors_allow_origins()
    cors_allow_credentials = _as_bool(os.getenv("CORS_ALLOW_CREDENTIALS"), default=True)
    if "*" in cors_allow_origins and cors_allow_credentials:
        cors_allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"status": "ok", "message": "Replay Research Platform API is running"}

    @app.post("/api/v1/simulations")
    def post_simulations(spec: SimulationSpec) -> dict[str, object]:
        return simulate_batch(spec, show_progress=False).model_dump(mode="json")

    @app.post("/simulate")
    def legacy_post_simulations(spec: SimulationSpec) -> dict[str, object]:
        batch = simulate_batch(spec, show_progress=False)
        return {
            "config": batch.config.model_dump(mode="json"),
            "results": [entry.model_dump(mode="json") for entry in batch.results],
            "metadata": batch.metadata,
        }

    @app.post("/api/v1/sweeps")
    def post_sweeps(spec: SweepSpec) -> dict[str, object]:
        return {
            "schema_version": spec.schema_version,
            "generated_at": None,
            "points": [
                point.model_dump(mode="json")
                for point in run_sweep(spec, show_progress=False)
            ],
        }

    @app.post("/api/v1/lab/validations")
    def post_lab_validations(spec: LabValidationSpec) -> dict[str, object]:
        try:
            return validate_lab_run(spec).model_dump(mode="json")
        except LabValidationPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=504,
                detail=f"validation timed out: {exc}",
            ) from exc
        except Exception as exc:  # pragma: no cover - hardware wrapper safety
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v1/lab/compare")
    def post_lab_compare(spec: LabValidationSpec) -> dict[str, object]:
        try:
            return compare_sim_vs_hardware(spec).model_dump(mode="json")
        except LabValidationPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - hardware wrapper safety
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str) -> dict[str, object]:
        try:
            return load_experiment_artifact(artifact_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/demo/manifest")
    def get_demo_manifest() -> dict[str, object]:
        try:
            return load_artifact_manifest().model_dump(mode="json")
        except FileNotFoundError:
            manifest = build_demo_artifacts()
            return manifest.model_dump(mode="json")

    return app


app = create_app()


def run_simulation(spec: SimulationSpec) -> dict[str, object]:
    """Compatibility wrapper used by existing unit tests."""

    return simulate_batch(spec, show_progress=False).model_dump(mode="json")
