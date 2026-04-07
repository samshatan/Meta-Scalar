"""
FastAPI application for the Incident Response OpenEnv environment.

Endpoints
---------
POST /reset              — Start a new episode
POST /step               — Submit an action
GET  /state              — Full internal state (includes ground truth)
GET  /tasks              — Task list + action schema
POST /grader             — Grade the current episode
POST /baseline           — Run the baseline inference script and return scores
GET  /health             — Health-check
"""

import os
import sys
import subprocess
import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from environment.env import IncidentResponseEnv
from environment.models import Action, Observation, Reward, StepResponse
from environment.tasks import TASKS

app = FastAPI(
    title="Incident Response OpenEnv",
    description=(
        "An OpenEnv-compliant environment where AI agents act as on-call SREs, "
        "triaging production incidents by classifying alerts, investigating services, "
        "applying remediations, and resolving incidents."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global environment instance (single-session; for multi-session use a session map)
_env = IncidentResponseEnv()


# ── Request / response schemas ────────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: str = "alert_classification"
    scenario_index: int = 0


class GraderResponse(BaseModel):
    task_id: str
    score: float
    breakdown: dict
    feedback: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    """Redirect root to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok", "environment": "incident-response-openenv", "version": "1.0.0"}


@app.post("/reset", response_model=Observation)
def reset(req: ResetRequest):
    """Start a fresh episode for the given task."""
    try:
        obs = _env.reset(task_id=req.task_id, scenario_index=req.scenario_index)
        return obs
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step", response_model=StepResponse)
def step(action: Action):
    """Submit an action and receive the next observation + reward."""
    try:
        obs, reward, done, info = _env.step(action)
        return StepResponse(observation=obs, reward=reward, done=done, info=info)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/state")
def state():
    """Return the full environment state (includes ground truth for debugging/grading)."""
    try:
        s = _env.state()
        # Serialise manually to handle enum ground-truth values
        raw = s.model_dump()
        gt = s.ground_truth
        # Convert enums in ground truth
        for k, v in gt.items():
            if hasattr(v, "value"):
                raw["ground_truth"][k] = v.value
            elif isinstance(v, list):
                raw["ground_truth"][k] = [
                    item.value if hasattr(item, "value") else item for item in v
                ]
        return raw
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tasks")
def tasks():
    """List all available tasks with their descriptions and action schemas."""
    result = {}
    for task_id, task in TASKS.items():
        result[task_id] = {
            "id": task["id"],
            "name": task["name"],
            "difficulty": task["difficulty"],
            "description": task["description"],
            "scenario_count": len(task["scenarios"]),
            "action_schema": task["action_schema"],
            "action_type_enum": [
                "classify", "investigate", "remediate", "escalate", "resolve"
            ],
            "incident_categories": [
                "database_connection", "memory_leak", "network_partition",
                "dependency_failure", "resource_exhaustion", "configuration_error"
            ],
            "remediation_actions": [
                "restart_service", "scale_up", "flush_cache", "rollback_deployment",
                "update_config", "kill_long_running_query", "increase_connection_pool",
                "restore_network_policy", "clear_disk_space", "rotate_credentials"
            ],
        }
    return result


@app.post("/grader", response_model=GraderResponse)
def grader():
    """Grade the current (or just-completed) episode."""
    try:
        result = _env.grade()
        s = _env.state()
        return GraderResponse(
            task_id=s.__dict__["_task_id"],
            score=result["score"],
            breakdown=result["breakdown"],
            feedback=result["feedback"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/baseline")
def baseline():
    """
    Run the baseline inference script against all three tasks and return scores.
    Uses OPENAI_API_KEY from environment.
    """
    script = os.path.join(os.path.dirname(__file__), "..", "baseline", "run_baseline.py")
    script = os.path.abspath(script)

    if not os.path.exists(script):
        raise HTTPException(status_code=500, detail="Baseline script not found.")

    env_vars = os.environ.copy()
    result = subprocess.run(
        [sys.executable, script, "--output", "json"],
        capture_output=True,
        text=True,
        timeout=300,
        env=env_vars,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Baseline script failed:\n{result.stderr[:2000]}"
        )

    try:
        scores = json.loads(result.stdout)
    except json.JSONDecodeError:
        scores = {"raw_output": result.stdout[:4000]}

    return {"status": "ok", "baseline_scores": scores}