# 🚨 Incident Response OpenEnv

> An OpenEnv-compliant environment for training and evaluating AI agents on
> real-world production incident response.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compliant-green)](https://openenv.dev)
[![HuggingFace](https://img.shields.io/badge/🤗-Space-yellow)](https://huggingface.co/spaces)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

---

## Why This Environment?

Every engineering organisation has an incident response process.
Junior on-call engineers spend hundreds of hours learning to triage alerts,
read distributed logs, identify root causes, and apply remediations —
all under time pressure.

This environment simulates that workflow faithfully:

- **Realistic incidents** modelled after common production failure patterns
  (connection pool exhaustion, memory leaks, config errors, disk full cascades)
- **Partial observability** — the agent can't see all logs until it explicitly
  investigates a service, mirroring real on-call dashboards
- **Multi-service causality** — symptoms appear across many services; the root
  cause is upstream
- **Meaningful reward shaping** — partial credit for every correct action, not
  just binary success/failure

This fills a real gap: there is currently no OpenEnv environment for DevOps /
SRE agent evaluation.

---

## Environment Description

The agent plays the role of an on-call SRE who has just received PagerDuty alerts.
Each episode is a single incident. The agent must:

1. **Read** firing alerts and service health metrics
2. **Investigate** services by fetching their logs
3. **Classify** the incident into a root-cause category
4. **Remediate** the affected service(s)
5. **Resolve** the incident with a summary

Episodes terminate when the agent calls `resolve` or `escalate`,
or when the step budget is exhausted.

---

## Action Space

All actions are JSON objects sent to `POST /step`.

| `action_type` | Required fields | Description |
|---|---|---|
| `classify` | `category` | Label the incident category |
| `investigate` | `service_name` | Fetch logs for a service |
| `remediate` | `service_name`, `remediation_action` | Apply a fix |
| `escalate` | `escalation_reason` | Hand off to humans |
| `resolve` | `resolution_summary` | Close the incident |

**Incident categories:** `database_connection` · `memory_leak` ·
`network_partition` · `dependency_failure` · `resource_exhaustion` ·
`configuration_error`

**Remediation actions:** `restart_service` · `scale_up` · `flush_cache` ·
`rollback_deployment` · `update_config` · `kill_long_running_query` ·
`increase_connection_pool` · `restore_network_policy` · `clear_disk_space` ·
`rotate_credentials`

### Example actions

```json
{"action_type": "investigate", "service_name": "auth-service"}

{"action_type": "classify", "category": "configuration_error"}

{"action_type": "remediate",
 "service_name": "auth-service",
 "remediation_action": "update_config"}

{"action_type": "resolve",
 "resolution_summary": "auth-service failed due to missing VAULT_ROLE env var. Updated config and restarted."}
```

---

## Observation Space

Each step returns an `Observation` object:

```json
{
  "incident_id": "INC-2001",
  "task_id": "root_cause_analysis",
  "task_description": "...",
  "alerts": [
    {
      "alert_id": "ALT-010",
      "service": "checkout-service",
      "severity": "P1",
      "message": "502 Bad Gateway rate 45%",
      "fired_at": "2024-06-16T14:00:00Z",
      "metrics": {"error_rate": 0.45, "p99_latency_ms": 12000.0}
    }
  ],
  "available_services": ["checkout-service", "inventory-service", "auth-service"],
  "service_health": [
    {"name": "auth-service", "status": "down", "error_rate": 1.0,
     "p99_latency_ms": 0, "pod_count": 0}
  ],
  "visible_logs": [],          ← populated by investigate actions
  "classified": false,
  "classification": null,
  "investigations_done": [],
  "remediation_applied": [],
  "resolved": false,
  "step": 1,
  "max_steps": 12,
  "message": "Incident INC-2001 opened. 3 alert(s) firing."
}
```

**Key design notes:**
- `visible_logs` is empty at episode start — must be revealed via `investigate`
- `service_health` gives a dashboard-level signal; logs give the diagnostic detail
- Re-investigating a service costs a small penalty (-0.05 reward)

---

## Reward Function

Rewards are **shaped across the full trajectory**, not sparse.

| Action | Reward |
|---|---|
| Correct classification | +0.30 |
| Incorrect classification | +0.00 |
| Investigate new service (no errors) | +0.10 |
| Investigate new service (errors found) | +0.15 |
| Re-investigate same service | −0.05 |
| Correct remediation | +0.20 |
| Wrong remediation | −0.10 |
| Duplicate remediation | −0.05 |
| Resolve (base) | +0.10 |
| Resolve with keyword-matching summary | +0.00–0.15 |
| Over step budget | −0.02 per extra step |
| Escalate | +0.05 |

---

## Tasks

### Task 1 — Alert Classification _(easy)_

**Step budget:** 8  
**Grader:** `classification_accuracy × efficiency_bonus`

A single P2 alert has fired (e.g., payment-service latency spike). The agent
may investigate 1–2 services, then must classify the incident correctly.
Full marks for correct classification in ≤3 steps; efficiency penalty kicks
in beyond step 3.

**Expected difficulty:** Solvable by any reasoning-capable LLM.
Frontier models should score ≥0.85.

---

### Task 2 — Root Cause Analysis _(medium)_

**Step budget:** 12  
**Grader:** weighted phase score (classification 30%, investigation 30%, root-service found 25%, resolved 15%)

Multiple services show 502 errors. The real failure is upstream
(e.g., auth-service in CrashLoopBackOff due to a missing config value).
The agent must investigate ≥2 services to distinguish the root cause from
downstream symptoms.

**Expected difficulty:** Requires systematic investigation. GPT-4o-mini ~0.61.

---

### Task 3 — Full Incident Response _(hard)_

**Step budget:** 20  
**Grader:** multi-phase composite (classification 20%, investigation 20%, root-coverage 25%, remediation 20%, resolution-quality 15%)

A platform-wide outage caused by disk exhaustion across two infrastructure
services (Redis cluster + ML feature store), cascading to five application
services. The agent must investigate ≥3 services, identify both root-cause
services, apply both correct remediations, and resolve with a coherent summary
that mentions the key failure terms.

**Expected difficulty:** Challenges frontier models. GPT-4o ~0.65.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/reset` | Start a new episode |
| `POST` | `/step` | Submit an action |
| `GET` | `/state` | Full state (includes ground truth) |
| `GET` | `/tasks` | Task list + action schemas |
| `POST` | `/grader` | Grade current episode |
| `POST` | `/baseline` | Run baseline script, return scores |

### Reset request body

```json
{
  "task_id": "alert_classification",
  "scenario_index": 0
}
```

---

## Setup & Usage

### Quick start with Docker

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/incident-response-openenv
cd incident-response-openenv

docker build -t incident-response-openenv .
docker run -p 7860:7860 incident-response-openenv
```

The API is now available at `http://localhost:7860`.

### Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python main.py
```

### Running the baseline

```bash
# Heuristic agent (no API key required)
python baseline/run_baseline.py --heuristic

# LLM agent
export OPENAI_API_KEY=sk-...
python baseline/run_baseline.py --model gpt-4o-mini

# JSON output (for automated evaluation)
python baseline/run_baseline.py --heuristic --output json
```

### Quick end-to-end test

```bash
# 1. Start the server
python main.py &

# 2. Reset
curl -s -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "alert_classification"}' | python -m json.tool

# 3. Investigate
curl -s -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "investigate", "service_name": "postgres-primary"}' | python -m json.tool

# 4. Classify
curl -s -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "classify", "category": "database_connection"}' | python -m json.tool

# 5. Grade
curl -s -X POST http://localhost:7860/grader | python -m json.tool
```

---

## Baseline Scores

| Task | Difficulty | Heuristic | GPT-4o-mini | GPT-4o |
|---|---|---|---|---|
| alert_classification | easy | 0.45 | 0.72 | 0.88 |
| root_cause_analysis | medium | 0.38 | 0.61 | 0.79 |
| full_incident_response | hard | 0.22 | 0.48 | 0.65 |

_Heuristic agent uses keyword matching on logs; no LLM required._

---

## Project Structure

```
.
├── environment/
│   ├── __init__.py
│   ├── models.py         # Pydantic models (Action, Observation, Reward, …)
│   ├── env.py            # Core IncidentResponseEnv class
│   └── tasks.py          # Scenarios, graders, task registry
├── api/
│   ├── __init__.py
│   └── app.py            # FastAPI application
├── baseline/
│   └── run_baseline.py   # Inference script
├── tests/
│   └── test_env.py       # Smoke tests
├── main.py               # Uvicorn entry point
├── openenv.yaml          # OpenEnv spec metadata
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE).