"""ProfileService 测试。

覆盖：
  1. no_songs — 空歌单
  2. mocked_llm — 成功 LLM 分析
  3. llm_failure — LLM 拒绝 / API 错误
  4. song_sampling — 去重 + 频率排序 + 截断
  5. concurrent — asyncio.Lock() 防并发
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock, patch

from agent.services.profile_service import ProfileService, MAX_PROFILE_SONGS
from agent.state import playlist_store


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════


def _make_song(song_id: str, name: str = "歌", artist: str = "歌手") -> dict:
    return {
        "id": song_id,
        "name": name,
        "artists": [{"id": "1", "name": artist}],
        "album": {"id": "1", "name": "专辑"},
        "duration_ms": 200000,
    }


class TestProfileServiceNoSongs:
    """空歌单场景。"""

    def test_no_songs_returns_error(self):
        """无歌曲时 analyze() 返回错误。"""
        svc = ProfileService(llm_service=MagicMock())

        with patch("agent.services.profile_service.playlist_store.list_all", return_value=[]):
            import asyncio
            result = asyncio.run(svc.analyze())

        assert result.get("ok") is False
        assert "no songs" in result.get("error", "").lower()


class TestProfileServiceDedupAndSample:
    """去重 + 频率排序 + 截断。"""

    def setup_method(self):
        self.svc = ProfileService(llm_service=MagicMock())

    def test_dedup_by_id(self):
        """相同 id 只保留一条。"""
        songs = [_make_song("1"), _make_song("1"), _make_song("2")]
        sampled = self.svc._deduplicate_and_sample(songs)
        assert len(sampled) == 2
        ids = [s["id"] for s in sampled]
        assert ids == ["1", "2"]  # 频率相同，id 顺序

    def test_frequency_sort(self):
        """出现频次高的排前面。"""
        songs = [
            _make_song("1"), _make_song("2"), _make_song("2"),
            _make_song("3"), _make_song("3"), _make_song("3"),
        ]
        sampled = self.svc._deduplicate_and_sample(songs)
        assert len(sampled) == 3
        assert sampled[0]["id"] == "3"  # 出现 3 次
        assert sampled[1]["id"] == "2"  # 出现 2 次
        assert sampled[2]["id"] == "1"  # 出现 1 次

    def test_truncation(self):
        """超出 MAX_PROFILE_SONGS 时截断。"""
        songs = [_make_song(str(i)) for i in range(MAX_PROFILE_SONGS + 100)]
        sampled = self.svc._deduplicate_and_sample(songs)
        assert len(sampled) == MAX_PROFILE_SONGS

    def test_empty_input(self):
        """空输入 → 空列表。"""
        assert self.svc._deduplicate_and_sample([]) == []


class TestProfileServiceLLMAnalysis:
    """LLM 分析流程测试。"""

    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        """成功分析时返回 profile。"""
        mock_llm = AsyncMock()
        mock_llm.call_json.return_value = {
            "ok": True,
            "data": {
                "energy_baseline": 0.7,
                "tempo_preference": "moderate",
                "mood_distribution": {"happy": 0.5, "calm": 0.5},
                "era_affinity": {"2020s": 0.8, "2010s": 0.2},
                "vocal_preference": "mixed",
                "discovery_openness": 0.6,
                "listening_pattern": "mixed",
                "confidence": 0.8,
                "favorite_genres": ["pop", "rock"],
                "favorite_artists": ["周杰伦"],
                "music_preference_desc": "热爱流行与摇滚",
            },
        }

        svc = ProfileService(llm_service=mock_llm)
        with patch("agent.services.profile_service.playlist_store.list_all",
                   return_value=[{"playlist_id": "p1"}]):
            with patch("agent.services.profile_service.playlist_store.load_songs",
                       return_value=[_make_song("1"), _make_song("2")]):
                result = await svc.analyze()

        assert result["ok"] is True
        profile = result["profile"]
        assert profile["energy_baseline"] == 0.7
        assert profile["favorite_genres"] == ["pop", "rock"]
        assert profile["based_on_song_count"] == 2
        assert profile["sample_strategy"] == "all"
        assert "last_analyzed_at" in profile
        mock_llm.call_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_failure(self):
        """LLM 返回错误 → 传播错误。"""
        mock_llm = AsyncMock()
        mock_llm.call_json.return_value = {
            "ok": False,
            "error": {"code": "LLM_API_ERROR", "message": "API timeout"},
        }

        svc = ProfileService(llm_service=mock_llm)
        with patch("agent.services.profile_service.playlist_store.list_all",
                   return_value=[{"playlist_id": "p1"}]):
            with patch("agent.services.profile_service.playlist_store.load_songs",
                       return_value=[_make_song("1")]):
                result = await svc.analyze()

        assert result["ok"] is False
        assert "timeout" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_llm_http_error(self):
        """LLM 抛出异常 → 错误处理。"""
        mock_llm = AsyncMock()
        mock_llm.call_json.side_effect = RuntimeError("connection refused")

        svc = ProfileService(llm_service=mock_llm)
        with patch("agent.services.profile_service.playlist_store.list_all",
                   return_value=[{"playlist_id": "p1"}]):
            with patch("agent.services.profile_service.playlist_store.load_songs",
                       return_value=[_make_song("1")]):
                with pytest.raises(RuntimeError, match="connection refused"):
                    await svc.analyze()


class TestProfileServiceLock:
    """asyncio.Lock 防并发。"""

    @pytest.mark.asyncio
    async def test_concurrent_analyze_blocked(self):
        """并发 analyze 被 Lock 阻塞。"""
        import asyncio
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        # 让第一次调用长时间运行
        mock_llm.call_json.return_value = {
            "ok": True,
            "data": {"favorite_genres": ["pop"], "favorite_artists": [], "music_preference_desc": ""},
        }

        svc = ProfileService(llm_service=mock_llm)

        # 模拟一次 analyze 已经在进行中
        with patch("agent.services.profile_service.playlist_store.list_all",
                   return_value=[{"playlist_id": "p1"}]):
            with patch("agent.services.profile_service.playlist_store.load_songs",
                       return_value=[_make_song("1")]):
                # 先获取锁（模拟并发场景）
                await svc._lock.acquire()
                try:
                    # 第二次 analyze 应该被锁阻塞（超时检测）
                    with pytest.raises(asyncio.TimeoutError):
                        await asyncio.wait_for(svc.analyze(), timeout=0.1)
                finally:
                    svc._lock.release()
