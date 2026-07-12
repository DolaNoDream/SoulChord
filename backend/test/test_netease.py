import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_get_netease_status():
    response = client.get("/api/netease/status")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "login_status" in data["data"]
    assert "nickname" in data["data"]


def test_netease_login():
    response = client.post("/api/netease/login", json={"credential": "test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["login_status"] is True
    assert data["data"]["nickname"] == "网易云用户"