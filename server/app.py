"""
Lead-Ops · FastAPI Application
==============================
Entrypoint for the OpenEnv environment server.

Provides the OpenEnv REST API:
- GET  /state/{session_id}
- POST /reset
- POST /step
"""

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

from session_manager import SessionManager
from environment import LeadOpsEnv
from models import TaskID, Action, LeadObservation, StepResult

app = FastAPI(
    title="Lead-Ops OpenEnv",
    description="RL environment for autonomous sales lead enrichment, MEDDIC qualification, and strategic routing.",
    version="1.0.0",
)

# Global instances
sm = SessionManager()
env = LeadOpsEnv(sm)

# ── API Models ──────────────────────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: TaskID

class ResetResponse(BaseModel):
    session_id: str
    observation: LeadObservation

class StepRequest(BaseModel):
    session_id: str
    action: Action

# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy", 
        "version": "1.0.0",
        "active_sessions": sm.active_count
    }

@app.post("/reset", response_model=ResetResponse)
async def reset(req: ResetRequest = Body(...)):
    """Initialize a new RL episode."""
    try:
        session_id, obs = env.reset(req.task_id)
        return {"session_id": session_id, "observation": obs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/step", response_model=StepResult)
async def step(req: StepRequest = Body(...)):
    """Execute an action and advance the environment."""
    try:
        result = env.step(req.session_id, req.action)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/state/{session_id}")
async def state(session_id: str):
    """Retrieve full database state for debugging constraints."""
    try:
        return env.state(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
