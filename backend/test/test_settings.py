import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_get_settings():
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "llm_apikey" in data["data"]
    assert "netease_apikey" in data["data"]


def test_update_settings():
    response = client.put("/api/settings", json={"llm_apikey": "test-api-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["llm_apikey"] == "test-api-key"

    response = client.put("/api/settings", json={"netease_apikey": "netease-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["netease_apikey"] == "netease-key"


def test_update_settings_empty():
    response = client.put("/api/settings", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0