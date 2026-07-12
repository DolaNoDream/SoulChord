import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_get_user_profile():
    response = client.get("/api/user/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "nickname" in data["data"]
    assert "favorite_genres" in data["data"]
    assert "favorite_artists" in data["data"]
    assert "music_preference_desc" in data["data"]
    assert "AI_conclustion" in data["data"]
    assert "update_at" in data["data"]


def test_update_user_baseinfo():
    response = client.put("/api/user/baseinfo", json={
        "nickname": "测试用户"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["nickname"] == "测试用户"

    response = client.put("/api/user/baseinfo", json={
        "nickname": "新昵称",
        "avatar_url": "https://example.com/avatar.jpg"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["nickname"] == "新昵称"
    assert data["data"]["avatar_url"] == "https://example.com/avatar.jpg"


def test_update_user_baseinfo_empty():
    response = client.put("/api/user/baseinfo", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1001


def test_analyze_user():
    response = client.post("/api/user/analyze")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "update_at" in data["data"]