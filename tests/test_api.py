import pytest

from fastapi.testclient import TestClient



from api.app import app



client = TestClient(app)



def test_health_endpoint():

    response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {

        "status": "ok",

        "environment": "incident-response-openenv",

        "version": "1.0.0"

    }
