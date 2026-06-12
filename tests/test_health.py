from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_status_ok():
    response = client.get("/health")
    assert response.json()["status"] == "ok"


def test_root_returns_200():
    response = client.get("/")
    assert response.status_code == 200
