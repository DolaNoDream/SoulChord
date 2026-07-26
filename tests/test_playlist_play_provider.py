"""播放路由 Provider 隔离测试（v9.15 P4）。

核心验证：
  1. QQ 歌曲（有 sources[]） → 走 QQProvider，不走 _call_music_api
  2. Netease 歌曲（无 sources） → 走 _call_music_api（旧路径向后兼容）
  3. Provider 全失败 → 返回 3002 错误

此测试覆盖了 P1-P4 中最关键的「Provider 隔离」：
数据里面 provider 正确，但执行链路没有消费 provider → 这个 bug 不能再次出现。
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.routes.http_routes import register_http_routes
from agent.state.state_manager import state_manager


@pytest.fixture
def client(monkeypatch, tmp_path):
    """HTTP 测试客户端（独立数据目录）。"""
    from agent.config import settings as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cfg, "SETTINGS_FILE", os.path.join(str(tmp_path), "settings.json"))
    monkeypatch.setattr(cfg, "AGENT_PORT", 8000)

    app = FastAPI()
    state_manager.runtime_dj_state = {"playlist_queue": [], "queue_strategy": {}}
    register_http_routes(app)
    return TestClient(app)


def _mock_source(provider: str) -> MagicMock:
    """创建 mock SongSource。"""
    s = MagicMock()
    s.provider = provider
    return s


class TestPlaylistPlayProviderIsolation:
    """Provider 隔离：QQ 歌曲不走 Netease，Netease 歌曲不走 Provider。"""

    # ── QQ 歌曲路径 ──

    def test_qq_song_uses_qq_provider(self, client):
        """QQ 歌曲走 Provider 路径，不调 _call_music_api。"""
        song_body = {
            "id": "4829184",
            "name": "讨厌红楼梦",
            "artists": [{"id": "123", "name": "陶喆"}],
            "sources": [
                {"provider": "qqmusic", "platform_id": "4829184", "platform_mid": "004bsQQ30reOH6"}
            ],
        }

        mock_qq_provider = MagicMock()
        mock_qq_provider.name = "qqmusic"
        mock_qq_provider.get_play_url = AsyncMock(return_value="http://qq-cdn.url/song.mp3")

        mock_selector = MagicMock()
        mock_source = _mock_source("qqmusic")
        mock_selector.rank.return_value = [mock_source]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_qq_provider

        with patch("agent.routes.http_routes._call_music_api", new_callable=AsyncMock) as mock_call_music:
            with patch(
                "agent.services.play_service._get_provider_infra",
                return_value=(mock_selector, mock_registry),
            ):
                resp = client.post("/api/playlist/play", json=song_body)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

        # 验证走了 Provider 路径
        mock_selector.rank.assert_called_once()
        mock_registry.get.assert_called_once_with("qqmusic")
        mock_qq_provider.get_play_url.assert_called_once_with(mock_source)

        # ★ 核心断言：绝不允许调 _call_music_api
        mock_call_music.assert_not_called()

        # 验证 proxy URL 包含 provider=qqmusic
        play_url = body["data"]["play_url"]
        assert "provider=qqmusic" in play_url

    def test_qq_song_all_providers_fail(self, client):
        """所有 Provider 都失败时返回 3002 错误。"""
        song_body = {
            "id": "4829184",
            "name": "讨厌红楼梦",
            "sources": [
                {"provider": "qqmusic", "platform_id": "4829184", "platform_mid": "004bsQQ30reOH6"}
            ],
        }

        mock_qq_provider = MagicMock()
        mock_qq_provider.get_play_url = AsyncMock(return_value=None)  # 返回 None = 失败

        mock_selector = MagicMock()
        mock_source = _mock_source("qqmusic")
        mock_selector.rank.return_value = [mock_source]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_qq_provider

        with patch("agent.services.play_service._get_provider_infra", return_value=(mock_selector, mock_registry)):
            resp = client.post("/api/playlist/play", json=song_body)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 3002
        assert "无法获取歌曲播放地址" in body["msg"]

    def test_qq_song_multiple_sources_priority(self, client):
        """多源歌曲按优先级选择 provider。"""
        song_body = {
            "id": "999",
            "name": "跨平台歌曲",
            "sources": [
                {"provider": "qqmusic", "platform_id": "qq999", "platform_mid": "mid999"},
                {"provider": "netease", "platform_id": "ne999"},
            ],
        }

        # 两个 provider 都 mock
        mock_qq = MagicMock()
        mock_qq.get_play_url = AsyncMock(return_value="http://qq.url/song.mp3")
        mock_netease = MagicMock()
        mock_netease.get_play_url = AsyncMock(return_value="http://163.url/song.mp3")

        mock_selector = MagicMock()
        mock_src_qq = _mock_source("qqmusic")
        mock_src_ne = _mock_source("netease")
        # 默认优先级：netease 优先
        mock_selector.rank.return_value = [mock_src_ne, mock_src_qq]

        mock_registry = MagicMock()
        def _get_side_effect(name):
            return {"netease": mock_netease, "qqmusic": mock_qq}.get(name)
        mock_registry.get.side_effect = _get_side_effect

        with patch("agent.services.play_service._get_provider_infra", return_value=(mock_selector, mock_registry)):
            resp = client.post("/api/playlist/play", json=song_body)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

        # 应该选 netease（默认优先级第一）
        mock_netease.get_play_url.assert_called_once_with(mock_src_ne)
        # proxy_url 包含 provider=netease
        assert "provider=netease" in body["data"]["play_url"]

    # ── Netease 旧路径 ──

    def test_netease_song_legacy_path(self, client):
        """无 sources 的旧数据走 Netease-only 路径。"""
        song_body = {
            "id": "123456",
            "name": "夜曲",
            "artists": [{"id": "1", "name": "周杰伦"}],
        }

        with patch(
            "agent.services.music_service.MusicService.get_play_url",
            new_callable=AsyncMock,
        ) as mock_get_play_url:
            mock_get_play_url.return_value = "http://163-cdn.url/song.mp3"
            resp = client.post("/api/playlist/play", json=song_body)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

        # 验证走了 MusicService（旧 Netease）路径
        mock_get_play_url.assert_called_once_with("123456")

        # proxy URL 默认 provider=netease
        assert "provider=netease" in body["data"]["play_url"]

    def test_netease_song_legacy_path_failure(self, client):
        """Netease-only 路径中 API 失败时返回 3002 错误。"""
        song_body = {
            "id": "123456",
            "name": "夜曲",
        }

        with patch(
            "agent.services.music_service.MusicService.get_play_url",
            new_callable=AsyncMock,
        ) as mock_get_play_url:
            mock_get_play_url.return_value = None  # API 失败返回 None
            resp = client.post("/api/playlist/play", json=song_body)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 3002

    # ── 边界：有 ID 但无 sources ──

    def test_qq_id_but_no_sources_still_netease(self, client):
        """QQ ID 歌曲但无 sources[] 字段 → 走 Netease 旧路径（向后兼容）。"""
        song_body = {
            "id": "4829184",
            "name": "讨厌红楼梦",
        }

        with patch(
            "agent.services.music_service.MusicService.get_play_url",
            new_callable=AsyncMock,
        ) as mock_get_play_url:
            mock_get_play_url.return_value = "http://163-cdn.url/song.mp3"
            resp = client.post("/api/playlist/play", json=song_body)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        mock_get_play_url.assert_called_once_with("4829184")
