"""
Task definitions and agent graders for the Incident Response environment.

Three tasks with increasing difficulty:
Task 1 – alert_classification  (easy)
Task 2 – root_cause_analysis   (medium)
Task 3 – full_incident_response (hard)
"""



import copy

from typing import Dict, Any, List



from .models import (

    Alert, LogEntry, ServiceHealth,

    IncidentCategory, RemediationAction,

    Observation

)



                                                                               

               

                                                                               



def _health(name, status, err, p99, pods):

    return ServiceHealth(name=name, status=status, error_rate=err, p99_latency_ms=p99, pod_count=pods)





                                                                               

                                       

                                                                               

                                                                      

                                                                    

                                                                       

                                                     



TASK_1_SCENARIOS = [

    {

        "incident_id": "INC-1001",

        "description": (

            "A P2 alert has fired on the payment-service reporting high latency. "

            "Investigate the situation and classify the root incident category."

        ),

        "alerts": [

            Alert(

                alert_id="ALT-001",

                service="payment-service",

                severity="P2",

                message="p99 latency > 5 s — SLO breach imminent",

                fired_at="2024-06-15T02:14:00Z",

                metrics={"p99_latency_ms": 5420.0, "error_rate": 0.03}

            )

        ],

        "available_services": ["payment-service", "postgres-primary", "redis-cache"],

        "service_health": [

            _health("payment-service",  "degraded", 0.03, 5420.0, 3),

            _health("postgres-primary", "degraded", 0.00, 4800.0, 1),

            _health("redis-cache",      "healthy",  0.00, 1.2,    2),

        ],

        "log_map": {

            "payment-service": [

                LogEntry(timestamp="2024-06-15T02:13:55Z", service="payment-service",

                    level="ERROR", message="Connection pool exhausted — queue depth: 512"),

                LogEntry(timestamp="2024-06-15T02:13:56Z", service="payment-service",

                    level="ERROR", message="Timeout waiting for DB connection after 30 s"),

                LogEntry(timestamp="2024-06-15T02:13:58Z", service="payment-service",

                    level="WARN",  message="Retrying transaction (attempt 3/3)"),

            ],

            "postgres-primary": [

                LogEntry(timestamp="2024-06-15T02:13:50Z", service="postgres-primary",

                    level="WARN",  message="max_connections=100 reached, refusing new connections"),

                LogEntry(timestamp="2024-06-15T02:13:52Z", service="postgres-primary",

                    level="ERROR", message="Connection from 10.0.1.15 rejected: too many clients"),

            ],

            "redis-cache": [

                LogEntry(timestamp="2024-06-15T02:13:55Z", service="redis-cache",

                    level="INFO",  message="All operations nominal"),

            ],

        },

        "ground_truth": {

            "category": IncidentCategory.DATABASE_CONNECTION,

            "root_service": "postgres-primary",

            "correct_remediation": RemediationAction.INCREASE_CONNECTION_POOL,

        },

        "max_steps": 8,

    },

    {

        "incident_id": "INC-1002",

        "description": (

            "Memory usage alerts are firing on the image-processing worker. "

            "Classify the incident category."

        ),

        "alerts": [

            Alert(

                alert_id="ALT-002",

                service="image-worker",

                severity="P2",

                message="Container memory usage at 94% — OOM kill likely",

                fired_at="2024-06-15T09:30:00Z",

                metrics={"memory_pct": 94.0, "gc_pause_ms": 820.0}

            )

        ],

        "available_services": ["image-worker", "object-store", "message-queue"],

        "service_health": [

            _health("image-worker",   "degraded", 0.12, 3200.0, 2),

            _health("object-store",   "healthy",  0.00,   45.0, 3),

            _health("message-queue",  "healthy",  0.00,    5.0, 2),

        ],

        "log_map": {

            "image-worker": [

                LogEntry(timestamp="2024-06-15T09:29:00Z", service="image-worker",

                    level="WARN",  message="GC pause 820 ms — heap 3.8 GB / 4 GB"),

                LogEntry(timestamp="2024-06-15T09:29:30Z", service="image-worker",

                    level="ERROR", message="OutOfMemoryError: unable to allocate 512 MB"),

                LogEntry(timestamp="2024-06-15T09:29:45Z", service="image-worker",

                    level="ERROR", message="Image cache not being evicted — TTL logic bypassed"),

            ],

            "object-store": [

                LogEntry(timestamp="2024-06-15T09:29:50Z", service="object-store",

                    level="INFO",  message="Serving requests normally"),

            ],

            "message-queue": [

                LogEntry(timestamp="2024-06-15T09:29:50Z", service="message-queue",

                    level="INFO",  message="Queue depth 24, within normal range"),

            ],

        },

        "ground_truth": {

            "category": IncidentCategory.MEMORY_LEAK,

            "root_service": "image-worker",

            "correct_remediation": RemediationAction.RESTART_SERVICE,

        },

        "max_steps": 8,

    },

]





                                                                               

                                        

                                                                               

                                                                         

                                                                               

                                                                               



TASK_2_SCENARIOS = [

    {

        "incident_id": "INC-2001",

        "description": (

            "Multiple microservices are returning 502 errors. The alerts span "

            "checkout-service, inventory-service, and notification-service. "

            "Investigate and identify the root cause service."

        ),

        "alerts": [

            Alert(alert_id="ALT-010", service="checkout-service",

                severity="P1", message="502 Bad Gateway rate 45%",

                fired_at="2024-06-16T14:00:00Z",

                metrics={"error_rate": 0.45, "p99_latency_ms": 12000.0}),

            Alert(alert_id="ALT-011", service="inventory-service",

                severity="P2", message="502 Bad Gateway rate 38%",

                fired_at="2024-06-16T14:00:30Z",

                metrics={"error_rate": 0.38, "p99_latency_ms": 9800.0}),

            Alert(alert_id="ALT-012", service="notification-service",

                severity="P3", message="Delivery failure rate 60%",

                fired_at="2024-06-16T14:01:00Z",

                metrics={"error_rate": 0.60}),

        ],

        "available_services": [

            "checkout-service", "inventory-service", "notification-service",

            "auth-service", "postgres-replica"

        ],

        "service_health": [

            _health("checkout-service",     "degraded", 0.45, 12000.0, 3),

            _health("inventory-service",    "degraded", 0.38,  9800.0, 3),

            _health("notification-service", "degraded", 0.60,  5000.0, 2),

            _health("auth-service",         "down",     1.00,     0.0, 0),

            _health("postgres-replica",     "healthy",  0.00,    22.0, 1),

        ],

        "log_map": {

            "checkout-service": [

                LogEntry(timestamp="2024-06-16T13:59:55Z", service="checkout-service",

                    level="ERROR", message="Failed to validate JWT: connection refused to auth-service:8080"),

                LogEntry(timestamp="2024-06-16T13:59:56Z", service="checkout-service",

                    level="ERROR", message="Auth check failed — returning 502 to client"),

            ],

            "inventory-service": [

                LogEntry(timestamp="2024-06-16T13:59:58Z", service="inventory-service",

                    level="ERROR", message="Authorization middleware: auth-service unreachable"),

                LogEntry(timestamp="2024-06-16T13:59:59Z", service="inventory-service",

                    level="WARN",  message="Fallback: rejecting all unauthenticated requests"),

            ],

            "notification-service": [

                LogEntry(timestamp="2024-06-16T14:00:10Z", service="notification-service",

                    level="ERROR", message="Cannot verify sender token — auth-service timeout"),

            ],

            "auth-service": [

                LogEntry(timestamp="2024-06-16T13:58:00Z", service="auth-service",

                    level="ERROR", message="OOMKilled — container restarting (CrashLoopBackOff)"),

                LogEntry(timestamp="2024-06-16T13:58:30Z", service="auth-service",

                    level="ERROR", message="Startup failed: cannot read secret /vault/token — permission denied"),

                LogEntry(timestamp="2024-06-16T13:58:32Z", service="auth-service",

                    level="ERROR", message="Configuration error: VAULT_ROLE not set"),

            ],

            "postgres-replica": [

                LogEntry(timestamp="2024-06-16T14:00:00Z", service="postgres-replica",

                    level="INFO",  message="Replication lag 0 ms — nominal"),

            ],

        },

        "ground_truth": {

            "category": IncidentCategory.CONFIGURATION_ERROR,

            "root_service": "auth-service",

            "correct_remediation": RemediationAction.UPDATE_CONFIG,

            "min_investigations": 2,                                    

        },

        "max_steps": 12,

    },

                                                                                  

    {

        "incident_id": "INC-2002",

        "description": (

            "The order-service and reporting-service are both showing elevated "

            "error rates. Multiple alerts indicate downstream timeouts. Investigate "

            "to find the root cause service and resolve."

        ),

        "alerts": [

            Alert(alert_id="ALT-013", service="order-service",

                severity="P1", message="Error rate 52% — order placement failures",

                fired_at="2024-07-10T11:00:00Z",

                metrics={"error_rate": 0.52, "p99_latency_ms": 14500.0}),

            Alert(alert_id="ALT-014", service="reporting-service",

                severity="P2", message="Report generation timeout 70%",

                fired_at="2024-07-10T11:00:30Z",

                metrics={"error_rate": 0.70}),

            Alert(alert_id="ALT-015", service="analytics-worker",

                severity="P3", message="Job queue stalled — no completions in 5 min",

                fired_at="2024-07-10T11:01:00Z",

                metrics={"queue_depth": 320.0}),

        ],

        "available_services": [

            "order-service", "reporting-service", "analytics-worker",

            "postgres-primary", "redis-cache",

        ],

        "service_health": [

            _health("order-service",      "degraded", 0.52, 14500.0, 3),

            _health("reporting-service",  "degraded", 0.70,  9000.0, 2),

            _health("analytics-worker",   "degraded", 0.30,  5000.0, 2),

            _health("postgres-primary",   "down",     1.00,     0.0, 1),

            _health("redis-cache",        "healthy",  0.00,     3.0, 2),

        ],

        "log_map": {

            "order-service": [

                LogEntry(timestamp="2024-07-10T10:59:45Z", service="order-service",

                    level="ERROR", message="DB query timeout after 30 s — postgres-primary unreachable"),

                LogEntry(timestamp="2024-07-10T10:59:47Z", service="order-service",

                    level="ERROR", message="FATAL: terminating connection due to administrator command"),

            ],

            "reporting-service": [

                LogEntry(timestamp="2024-07-10T10:59:50Z", service="reporting-service",

                    level="ERROR", message="Connection to postgres-primary refused: host unreachable"),

                LogEntry(timestamp="2024-07-10T10:59:52Z", service="reporting-service",

                    level="WARN",  message="Retrying DB query — attempt 3/3 failed"),

            ],

            "analytics-worker": [

                LogEntry(timestamp="2024-07-10T11:00:00Z", service="analytics-worker",

                    level="ERROR", message="Cannot open cursor — postgresql driver error: connection reset"),

            ],

            "postgres-primary": [

                LogEntry(timestamp="2024-07-10T10:58:00Z", service="postgres-primary",

                    level="ERROR", message="Out of memory: kill process 1234 (postgres) score 998"),

                LogEntry(timestamp="2024-07-10T10:58:05Z", service="postgres-primary",

                         level="ERROR", message="OOM killer terminated postmaster — database shutting down"),

                LogEntry(timestamp="2024-07-10T10:58:10Z", service="postgres-primary",

                         level="ERROR", message="Server process (PID 1234) was terminated by signal 9 (Killed)"),

            ],

            "redis-cache": [

                LogEntry(timestamp="2024-07-10T11:00:00Z", service="redis-cache",

                         level="INFO",  message="All keys within TTL — no anomalies"),

            ],

        },

        "ground_truth": {

            "category": IncidentCategory.MEMORY_LEAK,

            "root_service": "postgres-primary",

            "correct_remediation": RemediationAction.RESTART_SERVICE,

            "min_investigations": 2,

        },

        "max_steps": 12,

    },

]





                                                                               

                                         

                                                                               

                                                                          

                                                           

                                                              



TASK_3_SCENARIOS = [

    {

        "incident_id": "INC-3001",

        "description": (

            "CRITICAL: The entire e-commerce platform is degraded. Orders are failing, "

            "CDN latency is spiking, the fraud detection service is throwing errors, "

            "and the data warehouse pipeline has halted. Conduct a full incident "

            "response: classify, investigate all relevant services, apply the correct "

            "remediation, and resolve the incident with a clear summary."

        ),

        "alerts": [

            Alert(alert_id="ALT-020", service="api-gateway",

                  severity="P1", message="Error rate 55% — platform-wide impact",

                  fired_at="2024-06-17T03:00:00Z",

                  metrics={"error_rate": 0.55, "p99_latency_ms": 18000.0}),

            Alert(alert_id="ALT-021", service="order-service",

                  severity="P1", message="Order placement failure rate 62%",

                  fired_at="2024-06-17T03:00:05Z",

                  metrics={"error_rate": 0.62}),

            Alert(alert_id="ALT-022", service="fraud-detection",

                  severity="P2", message="Model inference timeout",

                  fired_at="2024-06-17T03:00:10Z",

                  metrics={"p99_latency_ms": 25000.0}),

            Alert(alert_id="ALT-023", service="warehouse-pipeline",

                  severity="P2", message="ETL pipeline halted — no rows processed",

                  fired_at="2024-06-17T03:01:00Z",

                  metrics={"rows_processed_last_5m": 0.0}),

        ],

        "available_services": [

            "api-gateway", "order-service", "fraud-detection",

            "warehouse-pipeline", "ml-feature-store", "redis-cluster", "postgres-primary"

        ],

        "service_health": [

            _health("api-gateway",        "degraded", 0.55, 18000.0, 4),

            _health("order-service",      "degraded", 0.62,  9000.0, 3),

            _health("fraud-detection",    "degraded", 0.80, 25000.0, 2),

            _health("warehouse-pipeline", "down",     1.00,     0.0, 0),

            _health("ml-feature-store",   "down",     1.00,     0.0, 0),

            _health("redis-cluster",      "degraded", 0.00,  4500.0, 3),

            _health("postgres-primary",   "healthy",  0.00,    18.0, 1),

        ],

        "log_map": {

            "api-gateway": [

                LogEntry(timestamp="2024-06-17T02:59:50Z", service="api-gateway",

                         level="ERROR", message="Upstream fraud-detection timeout after 25 s"),

                LogEntry(timestamp="2024-06-17T02:59:52Z", service="api-gateway",

                         level="ERROR", message="Redis CLUSTER SLOTS returned CLUSTERDOWN error"),

            ],

            "order-service": [

                LogEntry(timestamp="2024-06-17T02:59:55Z", service="order-service",

                         level="ERROR", message="Cannot connect to redis-cluster:6379 — CLUSTERDOWN"),

                LogEntry(timestamp="2024-06-17T02:59:56Z", service="order-service",

                         level="ERROR", message="Session store unavailable — rejecting checkout"),

            ],

            "fraud-detection": [

                LogEntry(timestamp="2024-06-17T02:59:45Z", service="fraud-detection",

                         level="ERROR", message="ml-feature-store connection refused on :9200"),

                LogEntry(timestamp="2024-06-17T02:59:46Z", service="fraud-detection",

                         level="ERROR", message="Feature lookup timeout — cannot score transaction"),

            ],

            "warehouse-pipeline": [

                LogEntry(timestamp="2024-06-17T02:59:40Z", service="warehouse-pipeline",

                         level="ERROR", message="Redis Streams consumer: CLUSTERDOWN state detected"),

                LogEntry(timestamp="2024-06-17T02:59:41Z", service="warehouse-pipeline",

                         level="ERROR", message="Aborting ETL batch — no events readable from stream"),

            ],

            "ml-feature-store": [

                LogEntry(timestamp="2024-06-17T02:58:00Z", service="ml-feature-store",

                         level="ERROR", message="Primary shard unassigned — cluster health RED"),

                LogEntry(timestamp="2024-06-17T02:58:05Z", service="ml-feature-store",

                         level="ERROR", message="Node ml-feature-store-1 evicted — disk 98% full"),

                LogEntry(timestamp="2024-06-17T02:58:10Z", service="ml-feature-store",

                         level="ERROR", message="Write-ahead log cannot flush — no disk space"),

            ],

            "redis-cluster": [

                LogEntry(timestamp="2024-06-17T02:58:30Z", service="redis-cluster",

                         level="ERROR", message="Cluster node redis-2 unreachable — PFAIL"),

                LogEntry(timestamp="2024-06-17T02:58:35Z", service="redis-cluster",

                         level="ERROR", message="redis-2 marked FAIL — cluster enters CLUSTERDOWN"),

                LogEntry(timestamp="2024-06-17T02:58:36Z", service="redis-cluster",

                         level="ERROR", message="redis-2 disk 99% — append-only file corrupted"),

            ],

            "postgres-primary": [

                LogEntry(timestamp="2024-06-17T03:00:00Z", service="postgres-primary",

                         level="INFO",  message="All connections healthy — no anomalies"),

            ],

        },

        "ground_truth": {

                                                                                       

            "category": IncidentCategory.RESOURCE_EXHAUSTION,

            "root_services": ["redis-cluster", "ml-feature-store"],

            "correct_remediations": [

                RemediationAction.CLEAR_DISK_SPACE,

                RemediationAction.RESTART_SERVICE,

            ],

            "correct_remediation_values": {

                RemediationAction.CLEAR_DISK_SPACE.value,

                RemediationAction.RESTART_SERVICE.value,

            },

            "min_investigations": 3,

            "resolution_keywords": ["disk", "redis", "cluster", "feature"],

        },

        "max_steps": 20,

    },

                                                                                  

    {

        "incident_id": "INC-3002",

        "description": (

            "CRITICAL: All HTTPS traffic to the platform is failing. Multiple "

            "services report TLS handshake errors and certificate validation "

            "failures. The mobile app, web frontend, and partner API are all "

            "down. Conduct a full incident response: classify, investigate "

            "relevant services, apply the correct remediation, and resolve."

        ),

        "alerts": [

            Alert(alert_id="ALT-030", service="api-gateway",

                  severity="P1", message="TLS handshake error rate 98% — all HTTPS terminated",

                  fired_at="2024-08-01T00:00:00Z",

                  metrics={"error_rate": 0.98, "tls_errors_per_min": 12000.0}),

            Alert(alert_id="ALT-031", service="mobile-backend",

                  severity="P1", message="SSL certificate verification failed — all clients rejected",

                  fired_at="2024-08-01T00:00:05Z",

                  metrics={"error_rate": 0.99}),

            Alert(alert_id="ALT-032", service="partner-api",

                  severity="P2", message="Mutual TLS auth failure 100%",

                  fired_at="2024-08-01T00:00:10Z",

                  metrics={"error_rate": 1.00}),

            Alert(alert_id="ALT-033", service="health-monitor",

                  severity="P3", message="Certificate expiry check: *.platform.io expired 2 min ago",

                  fired_at="2024-08-01T00:01:00Z",

                  metrics={"days_until_expiry": -0.001}),

        ],

        "available_services": [

            "api-gateway", "mobile-backend", "partner-api",

            "cert-manager", "health-monitor", "postgres-primary",

        ],

        "service_health": [

            _health("api-gateway",     "down",    1.00,     0.0, 4),

            _health("mobile-backend", "down",    1.00,     0.0, 3),

            _health("partner-api",    "down",    1.00,     0.0, 2),

            _health("cert-manager",   "degraded",0.20,  2400.0, 1),

            _health("health-monitor", "degraded",0.00,   120.0, 1),

            _health("postgres-primary","healthy",0.00,    15.0, 1),

        ],

        "log_map": {

            "api-gateway": [

                LogEntry(timestamp="2024-08-01T00:00:00Z", service="api-gateway",

                         level="ERROR", message="TLS: certificate has expired — notAfter=2024-07-31T23:58:00Z"),

                LogEntry(timestamp="2024-08-01T00:00:01Z", service="api-gateway",

                         level="ERROR", message="SSL_CTX_use_certificate: certificate verify failed — rejecting all connections"),

            ],

            "mobile-backend": [

                LogEntry(timestamp="2024-08-01T00:00:03Z", service="mobile-backend",

                         level="ERROR", message="x509: certificate has expired or is not yet valid"),

                LogEntry(timestamp="2024-08-01T00:00:04Z", service="mobile-backend",

                         level="ERROR", message="HTTPS listener shutdown — cannot bind expired certificate"),

            ],

            "partner-api": [

                LogEntry(timestamp="2024-08-01T00:00:05Z", service="partner-api",

                         level="ERROR", message="Mutual TLS: peer certificate verification failed — chain expired"),

            ],

            "cert-manager": [

                LogEntry(timestamp="2024-07-28T12:00:00Z", service="cert-manager",

                         level="WARN",  message="Certificate *.platform.io expiring in 3 days — renewal pending"),

                LogEntry(timestamp="2024-07-31T22:00:00Z", service="cert-manager",

                         level="ERROR", message="ACME challenge failed — DNS propagation timeout"),

                LogEntry(timestamp="2024-07-31T23:58:00Z", service="cert-manager",

                         level="ERROR", message="Certificate *.platform.io EXPIRED — renewal failed 3 times"),

            ],

            "health-monitor": [

                LogEntry(timestamp="2024-08-01T00:01:00Z", service="health-monitor",

                         level="ERROR", message="SSL check *.platform.io: EXPIRED 2 minutes ago"),

                LogEntry(timestamp="2024-08-01T00:01:01Z", service="health-monitor",

                         level="ERROR", message="Certificate renewal blocked: DNS challenge token not found at /.well-known/acme-challenge/"),

            ],

            "postgres-primary": [

                LogEntry(timestamp="2024-08-01T00:01:00Z", service="postgres-primary",

                         level="INFO",  message="All connections healthy — no anomalies"),

            ],

        },

        "ground_truth": {

            "category": IncidentCategory.CONFIGURATION_ERROR,

            "root_services": ["cert-manager"],

            "correct_remediations": [

                RemediationAction.ROTATE_CREDENTIALS,

                RemediationAction.UPDATE_CONFIG,

            ],

            "correct_remediation_values": {

                RemediationAction.ROTATE_CREDENTIALS.value,

                RemediationAction.UPDATE_CONFIG.value,

            },

            "min_investigations": 3,

            "resolution_keywords": ["certificate", "tls", "expired", "cert"],

        },

        "max_steps": 20,

    },

]





                                                                               

               

                                                                               



TASKS = {

    "alert_classification": {

        "id": "alert_classification",

        "name": "Alert Classification",

        "difficulty": "easy",

        "description": (

            "A single alert has fired. Optionally investigate one or two services, "

            "then classify the incident into the correct IncidentCategory. "

            "Rewards correct classification and penalises wasted steps."

        ),

        "scenarios": TASK_1_SCENARIOS,

        "action_schema": {

            "classify":    {"category": "IncidentCategory enum value"},

            "investigate": {"service_name": "string"},

        },

    },

    "root_cause_analysis": {

        "id": "root_cause_analysis",

        "name": "Root Cause Analysis",

        "difficulty": "medium",

        "description": (

            "Multiple services are affected. The agent must investigate at least two "

            "services, correctly classify the incident, identify the root service, "

            "and resolve the episode. Partial credit for each phase."

        ),

        "scenarios": TASK_2_SCENARIOS,

        "action_schema": {

            "classify":    {"category": "IncidentCategory enum value"},

            "investigate": {"service_name": "string"},

            "remediate":   {"service_name": "string", "remediation_action": "RemediationAction enum value"},

            "resolve":     {"resolution_summary": "string"},

        },

    },

    "full_incident_response": {

        "id": "full_incident_response",

        "name": "Full Incident Response",

        "difficulty": "hard",

        "description": (

            "A platform-wide outage. The agent must classify, investigate ≥3 services, "

            "apply the correct remediations across multiple root-cause services, then "

            "resolve with a coherent summary. Every phase is scored independently."

        ),

        "scenarios": TASK_3_SCENARIOS,

        "action_schema": {

            "classify":    {"category": "IncidentCategory enum value"},

            "investigate": {"service_name": "string"},

            "remediate":   {"service_name": "string", "remediation_action": "RemediationAction enum value"},

            "escalate":    {"escalation_reason": "string"},

            "resolve":     {"resolution_summary": "string"},

        },

    },

}





                                                                               

         

                                                                               



def grade_task1(state: Dict[str, Any]) -> Dict[str, Any]:

    """
    Easy grader — alert classification.

    Score = classification_correct * efficiency_bonus

    classification_correct  : 1.0 if correct, 0.0 otherwise
    efficiency_bonus        : 1.0 if ≤3 steps, scaled down to 0.5 at max_steps
    """

    gt = state["ground_truth"]

    obs = state["observation"]

    history = state["step_history"]



    classification_correct = 0.0

    if obs.get("classified") and obs.get("classification") == gt["category"].value:

        classification_correct = 1.0



                                          

    steps_used = obs.get("step", 0)

    max_steps = state.get("max_steps", 8)

    if steps_used <= 3:

        efficiency = 1.0

    else:

        efficiency = max(0.5, 1.0 - 0.05 * (steps_used - 3))



    score = classification_correct * efficiency

    return {

        "score": round(score, 4),

        "breakdown": {

            "classification_correct": classification_correct,

            "efficiency_bonus": efficiency,

        },

        "feedback": (

            f"Classification {'correct ✓' if classification_correct else 'wrong ✗'} "

            f"(submitted: {obs.get('classification')}, "

            f"expected: {gt['category'].value}). "

            f"Efficiency: {efficiency:.2f} ({steps_used} steps used)."

        ),

    }





def grade_task2(state: Dict[str, Any]) -> Dict[str, Any]:

    """
    Medium grader — root cause analysis.

    Phase scores (weighted):
      classification   30%  — correct IncidentCategory
      investigation    30%  — investigated ≥ min_investigations services
      root_identified  25%  — root_service in investigations_done
      resolved         15%  — agent called resolve
    """

    gt = state["ground_truth"]

    obs = state["observation"]



                    

    cls_score = 1.0 if (obs.get("classified") and

                        obs.get("classification") == gt["category"].value) else 0.0



                           

    done = obs.get("investigations_done", [])

    min_inv = gt.get("min_investigations", 2)

    inv_score = min(1.0, len(done) / min_inv) if min_inv > 0 else 1.0



                                                          

    root_investigated = 1.0 if gt["root_service"] in done else 0.0



              

    resolved_score = 1.0 if obs.get("resolved") else 0.0



    score = (0.30 * cls_score +

             0.30 * inv_score +

             0.25 * root_investigated +

             0.15 * resolved_score)



    return {

        "score": round(score, 4),

        "breakdown": {

            "classification":  cls_score,

            "investigation":   inv_score,

            "root_identified": root_investigated,

            "resolved":        resolved_score,

        },

        "feedback": (

            f"Classification: {cls_score:.2f} | "

            f"Investigation breadth: {inv_score:.2f} ({len(done)}/{min_inv} services) | "

            f"Root service found: {root_investigated:.2f} | "

            f"Resolved: {resolved_score:.2f}"

        ),

    }





def grade_task3(state: Dict[str, Any]) -> Dict[str, Any]:

    """
    Hard grader — full incident response.

    Phase scores (weighted):
      classification     20%  — correct IncidentCategory
      investigation      20%  — ≥ min_investigations services investigated
      root_coverage      25%  — fraction of root services investigated
      remediation        20%  — fraction of correct remediations applied
      resolution_quality 15%  — resolved + summary contains key terms
    """

    gt = state["ground_truth"]

    obs = state["observation"]



                    

    cls_score = 1.0 if (obs.get("classified") and

                        obs.get("classification") == gt["category"].value) else 0.0



                           

    done = set(obs.get("investigations_done", []))

    min_inv = gt.get("min_investigations", 3)

    inv_score = min(1.0, len(done) / min_inv)



                           

    root_services = set(gt.get("root_services", []))

    covered = root_services & done

    root_score = len(covered) / len(root_services) if root_services else 1.0



                         

    applied = set(obs.get("remediation_applied", []))

    correct = gt.get("correct_remediation_values", set())

    if not correct and "correct_remediations" in gt:

        correct = set(r.value for r in gt.get("correct_remediations", []))

    rem_score = len(applied & correct) / len(correct) if correct else 1.0

                                 

    wrong = applied - correct

    rem_score = max(0.0, rem_score - 0.1 * len(wrong))



                        

    res_score = 0.0

    if obs.get("resolved"):

        res_score = 0.5

        summary = obs.get("resolution_summary", "").lower()

        keywords = gt.get("resolution_keywords", [])

        kw_found = sum(1 for k in keywords if k in summary)

        if keywords:

            res_score += 0.5 * (kw_found / len(keywords))

        else:

            res_score = 1.0



    score = (0.20 * cls_score +

             0.20 * inv_score +

             0.25 * root_score +

             0.20 * rem_score +

             0.15 * res_score)



    return {

        "score": round(score, 4),

        "breakdown": {

            "classification":     cls_score,

            "investigation":      inv_score,

            "root_coverage":      round(root_score, 3),

            "remediation":        round(rem_score, 3),

            "resolution_quality": round(res_score, 3),

        },

        "feedback": (

            f"Classification: {cls_score:.2f} | "

            f"Investigation: {inv_score:.2f} ({len(done)}/{min_inv}) | "

            f"Root coverage: {root_score:.2f} ({covered}/{root_services}) | "

            f"Remediation: {rem_score:.2f} | "

            f"Resolution: {res_score:.2f}"

        ),

    }





GRADERS = {

    "alert_classification":  grade_task1,

    "root_cause_analysis":   grade_task2,

    "full_incident_response": grade_task3,

}
