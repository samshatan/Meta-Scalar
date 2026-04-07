import sys

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



from environment.tasks import _health

from environment.models import ServiceHealth



def test_health_utility():

                     

    health = _health("payment-service", "degraded", 0.03, 5420.0, 3)

    assert isinstance(health, ServiceHealth)

    assert health.name == "payment-service"

    assert health.status == "degraded"

    assert health.error_rate == 0.03

    assert health.p99_latency_ms == 5420.0

    assert health.pod_count == 3



                       

    health2 = _health("redis-cache", "healthy", 0.00, 1.2, 2)

    assert health2.name == "redis-cache"

    assert health2.status == "healthy"

    assert health2.error_rate == 0.00

    assert health2.p99_latency_ms == 1.2

    assert health2.pod_count == 2
