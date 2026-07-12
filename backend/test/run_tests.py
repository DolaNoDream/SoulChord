import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

passed = 0
failed = 0


def test(name, func):
    global passed, failed
    try:
        func()
        print(f"✓ {name}")
        passed += 1
    except Exception as e:
        print(f"✗ {name}: {e}")
        failed += 1


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


if __name__ == "__main__":
    print("=" * 60)
    print("Running SoulChord Backend API Tests")
    print("=" * 60)
    print()

    test("GET /api/init", test_init)
    test("GET /api/settings", test_get_settings)
    test("PUT /api/settings", test_update_settings)
    test("PUT /api/settings (empty)", test_update_settings_empty)
    test("GET /api/netease/status", test_get_netease_status)
    test("POST /api/netease/login", test_netease_login)
    test("POST /api/playlist/import", test_import_playlist)
    test("GET /api/playlist/list", test_get_playlist_list)
    test("GET /api/playlist/{id}", test_get_playlist)
    test("GET /api/playlist/{id} (not found)", test_get_playlist_not_found)
    test("PUT /api/playlist/{id}", test_update_playlist)
    test("PUT /api/playlist/{id} (not found)", test_update_playlist_not_found)
    test("PUT /api/playlist/{id} (empty)", test_update_playlist_empty)
    test("DELETE /api/playlist/{id}", test_delete_playlist)
    test("DELETE /api/playlist/{id} (not found)", test_delete_playlist_not_found)
    test("GET /api/user/profile", test_get_user_profile)
    test("PUT /api/user/baseinfo", test_update_user_baseinfo)
    test("PUT /api/user/baseinfo (empty)", test_update_user_baseinfo_empty)
    test("POST /api/user/analyze", test_analyze_user)

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)