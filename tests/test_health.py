from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.db.session import get_db_session
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


async def _db_ok():
    yield AsyncMock()


async def _db_fail():
    mock = AsyncMock()
    mock.execute.side_effect = Exception("connection refused")
    yield mock


def test_health_db_connected():
    app.dependency_overrides[get_db_session] = _db_ok
    try:
        response = client.get("/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "connected"}
    finally:
        app.dependency_overrides.clear()


def test_health_db_unavailable():
    app.dependency_overrides[get_db_session] = _db_fail
    try:
        response = client.get("/health/db")
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()
