"""HTTP 路由测试 — 11 群组全覆盖（health / init / settings / playlist / user / feedback / memory / history / netease / feishu）。

覆盖：
  1. GET /api/health — 健康检查
  2. GET /api/init — 初始化数据拉取
  3. GET/PUT /api/settings — 设置 CRUD
  4. GET /api/playlist/list, GET/PUT/DELETE /api/playlist/{id}, POST /api/playlist/import
  5. GET /api/user/profile, PUT /api/user/baseinfo, POST /api/user/analyze
  6. GET /api/feedback, GET /api/feedback/stats, POST /api/feedback
  7. GET /api/memory/query, POST /api/memory/update, DELETE /api/memory/{key}
  8. GET /api/history/songs?limit=20&offset=0 — 分页
  9. POST /api/netease/login, GET /api/netease/status
  10. GET /api/feishu/status, GET /api/feishu/auth/url,
      GET /api/feishu/calendar/today, GET /api/feishu/calendar/current,
      POST /api/feishu/refresh

使用方法：
    cd dev
    python -m pytest tests/test_http_routes.py -v
"""

import json
import os
import sys
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.routes.http_routes import register_http_routes
from agent.state import settings_store, playlist_store, memory_store, player_state
from agent.state.state_manager import state_manager


# ═══════════════════════════════════════════════════════════════
# 夹具：隔离的临时数据目录（monkeypatch 保证测试间无状态残留）
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_data_dir(monkeypatch, tmp_path):
    """创建临时数据目录，用 monkeypatch 覆盖 settings 属性。"""
    tmpdir = str(tmp_path)
    from agent.config import settings as cfg
    monkeypatch.setattr(cfg, "DATA_DIR", tmpdir)
    monkeypatch.setattr(cfg, "MEMORY_FILE", os.path.join(tmpdir, "memory.json"))
    monkeypatch.setattr(cfg, "SETTINGS_FILE", os.path.join(tmpdir, "settings.json"))
    monkeypatch.setattr(cfg, "PLAYLISTS_FILE", os.path.join(tmpdir, "playlists.json"))
    monkeypatch.setattr(cfg, "PLAYER_MIRROR_FILE", os.path.join(tmpdir, "player_mirror.json"))
    monkeypatch.setattr(cfg, "PLAYER_HISTORY_FILE", os.path.join(tmpdir, "player_history.json"))
    monkeypatch.setattr(cfg, "PROGRAM_STATE_FILE", os.path.join(tmpdir, "program_state.json"))
    return tmpdir


@pytest.fixture
def client(tmp_data_dir):
    """使用临时目录的 HTTP 测试客户端。"""
    app = FastAPI()
    # 注入 RuntimeDJState 供 /api/playlist/sync-queue 使用
    state_manager.runtime_dj_state = {
        "playlist_queue": [],
        "queue_strategy": {},
    }
    register_http_routes(app)
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# 1. health
# ═══════════════════════════════════════════════════════════════


class TestHealth:
    """GET /api/health"""

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["status"] == "ok"
        assert body["data"]["init_mode"] in ("first_init", "new_day_init", "resume")

    def test_health_init_mode_first_init(self, client, tmp_data_dir):
        """program_state.json 不存在 → first_init。"""
        resp = client.get("/api/health")
        assert resp.json()["data"]["init_mode"] == "first_init"

    def test_health_init_mode_resume(self, client, tmp_data_dir):
        """program_state.json 是今天 → resume。"""
        from agent.state.program_state import DEFAULT_PROGRAM_STATE
        state = dict(DEFAULT_PROGRAM_STATE)
        import datetime
        state["program_date"] = datetime.date.today().isoformat()
        _write_json(os.path.join(tmp_data_dir, "program_state.json"), state)

        resp = client.get("/api/health")
        assert resp.json()["data"]["init_mode"] == "resume"


# ═══════════════════════════════════════════════════════════════
# 2. init
# ═══════════════════════════════════════════════════════════════


class TestInit:
    """GET /api/init"""

    def test_init_returns_all_sections(self, client):
        """init 返回 9 个 data 段（含契约补齐字段）。"""
        resp = client.get("/api/init")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert "agent" in data
        assert data["agent"]["version"] == "0.2.0"
        assert data["agent"]["persona"] == "night_dj"
        assert "settings" in data
        assert "netease" in data
        assert "user_profile" in data
        assert "playlists" in data
        assert "player" in data
        assert "recent_moods" in data
        assert isinstance(data["recent_moods"], list)
        assert "current_state" in data
        assert "is_playing" in data["current_state"]
        assert "calendar" in data
        assert "connected" in data["calendar"]

    def test_init_settings_defaults(self, client):
        resp = client.get("/api/init")
        s = resp.json()["data"]["settings"]
        assert isinstance(s["llm_apikey"], str)  # 可能是空或 .env 配置值

    def test_init_netease_mock(self, client):
        resp = client.get("/api/init")
        n = resp.json()["data"]["netease"]
        assert "login_status" in n

    def test_init_user_profile_empty(self, client):
        resp = client.get("/api/init")
        p = resp.json()["data"]["user_profile"]
        assert isinstance(p, dict)

    def test_init_playlists_empty(self, client):
        resp = client.get("/api/init")
        pl = resp.json()["data"]["playlists"]
        assert isinstance(pl, list)
        assert len(pl) == 0


# ═══════════════════════════════════════════════════════════════
# 3. settings
# ═══════════════════════════════════════════════════════════════


class TestSettings:
    """GET/PUT /api/settings"""

    def test_get_settings_defaults(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data["llm_apikey"], str)

    def test_put_settings_updates(self, client, tmp_data_dir):
        resp = client.put("/api/settings", json={
            "llm_apikey": "sk-test",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["llm_apikey"] == "sk-test"

        # 验证持久化
        saved = _read_json(os.path.join(tmp_data_dir, "settings.json"))
        assert saved["llm_apikey"] == "sk-test"

    def test_put_settings_partial(self, client):
        """只更新 llm_apikey。"""
        client.put("/api/settings", json={"llm_apikey": "sk-a"})
        resp = client.put("/api/settings", json={"llm_apikey": "sk-c"})
        data = resp.json()["data"]
        assert data["llm_apikey"] == "sk-c"


# ═══════════════════════════════════════════════════════════════
# 4. playlist
# ═══════════════════════════════════════════════════════════════


class TestPlaylist:
    """playlist CRUD + import"""

    def test_list_empty(self, client):
        resp = client.get("/api/playlist/list")
        assert resp.status_code == 200
        assert resp.json()["data"]["playlists"] == []

    def test_import_creates_playlist(self, client):
        resp = client.post("/api/playlist/import", json={
            "playlist_url": "https://music.163.com/playlist/123"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] != ""
        assert data["source_url"] == "https://music.163.com/playlist/123"
        assert "playlist_id" in data

    def test_get_playlist_by_id(self, client):
        created = client.post("/api/playlist/import", json={
            "playlist_url": "https://music.163.com/playlist/456"
        }).json()["data"]

        resp = client.get(f"/api/playlist/{created['playlist_id']}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["playlist"]["playlist_id"] == created["playlist_id"]

    def test_get_playlist_not_found(self, client):
        resp = client.get("/api/playlist/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["code"] == 1003

    def test_update_playlist(self, client):
        created = client.post("/api/playlist/import", json={
            "playlist_url": "https://music.163.com/playlist/789"
        }).json()["data"]

        resp = client.put(f"/api/playlist/{created['playlist_id']}", json={
            "name": "新名称",
            "remark": "新备注",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "新名称"

    def test_update_playlist_not_found(self, client):
        resp = client.put("/api/playlist/nonexistent", json={"name": "test"})
        assert resp.json()["code"] == 1003

    def test_delete_playlist(self, client):
        created = client.post("/api/playlist/import", json={
            "playlist_url": "https://music.163.com/playlist/000"
        }).json()["data"]

        resp = client.delete(f"/api/playlist/{created['playlist_id']}")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

        # 确认已删除
        resp = client.get(f"/api/playlist/{created['playlist_id']}")
        assert resp.json()["code"] == 1003

    def test_delete_playlist_not_found(self, client):
        resp = client.delete("/api/playlist/nonexistent")
        assert resp.json()["code"] == 1003

    def test_list_after_import(self, client):
        client.post("/api/playlist/import", json={
            "playlist_url": "https://music.163.com/playlist/a"
        })
        client.post("/api/playlist/import", json={
            "playlist_url": "https://music.163.com/playlist/b"
        })

        resp = client.get("/api/playlist/list")
        assert len(resp.json()["data"]["playlists"]) == 2

    def test_import_empty_url_fails(self, client):
        resp = client.post("/api/playlist/import", json={"playlist_url": ""})
        assert resp.json()["code"] == 1001

    def test_sync_queue_updates_backend(self, client, tmp_data_dir):
        """POST /api/playlist/sync-queue 应更新 RuntimeDJState 和 player_mirror.json。"""
        songs = [
            {"id": "1", "name": "Song A", "artists": [{"id": "a1", "name": "Artist A"}]},
            {"id": "2", "name": "Song B", "artists": [{"id": "b1", "name": "Artist B"}]},
        ]
        resp = client.post("/api/playlist/sync-queue", json={"songs": songs})
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

        # 确认 RuntimeDJState 已更新
        assert state_manager.runtime_dj_state["playlist_queue"] == songs
        assert state_manager.runtime_dj_state["queue_strategy"] == {"source": "playlist"}

        # 确认 player_mirror.json 已更新
        mirror = player_state.load_player_mirror()
        assert mirror["playlist_queue"] == songs

    def test_sync_queue_empty(self, client, tmp_data_dir):
        """POST /api/playlist/sync-queue 接受空列表。"""
        resp = client.post("/api/playlist/sync-queue", json={"songs": []})
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        assert state_manager.runtime_dj_state["playlist_queue"] == []


# ═══════════════════════════════════════════════════════════════
# 5. user
# ═══════════════════════════════════════════════════════════════


class TestUser:
    """user profile / baseinfo / analyze"""

    def test_profile_empty(self, client):
        resp = client.get("/api/user/profile")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_update_baseinfo(self, client, tmp_data_dir):
        resp = client.put("/api/user/baseinfo", json={
            "nickname": "测试用户",
            "avatar_url": "https://example.com/avatar.png",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["nickname"] == "测试用户"
        assert data["avatar_url"] == "https://example.com/avatar.png"

        # 确认持久化
        memory = _read_json(os.path.join(tmp_data_dir, "memory.json"))
        assert memory["profile"]["nickname"]["value"] == "测试用户"

    def test_update_baseinfo_partial(self, client):
        resp = client.put("/api/user/baseinfo", json={"nickname": "新昵称"})
        data = resp.json()["data"]
        assert data["nickname"] == "新昵称"

    def test_analyze_writes_profile(self, client, tmp_data_dir):
        from agent.services.profile_service import ProfileService, set_profile_service
        from unittest.mock import AsyncMock
        import json

        # 设置 ProfileService + mock LLM
        mock_llm = AsyncMock()
        mock_llm.call_json.return_value = {
            "ok": True,
            "data": {
                "energy_baseline": 0.6, "tempo_preference": "mixed",
                "mood_distribution": {"calm": 0.5, "happy": 0.5},
                "era_affinity": {"2020s": 1.0},
                "vocal_preference": "mixed", "discovery_openness": 0.5,
                "listening_pattern": "mixed", "confidence": 0.7,
                "favorite_genres": ["pop", "rock"],
                "favorite_artists": ["周杰伦"],
                "music_preference_desc": "测试描述",
            },
        }
        svc = ProfileService(llm_service=mock_llm)
        set_profile_service(svc)

        # 写入一首歌供分析
        pl_file = os.path.join(tmp_data_dir, "playlists.json")
        with open(pl_file, "w", encoding="utf-8") as f:
            json.dump({
                "playlists": [{"playlist_id": "p1", "name": "测试", "song_count": 1}],
                "songs": {"p1": [{"id": "1", "name": "夜曲", "artists": [{"name": "周杰伦"}], "album": {}, "duration_ms": 200000}]},
            }, f)

        resp = client.post("/api/user/analyze")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        assert resp.json()["data"].get("update_at", 0) > 0

        memory_path = os.path.join(tmp_data_dir, "memory.json")
        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                memory = json.load(f)
        else:
            memory = {}
        profile = memory.get("profile", {})
        assert "favorite_genres" in profile
        assert "music_preference_desc" in profile

    def test_analyze_then_profile_returns_data(self, client, tmp_data_dir):
        from agent.services.profile_service import ProfileService, set_profile_service
        from unittest.mock import AsyncMock
        import json

        mock_llm = AsyncMock()
        mock_llm.call_json.return_value = {
            "ok": True,
            "data": {
                "energy_baseline": 0.6, "tempo_preference": "mixed",
                "mood_distribution": {"calm": 0.5, "happy": 0.5},
                "era_affinity": {"2020s": 1.0},
                "vocal_preference": "mixed", "discovery_openness": 0.5,
                "listening_pattern": "mixed", "confidence": 0.7,
                "favorite_genres": ["pop", "rock"],
                "favorite_artists": ["周杰伦"],
                "music_preference_desc": "测试描述",
            },
        }
        svc = ProfileService(llm_service=mock_llm)
        set_profile_service(svc)

        pl_file = os.path.join(tmp_data_dir, "playlists.json")
        with open(pl_file, "w", encoding="utf-8") as f:
            json.dump({
                "playlists": [{"playlist_id": "p1", "name": "测试", "song_count": 1}],
                "songs": {"p1": [{"id": "1", "name": "夜曲", "artists": [{"name": "周杰伦"}], "album": {}, "duration_ms": 200000}]},
            }, f)

        client.post("/api/user/analyze")
        resp = client.get("/api/user/profile")
        data = resp.json()["data"]
        assert "pop" in data.get("favorite_genres", [])


# ═══════════════════════════════════════════════════════════════
# 6. feedback
# ═══════════════════════════════════════════════════════════════


class TestFeedback:
    """feedback list + stats"""

    def test_feedback_empty(self, client):
        resp = client.get("/api/feedback")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["records"] == []
        assert data["total"] == 0

    def test_feedback_stats_empty(self, client):
        resp = client.get("/api/feedback/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert stats["like_count"] == 0
        assert stats["dislike_count"] == 0
        assert stats["skip_count"] == 0

    def test_feedback_with_data(self, client, tmp_data_dir):
        """写入内存 feedback 后验证 list + stats。"""
        from agent.config import settings as cfg
        _write_json(cfg.MEMORY_FILE, {
            "feedback": {
                "song_001": {
                    "value": {"action": "like", "song_id": "001"},
                    "ts": 1000,
                },
                "song_002": {
                    "value": {"action": "dislike", "song_id": "002"},
                    "ts": 2000,
                },
                "song_003": {
                    "value": {"action": "skip", "song_id": "003"},
                    "ts": 3000,
                },
            }
        })

        # list
        resp = client.get("/api/feedback")
        data = resp.json()["data"]
        assert data["total"] == 3
        actions = {r["id"]: r["action"] for r in data["records"]}
        assert actions["song_001"] == "like"
        assert actions["song_002"] == "dislike"
        assert actions["song_003"] == "skip"

        # stats
        resp = client.get("/api/feedback/stats")
        stats = resp.json()["data"]
        assert stats["like_count"] == 1
        assert stats["dislike_count"] == 1
        assert stats["skip_count"] == 1

    # ── POST /api/feedback ──

    def test_feedback_submit_like(self, client):
        """提交 like 反馈，验证响应格式。"""
        resp = client.post("/api/feedback", json={
            "song_id": "song_999",
            "action": "like",
            "ts": 5000,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["recorded"] is True
        assert body["data"]["ts"] == 5000

    def test_feedback_submit_all_actions(self, client):
        """验证 4 种 action 都能正确提交。"""
        for action in ("like", "dislike", "skip", "favorite"):
            resp = client.post("/api/feedback", json={
                "song_id": f"song_{action}",
                "action": action,
                "ts": 0,
            })
            assert resp.status_code == 200
            assert resp.json()["code"] == 0
            assert resp.json()["data"]["recorded"] is True

    def test_feedback_submit_invalid_action(self, client):
        """不支持的 action 返回 1001。"""
        resp = client.post("/api/feedback", json={
            "song_id": "song_001",
            "action": "invalid_action",
            "ts": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["code"] == 1001

    def test_feedback_submit_empty_song_id(self, client):
        """空 song_id 返回 1001。"""
        resp = client.post("/api/feedback", json={
            "song_id": "",
            "action": "like",
            "ts": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["code"] == 1001

    def test_feedback_submit_persists_to_json(self, client, tmp_data_dir):
        """提交后确认数据写入 memory.json。"""
        from agent.config import settings as cfg
        client.post("/api/feedback", json={
            "song_id": "song_persist",
            "action": "like",
            "ts": 0,
        })
        saved = _read_json(cfg.MEMORY_FILE)
        feedback = saved.get("feedback", {})
        assert "song_persist" in feedback
        assert feedback["song_persist"]["value"]["action"] == "like"


# ═══════════════════════════════════════════════════════════════
# 8. memory
# ═══════════════════════════════════════════════════════════════


class TestMemory:
    """Memory query / update / delete"""

    def test_memory_query_empty(self, client, tmp_data_dir):
        """无数据时返回空列表。"""
        from agent.config import settings as cfg
        _write_json(cfg.MEMORY_FILE, {"profile": {}, "preference": {}, "context": {}, "feedback": {}})
        resp = client.get("/api/memory/query")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["memories"] == []

    def test_memory_query_by_category(self, client, tmp_data_dir):
        """按 category 查询 Memory。"""
        from agent.config import settings as cfg
        _write_json(cfg.MEMORY_FILE, {
            "preference": {
                "favorite_genres": {
                    "value": ["pop", "rock"],
                    "ts": 1000,
                }
            },
            "profile": {
                "nickname": {
                    "value": "test_user",
                    "ts": 2000,
                }
            }
        })
        resp = client.get("/api/memory/query?category=preference")
        memories = resp.json()["data"]["memories"]
        assert len(memories) == 1
        assert memories[0]["key"] == "favorite_genres"
        assert memories[0]["value"] == ["pop", "rock"]

    def test_memory_query_by_key(self, client, tmp_data_dir):
        """按 key 查询 Memory。"""
        from agent.config import settings as cfg
        _write_json(cfg.MEMORY_FILE, {
            "preference": {
                "favorite_genres": {
                    "value": ["pop"],
                    "ts": 1000,
                },
                "favorite_artists": {
                    "value": ["Jay"],
                    "ts": 2000,
                },
            }
        })
        resp = client.get("/api/memory/query?key=favorite_artists")
        memories = resp.json()["data"]["memories"]
        assert len(memories) == 1
        assert memories[0]["key"] == "favorite_artists"

    def test_memory_query_invalid_category(self, client):
        """无效 category 返回 1001。"""
        resp = client.get("/api/memory/query?category=invalid")
        assert resp.json()["code"] == 1001

    def test_memory_update_writes_value(self, client, tmp_data_dir):
        """POST /api/memory/update 写入后可通过 query 读取。"""
        from agent.config import settings as cfg
        resp = client.post("/api/memory/update", json={
            "key": "favorite_genres",
            "category": "preference",
            "value": ["lo-fi", "jazz"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["updated"] is True

        # 验证持久化
        saved = _read_json(cfg.MEMORY_FILE)
        assert saved["preference"]["favorite_genres"]["value"] == ["lo-fi", "jazz"]

    def test_memory_update_invalid_category(self, client):
        """无效 category 返回 1001。"""
        resp = client.post("/api/memory/update", json={
            "key": "test",
            "category": "invalid",
            "value": "test",
        })
        assert resp.json()["code"] == 1001

    def test_memory_delete_removes_key(self, client, tmp_data_dir):
        """DELETE /api/memory/{key} 删除后 query 返回空。"""
        from agent.config import settings as cfg
        _write_json(cfg.MEMORY_FILE, {
            "preference": {
                "favorite_genres": {
                    "value": ["pop"],
                    "ts": 1000,
                },
            }
        })
        resp = client.delete("/api/memory/favorite_genres?category=preference")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["deleted"] is True

        saved = _read_json(cfg.MEMORY_FILE)
        assert "favorite_genres" not in saved.get("preference", {})

    def test_memory_delete_not_found(self, client):
        """删除不存在的 key 返回 1003。"""
        resp = client.delete("/api/memory/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["code"] == 1003


# ═══════════════════════════════════════════════════════════════
# 9. history


class TestHistory:
    """history 分页查询"""

    def test_history_empty(self, client):
        resp = client.get("/api/history/songs")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_history_with_data(self, client, tmp_data_dir):
        """写入 player_history.json 后验证分页。"""
        from agent.config import settings as cfg
        items = [
            {"song_id": f"s{i:03d}", "played_at": i * 1000}
            for i in range(25)
        ]
        _write_json(cfg.PLAYER_HISTORY_FILE, items)

        resp = client.get("/api/history/songs")
        data = resp.json()["data"]
        assert data["total"] == 25
        assert len(data["items"]) == 20  # 默认 limit
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_history_pagination(self, client, tmp_data_dir):
        from agent.config import settings as cfg
        items = [{"song_id": f"s{i:03d}"} for i in range(25)]
        _write_json(cfg.PLAYER_HISTORY_FILE, items)

        resp = client.get("/api/history/songs?limit=5&offset=10")
        data = resp.json()["data"]
        assert len(data["items"]) == 5
        assert data["total"] == 25
        assert data["limit"] == 5
        assert data["offset"] == 10
        # 第 11 条（index 10）开始
        assert data["items"][0]["song_id"] == "s010"

    def test_history_limit_clamped(self, client):
        """limit 最大 200，最小 1。"""
        resp = client.get("/api/history/songs?limit=999")
        assert resp.json()["data"]["limit"] == 200

        resp = client.get("/api/history/songs?limit=0")
        assert resp.json()["data"]["limit"] == 1


# ═══════════════════════════════════════════════════════════════
# 10. netease
# ═══════════════════════════════════════════════════════════════


class TestNetease:
    """netease login + status（proxy 到 music_agent_api，单元测试时服务不可用）"""

    def test_login_phone_empty(self, client):
        """手机号登录缺参数返回错误"""
        resp = client.post("/api/netease/login", json={"type": "phone", "phone": "", "password": ""})
        assert resp.status_code == 200
        assert resp.json()["code"] == 1001

    def test_login_qr_proxy_unavailable(self, client):
        """QR 登录 — music_agent_api 不可用返回服务不可用"""
        resp = client.post("/api/netease/login", json={"type": "qr", "token": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["code"] == 3002

    def test_status_fallback(self, client):
        """status — music_agent_api 不可用时返回未登录"""
        resp = client.get("/api/netease/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "login_status" in data
        assert data["login_status"] is False


# ═══════════════════════════════════════════════════════════════
# 11. feishu
# ═══════════════════════════════════════════════════════════════


class TestFeishu:
    """飞书日历路由（proxy 到 music_agent_api，单元测试时服务不可用）"""

    def test_status_unavailable(self, client):
        """status — 服务不可用返回未连接"""
        resp = client.get("/api/feishu/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "connected" in data
        assert data["connected"] is False

    def test_auth_url_unavailable(self, client):
        """auth/url — 服务不可用返回错误"""
        resp = client.get("/api/feishu/auth/url")
        assert resp.status_code == 200
        assert resp.json()["code"] == 3002

    def test_calendar_today_fallback_to_mock(self, client):
        """calendar/today — 服务不可用回退到 mock"""
        resp = client.get("/api/feishu/calendar/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "date" in data["data"]
        assert "event_count" in data["data"]
        assert data["data"]["source"] == "feishu_mock"

    def test_calendar_current_fallback_to_mock(self, client):
        """calendar/current — 服务不可用回退到 mock"""
        resp = client.get("/api/feishu/calendar/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "has_event" in data["data"]
        assert data["data"]["source"] == "feishu_mock"

    def test_refresh(self, client):
        """refresh — 总是返回 ok"""
        resp = client.post("/api/feishu/refresh")
        assert resp.status_code == 200
        assert resp.json()["code"] == 0


# ═══════════════════════════════════════════════════════════════
# 12. 统一响应格式
# ═══════════════════════════════════════════════════════════════


class TestResponseFormat:
    """所有 endpoint 返回统一格式 {code, msg, data}。"""

    ENDPOINTS = [
        ("GET", "/api/health"),
        ("GET", "/api/init"),
        ("GET", "/api/settings"),
        ("GET", "/api/playlist/list"),
        ("GET", "/api/user/profile"),
        ("GET", "/api/feedback"),
        ("GET", "/api/feedback/stats"),
        ("GET", "/api/memory/query"),
        ("GET", "/api/history/songs"),
        ("GET", "/api/netease/status"),
        ("GET", "/api/feishu/status"),
        ("GET", "/api/feishu/calendar/today"),
        ("GET", "/api/feishu/calendar/current"),
        ("POST", "/api/feishu/refresh"),
    ]

    def test_all_endpoints_have_unified_format(self, client):
        for method, path in self.ENDPOINTS:
            resp = client.request(method, path)
            assert resp.status_code == 200, f"{method} {path} failed"
            body = resp.json()
            assert "code" in body, f"{method} {path} missing code"
            assert "msg" in body, f"{method} {path} missing msg"
            assert "data" in body, f"{method} {path} missing data"
            assert body["code"] == 0, f"{method} {path} code != 0: {body}"


# ═══════════════════════════════════════════════════════════════
# 10. Store 隔离 —— route 不直接 open json
# ═══════════════════════════════════════════════════════════════


class TestStoreIsolation:
    """所有数据读写经过 Store，route 不直接 open json。"""

    def test_settings_persisted_via_store(self, client, tmp_data_dir):
        client.put("/api/settings", json={"llm_apikey": "sk-store-test"})
        # 通过 store 验证
        loaded = settings_store.load()
        assert loaded["llm_apikey"] == "sk-store-test"

    def test_playlist_persisted_via_store(self, client, tmp_data_dir):
        client.post("/api/playlist/import", json={
            "playlist_url": "https://music.163.com/playlist/store-test"
        })
        pls = playlist_store.list_all()
        assert len(pls) == 1
        assert "store-test" in pls[0]["source_url"]

    def test_import_from_qq(self, client, tmp_data_dir):
        """import_from_qq 写入 playlists.json。"""
        mock_songs_data = {
            "code": 0,
            "msg": "ok",
            "data": {
                "info": {
                    "title": "我的QQ歌单",
                    "picurl": "http://cover.url",
                    "desc": "测试歌单",
                },
                "songs": [
                    {
                        "id": 1001, "mid": "mid1", "name": "夜曲",
                        "singer": [{"id": 1, "name": "周杰伦"}],
                        "album": {"id": 100, "name": "叶惠美"},
                        "interval": 240, "pay": {"pay_play": 0},
                    },
                ],
            },
        }
        with patch("agent.routes.http_routes._call_qq_api") as mock_qq:
            mock_qq.return_value = mock_songs_data
            resp = client.post("/api/qq/playlist/import", json={"qq_id": "12345"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        pl = body["data"]
        assert pl["provider"] == "qqmusic"
        assert pl["qq_id"] == 12345
        assert pl["name"] == "我的QQ歌单"
        assert pl["song_count"] == 1
        assert pl["description"] == "测试歌单"

        # 验证持久化
        pls = playlist_store.list_all()
        assert len(pls) == 1
        assert pls[0]["playlist_id"] == pl["playlist_id"]

    def test_import_from_qq_empty_songs(self, client, tmp_data_dir):
        """QQ 导入空歌单。"""
        with patch("agent.routes.http_routes._call_qq_api") as mock_qq:
            mock_qq.return_value = {
                "code": 0,
                "msg": "ok",
                "data": {
                    "info": {"title": "", "picurl": "", "desc": ""},
                    "songs": [],
                },
            }
            resp = client.post("/api/qq/playlist/import", json={"qq_id": "99999"})

        assert resp.status_code == 200
        pl = resp.json()["data"]
        assert pl["song_count"] == 0

    def test_import_from_qq_api_failure(self, client, tmp_data_dir):
        """QQ API 返回错误 → 不透传写入。"""
        with patch("agent.routes.http_routes._call_qq_api") as mock_qq:
            mock_qq.return_value = {"code": -1, "msg": "not found"}
            resp = client.post("/api/qq/playlist/import", json={"qq_id": "bad_id"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] != 0
        assert "not found" in body["msg"]
        # 验证没有写入
        assert playlist_store.list_all() == []
