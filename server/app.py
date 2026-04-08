"""
Lead-Ops · FastAPI Application
==============================
Entrypoint for the OpenEnv environment server.

Provides the OpenEnv REST API:
    - GET  /health               — container health check (200 OK)
    - GET  /state/{session_id}   — database state snapshot
    - POST /reset                — initialize a new episode
    - POST /step                 — execute an action

Port: 7860 (Hugging Face Spaces requirement)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, ValidationError

from session_manager import SessionManager
from environment import LeadOpsEnv
from models import TaskID, Action, LeadObservation, StepResult

app = FastAPI(
    title="Lead-Ops OpenEnv",
    description=(
        "RL environment for autonomous sales lead enrichment, "
        "MEDDIC qualification, and strategic routing."
    ),
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
    task_id: str
    observation: LeadObservation


class StepRequest(BaseModel):
    session_id: str
    action: Action


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Basic health check endpoint for HF Spaces monitoring."""
    from config import get_settings
    settings = get_settings()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "active_sessions": sm.active_count,
        "configured": settings.is_configured,
    }


@app.post("/reset", response_model=ResetResponse)
async def reset(data: Optional[dict] = Body(None)):
    """Initialize a new RL episode.

    Accepts optional body to stay robust against validators that send null.
    Defaults to task_id='enrich_lead' when payload is missing.
    """
    try:
        if data is None:
            data = {}

        raw_task_id = data.get("task_id", TaskID.ENRICH_LEAD.value)
        try:
            task_id = TaskID(raw_task_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task_id '{raw_task_id}'. Expected one of: enrich_lead, meddic_qualify, strategic_route.",
            )

        session_id, obs = env.reset(task_id)
        return {
            "session_id": session_id,
            "task_id": task_id.value,
            "observation": obs,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step", response_model=StepResult)
async def step(data: Optional[dict] = Body(None)):
    """Execute an action and advance the environment.

    Uses explicit validation to avoid FastAPI's automatic 422 for null payloads.
    """
    try:
        if data is None:
            data = {}

        try:
            req = StepRequest.model_validate(data)
        except ValidationError:
            raise HTTPException(
                status_code=400,
                detail="Missing or invalid step payload. Required keys: session_id, action.",
            )

        result = env.step(req.session_id, req.action)
        return result
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/state/{session_id}")
async def state(session_id: str):
    """Retrieve full database state for debugging."""
    try:
        return env.state(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Direct run (for local testing) ──────────────────────────────────────────

def main() -> None:
    """Run the API server for local and script-based entrypoints."""
    import uvicorn
    import os

    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()
