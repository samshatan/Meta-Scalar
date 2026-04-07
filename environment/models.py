"""
Typed Pydantic models for the Incident Response OpenEnv environment.
All action, observation, and reward types are defined here.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


# ── Enumerations ──────────────────────────────────────────────────────────────

class IncidentCategory(str, Enum):
    DATABASE_CONNECTION  = "database_connection"
    MEMORY_LEAK          = "memory_leak"
    NETWORK_PARTITION    = "network_partition"
    DEPENDENCY_FAILURE   = "dependency_failure"
    RESOURCE_EXHAUSTION  = "resource_exhaustion"
    CONFIGURATION_ERROR  = "configuration_error"


class ActionType(str, Enum):
    CLASSIFY    = "classify"     # Label the incident category
    INVESTIGATE = "investigate"  # Fetch logs for a specific service
    REMEDIATE   = "remediate"    # Apply a remediation action
    ESCALATE    = "escalate"     # Hand off to a human team
    RESOLVE     = "resolve"      # Mark the incident resolved


class RemediationAction(str, Enum):
    RESTART_SERVICE         = "restart_service"
    SCALE_UP                = "scale_up"
    FLUSH_CACHE             = "flush_cache"
    ROLLBACK_DEPLOYMENT     = "rollback_deployment"
    UPDATE_CONFIG           = "update_config"
    KILL_LONG_RUNNING_QUERY = "kill_long_running_query"
    INCREASE_CONNECTION_POOL= "increase_connection_pool"
    RESTORE_NETWORK_POLICY  = "restore_network_policy"
    CLEAR_DISK_SPACE        = "clear_disk_space"
    ROTATE_CREDENTIALS      = "rotate_credentials"


# ── Action ────────────────────────────────────────────────────────────────────

class Action(BaseModel):
    """
    The action an agent submits each step.

    Depending on `action_type`, different fields are required:

    | action_type | required fields                              |
    |-------------|----------------------------------------------|
    | classify    | category                                     |
    | investigate | service_name                                 |
    | remediate   | service_name, remediation_action             |
    | escalate    | escalation_reason                            |
    | resolve     | resolution_summary                           |
    """
    action_type: ActionType = Field(..., description="Type of action to perform")

    # classify
    category: Optional[IncidentCategory] = Field(
        None, description="Incident category (required for classify action)"
    )

    # investigate / remediate
    service_name: Optional[str] = Field(
        None, description="Target service name (required for investigate & remediate)"
    )

    # remediate
    remediation_action: Optional[RemediationAction] = Field(
        None, description="Specific remediation to apply (required for remediate)"
    )

    # escalate
    escalation_reason: Optional[str] = Field(
        None, description="Why the agent is escalating (required for escalate)"
    )

    # resolve
    resolution_summary: Optional[str] = Field(
        None, description="Human-readable resolution summary (required for resolve)"
    )


# ── Sub-models used inside Observation ────────────────────────────────────────

class Alert(BaseModel):
    alert_id: str
    service: str
    severity: str          # P1 / P2 / P3
    message: str
    fired_at: str          # ISO-8601 timestamp
    metrics: Dict[str, float] = Field(default_factory=dict)


class LogEntry(BaseModel):
    timestamp: str
    service: str
    level: str             # ERROR / WARN / INFO
    message: str


class ServiceHealth(BaseModel):
    name: str
    status: str            # healthy / degraded / down
    error_rate: float      # 0.0 – 1.0
    p99_latency_ms: float
    pod_count: int


# ── Observation ───────────────────────────────────────────────────────────────

class Observation(BaseModel):
    """
    Everything the agent can see at a given step.

    - `alerts`              : Firing PagerDuty-style alerts
    - `available_services`  : Services the agent may investigate
    - `visible_logs`        : Log lines returned by the last investigate action
                              (empty until the agent investigates a service)
    - `service_health`      : Real-time health snapshot of each service
    - `classified`          : Whether the agent has submitted a classification
    - `classification`      : The submitted category (if classified)
    - `investigations_done` : Services the agent has already investigated
    - `remediation_applied` : Remediations the agent has applied so far
    - `resolved`            : Whether the episode is finished
    - `step` / `max_steps`  : Progress counter
    - `message`             : Human-readable narrative of what just happened
    """
    incident_id: str
    task_id: str
    task_description: str

    # Current incident context
    alerts: List[Alert]
    available_services: List[str]
    service_health: List[ServiceHealth]

    # Logs revealed by investigate actions
    visible_logs: List[LogEntry] = Field(default_factory=list)

    # Agent progress tracking
    classified: bool = False
    classification: Optional[str] = None
    investigations_done: List[str] = Field(default_factory=list)
    remediation_applied: List[str] = Field(default_factory=list)
    resolved: bool = False

    # Resolution text (set when agent calls resolve action)
    resolution_summary: Optional[str] = None

    # Episode metadata
    step: int = 0
    max_steps: int = 10
    message: str = ""


# ── Reward ────────────────────────────────────────────────────────────────────

class Reward(BaseModel):
    """
    Per-step reward.

    `score`     : float in [-1.0, 1.0] — step reward signal.
                  Positive for progress; negative for penalties (wrong/duplicate actions).
    `cumulative`: float in [-1.0, 1.0] — running total across the episode.
    `breakdown` : component scores (classification, diagnosis, remediation, efficiency)
    `feedback`  : plain-English explanation of why this reward was given

    NOTE: Scores *can* be negative (penalty for wrong/duplicate actions).
    The final grader score is always normalised to [0.0, 1.0].
    """
    score: float = Field(..., ge=-1.0, le=1.0)
    cumulative: float = Field(..., ge=-1.0, le=1.0)
    breakdown: Dict[str, float] = Field(default_factory=dict)
    feedback: str = ""


# ── State (full internal state — returned by /state) ─────────────────────────

class EnvironmentState(BaseModel):
    """Complete internal state, including ground truth (for graders)."""
    observation: Observation
    ground_truth: Dict[str, Any]       # hidden from the agent in step/reset
    episode_done: bool = False
    cumulative_score: float = 0.0
    step_history: List[Dict[str, Any]] = Field(default_factory=list)


# ── Step response ─────────────────────────────────────────────────────────────

class StepResponse(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)