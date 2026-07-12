import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_import_playlist():
    response = client.post("/api/playlist/import", json={
        "playlist_url": "https://music.163.com/#/playlist?id=123456"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "playlist_id" in data["data"]
    assert data["data"]["source_url"] == "https://music.163.com/#/playlist?id=123456"
    return data["data"]["playlist_id"]


def test_get_playlist_list():
    response = client.get("/api/playlist/list")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


def test_get_playlist():
    playlist_id = test_import_playlist()
    response = client.get(f"/api/playlist/{playlist_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["playlist_id"] == playlist_id


def test_get_playlist_not_found():
    response = client.get("/api/playlist/nonexistent-id")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1003
    assert data["msg"] == "歌单不存在"


def test_update_playlist():
    playlist_id = test_import_playlist()
    response = client.put(f"/api/playlist/{playlist_id}", json={
        "name": "测试歌单"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "测试歌单"


def test_update_playlist_not_found():
    response = client.put("/api/playlist/nonexistent-id", json={
        "name": "测试"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1003


def test_update_playlist_empty():
    playlist_id = test_import_playlist()
    response = client.put(f"/api/playlist/{playlist_id}", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1001


def test_delete_playlist():
    playlist_id = test_import_playlist()
    response = client.delete(f"/api/playlist/{playlist_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0


def test_delete_playlist_not_found():
    response = client.delete("/api/playlist/nonexistent-id")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1003