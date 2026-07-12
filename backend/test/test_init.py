import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_init():
    response = client.get("/api/init")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["msg"] == "ok"
    assert "data" in data
    assert "settings" in data["data"]
    assert "netease_status" in data["data"]
    assert "user_profile" in data["data"]
    assert "playlists" in data["data"]
    assert "player_state" in data["data"]