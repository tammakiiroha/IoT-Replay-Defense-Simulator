from __future__ import annotations

from replay.api import app, create_app
from replay.contracts import SimulationSpec as SimulationRequest
from replay.services import simulate_batch


def run_simulation(req: SimulationRequest) -> dict[str, object]:
    batch = simulate_batch(req, show_progress=False)
    return {
        "schema_version": batch.schema_version,
        "config": batch.config.model_dump(mode="json"),
        "results": [entry.model_dump(mode="json") for entry in batch.results],
        "metadata": batch.metadata,
    }


__all__ = ["SimulationRequest", "app", "create_app", "run_simulation"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
