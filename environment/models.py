"""
Typed Pydantic models for the Incident Response OpenEnv environment.
All action, observation, and reward types are defined here.
"""

from pydantic import BaseModel, Field

from typing import Optional, List, Dict, Any

from enum import Enum

class IncidentCategory(str, Enum):

    DATABASE_CONNECTION  = "database_connection"

    MEMORY_LEAK          = "memory_leak"

    NETWORK_PARTITION    = "network_partition"

    DEPENDENCY_FAILURE   = "dependency_failure"

    RESOURCE_EXHAUSTION  = "resource_exhaustion"

    CONFIGURATION_ERROR  = "configuration_error"

class ActionType(str, Enum):

    CLASSIFY    = "classify"

    INVESTIGATE = "investigate"

    REMEDIATE   = "remediate"

    ESCALATE    = "escalate"

    RESOLVE     = "resolve"

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

    category: Optional[IncidentCategory] = Field(

        None, description="Incident category (required for classify action)"

    )

    service_name: Optional[str] = Field(

        None, description="Target service name (required for investigate & remediate)"

    )

    remediation_action: Optional[RemediationAction] = Field(

        None, description="Specific remediation to apply (required for remediate)"

    )

    escalation_reason: Optional[str] = Field(

        None, description="Why the agent is escalating (required for escalate)"

    )

    resolution_summary: Optional[str] = Field(

        None, description="Human-readable resolution summary (required for resolve)"

    )

class Alert(BaseModel):

    alert_id: str

    service: str

    severity: str

    message: str

    fired_at: str

    metrics: Dict[str, float] = Field(default_factory=dict)

class LogEntry(BaseModel):

    timestamp: str

    service: str

    level: str

    message: str

class ServiceHealth(BaseModel):

    name: str

    status: str

    error_rate: float

    p99_latency_ms: float

    pod_count: int

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

    alerts: List[Alert]

    available_services: List[str]

    service_health: List[ServiceHealth]

    visible_logs: List[LogEntry] = Field(default_factory=list)

    classified: bool = False

    classification: Optional[str] = None

    investigations_done: List[str] = Field(default_factory=list)

    remediation_applied: List[str] = Field(default_factory=list)

    resolved: bool = False

    resolution_summary: Optional[str] = None

    step: int = 0

    max_steps: int = 10

    message: str = ""

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

class EnvironmentState(BaseModel):

    """Complete internal state, including ground truth (for graders)."""

    observation: Observation

    ground_truth: Dict[str, Any]

    episode_done: bool = False

    cumulative_score: float = 0.0

    step_history: List[Dict[str, Any]] = Field(default_factory=list)

class StepResponse(BaseModel):

    observation: Observation

    reward: Reward

    done: bool

    info: Dict[str, Any] = Field(default_factory=dict)
