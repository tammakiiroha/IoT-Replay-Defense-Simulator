from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sim.experiment import run_many_experiments
from sim.types import Mode, AttackMode, SimulationConfig, AggregateStats

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, set this to ["http://localhost:3000", "http://localhost:3001"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulationRequest(BaseModel):
    modes: List[str]
    runs: int = 200
    p_loss: float = 0.0
    p_reorder: float = 0.0
    window_size: int = 5
    num_legit: int = 20
    num_replay: int = 100
    attack_mode: str = "post" # "post" or "inline"

@app.get("/")
def read_root():
    return {"status": "ok", "message": "IoT Replay Simulator API is running"}

@app.post("/simulate")
def run_simulation(req: SimulationRequest):
    try:
        # Map string modes to Enum
        try:
            selected_modes = [Mode(m) for m in req.modes]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {e}")

        try:
            attack_mode_enum = AttackMode(req.attack_mode)
        except ValueError as e:
             raise HTTPException(status_code=400, detail=f"Invalid attack mode: {e}")

        # Create base config
        config = SimulationConfig(
            mode=Mode.NO_DEFENSE, # placeholder, will be overridden by run_many_experiments per mode
            attack_mode=attack_mode_enum,
            num_legit=req.num_legit,
            num_replay=req.num_replay,
            p_loss=req.p_loss,
            p_reorder=req.p_reorder,
            window_size=req.window_size,
            # Use default command set internally
        )

        # Run experiments
        # run_many_experiments returns List[AggregateStats]
        results: List[AggregateStats] = run_many_experiments(
            base_config=config,
            modes=selected_modes,
            runs=req.runs,
            show_progress=False # Disable CLI progress bar
        )

        # Convert to JSON-compatible dict
        return {
            "config": req.dict(),
            "results": [r.as_dict() for r in results]
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
