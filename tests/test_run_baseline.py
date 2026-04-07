import pytest

from baseline.run_baseline import obs_to_text

def test_obs_to_text_full():

    obs_dict = {

        "incident_id": "INC-123",

        "task_description": "Fix the outage",

        "step": 1,

        "max_steps": 10,

        "message": "Initial alert",

        "alerts": [

            {"severity": "CRITICAL", "service": "db", "message": "High CPU", "metrics": "CPU=99%"},

            {"severity": "WARN", "service": "web", "message": "Latency"}

        ],

        "service_health": [

            {"name": "db", "status": "UNHEALTHY", "error_rate": 0.05, "p99_latency_ms": 1500, "pod_count": 3}

        ],

        "visible_logs": [

            {"timestamp": "2023-01-01T12:00:00", "service": "db", "level": "ERROR", "message": "Connection timeout"}

        ],

        "classified": True,

        "classification": "database_connection",

        "investigations_done": ["db"],

        "remediation_applied": ["restart_db"],

        "available_services": ["db", "web", "api"]

    }

    text = obs_to_text(obs_dict)

    assert "== INCIDENT: INC-123 ==" in text

    assert "Task: Fix the outage" in text

    assert "Step: 1/10" in text

    assert "Message: Initial alert" in text

    assert "=== ALERTS ===" in text

    assert "[CRITICAL] db: High CPU" in text

    assert "Metrics: CPU=99%" in text

    assert "[WARN] web: Latency" in text

    assert "=== SERVICE HEALTH ===" in text

    assert "db: UNHEALTHY | err_rate=5% | p99=1500ms | pods=3" in text

    assert "=== RECENT LOGS ===" in text

    assert "[2023-01-01T12:00:00] db ERROR: Connection timeout" in text

    assert "=== AGENT PROGRESS ===" in text

    assert "Classified: True (database_connection)" in text

    assert "Investigated: ['db']" in text

    assert "Remediations: ['restart_db']" in text

    assert "Available services to investigate: ['db', 'web', 'api']" in text

def test_obs_to_text_minimal():

    obs_dict = {

        "incident_id": "INC-456",

        "task_description": "Minimal task",

        "step": 5,

        "max_steps": 15,

        "message": "No new messages"

    }

    text = obs_to_text(obs_dict)

    assert "== INCIDENT: INC-456 ==" in text

    assert "Task: Minimal task" in text

    assert "Step: 5/15" in text

    assert "Message: No new messages" in text

    assert "=== ALERTS ===" in text

    assert "=== SERVICE HEALTH ===" in text

    assert "=== RECENT LOGS ===" not in text

    assert "=== AGENT PROGRESS ===" in text

    assert "Classified: None (-)" in text

    assert "Investigated: []" in text

    assert "Remediations: []" in text

    assert "Available services to investigate: []" in text

def test_obs_to_text_truncates_logs():

    logs = [{"timestamp": f"T{i}", "service": "svc", "level": "INFO", "message": f"Log {i}"} for i in range(30)]

    obs_dict = {

        "incident_id": "INC-789",

        "task_description": "Log truncation",

        "step": 1,

        "max_steps": 5,

        "message": "Lots of logs",

        "visible_logs": logs

    }

    text = obs_to_text(obs_dict)

    assert "=== RECENT LOGS ===" in text

    assert "[T9] svc INFO: Log 9" not in text

    assert "[T10] svc INFO: Log 10" in text

    assert "[T29] svc INFO: Log 29" in text

    assert text.count(" svc INFO: Log ") == 20
