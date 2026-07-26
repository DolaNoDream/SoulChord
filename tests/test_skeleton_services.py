"""FeishuService / ASRService 骨架测试。

覆盖：
  1. FeishuService.get_calendar_current 返回正确 schema
  2. FeishuService.get_calendar_today 返回正确 schema（含聚合标签）
  3. ASRService.recognize 返回正确 schema
  4. ASRService.recognize 空 URL 返回空结果
  5. adapter dispatch query_calendar 经 FeishuService
  6. adapter dispatch query_calendar scope=current

使用方法：
    cd dev
    python -m pytest tests/test_skeleton_services.py -v
"""

import sys
import os
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.services.feishu_service import FeishuService, feishu_service
from agent.services.asr_service import ASRService, asr_service


# ═══════════════════════════════════════════════════════════════
# FeishuService tests
# ═══════════════════════════════════════════════════════════════


class TestFeishuService:
    @pytest.mark.asyncio
    async def test_get_calendar_current_returns_correct_schema(self):
        """get_calendar_current 返回完整 schema（含 has_event/title/location/participants/source）。"""
        result = await feishu_service.get_calendar_current()
        assert isinstance(result, dict)
        assert "has_event" in result
        assert "title" in result
        assert "location" in result
        assert "participants" in result
        assert "source" in result
        assert result["source"] == "feishu_mock"
        assert isinstance(result["participants"], list)
        assert result["has_event"] is True

    @pytest.mark.asyncio
    async def test_get_calendar_today_returns_correct_schema(self):
        """get_calendar_today 返回正确 schema（含 date/event_count/tags/is_busy/source）。"""
        result = await feishu_service.get_calendar_today()
        assert isinstance(result, dict)
        assert "date" in result
        assert "event_count" in result
        assert "tags" in result
        assert "is_busy" in result
        assert "source" in result
        assert result["source"] == "feishu_mock"
        assert isinstance(result["tags"], list)
        assert result["event_count"] >= 0

    @pytest.mark.asyncio
    async def test_calendar_tags_are_aggregate_labels(self):
        """日程标签是聚合标签，不包含原始标题/地点/参与人。"""
        result = await feishu_service.get_calendar_today()
        for tag in result["tags"]:
            assert isinstance(tag, str)
            # 不应包含原始个人数据
            assert tag not in ("张三", "李四", "3楼会议室")


# ═══════════════════════════════════════════════════════════════
# ASRService tests
# ═══════════════════════════════════════════════════════════════


class TestASRService:
    @pytest.mark.asyncio
    async def test_recognize_returns_correct_schema(self):
        """recognize 返回完整 schema（含 text/confidence/duration_ms/source）。"""
        # 无 API Key 时降级返回 fish_audio_mock
        result = await asr_service.recognize(b"mock audio data")
        assert isinstance(result, dict)
        assert "text" in result
        assert "confidence" in result
        assert "duration_ms" in result
        assert "source" in result
        assert result["source"] in ("fish_audio_mock", "fish_audio"), \
            f"source 应为 fish_audio_mock，实际: {result['source']}"
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_recognize_empty_data_returns_empty_text(self):
        """空 audio_data 返回 text="" / confidence=0.0 / duration_ms=0。"""
        result = await asr_service.recognize(b"")
        assert result["text"] == ""
        assert result["confidence"] == 0.0
        assert result["duration_ms"] == 0
        # 无 API Key 时降级为 fish_audio_mock
        assert result["source"] in ("fish_audio_mock", "fish_audio"), \
            f"source 应为 fish_audio_mock，实际: {result['source']}"

    @pytest.mark.asyncio
    async def test_recognize_empty_data_returns_empty(self):
        """空 audio_data 返回空结果。"""
        result = await asr_service.recognize(b"")
        assert result["text"] == ""


# ═══════════════════════════════════════════════════════════════
# adapter dispatch 集成测试
# ═══════════════════════════════════════════════════════════════


class TestAdapterFeishuDispatch:
    @pytest.mark.asyncio
    async def test_query_calendar_dispatches_to_feishu_today(self):
        """adapter dispatch query_calendar 默认 scope=today 调 feishu.get_calendar_today。"""
        with patch("agent.services.adapter.adapter.feishu.get_calendar_today",
                   new_callable=AsyncMock, return_value={"date": "2026-07-17", "source": "feishu_mock"}):
            from agent.services.adapter import adapter
            result = await adapter.dispatch("query_calendar", {})
        assert result["date"] == "2026-07-17"
        assert result["source"] == "feishu_mock"

    @pytest.mark.asyncio
    async def test_query_calendar_scope_current(self):
        """adapter dispatch query_calendar scope=current 调 feishu.get_calendar_current。"""
        with patch("agent.services.adapter.adapter.feishu.get_calendar_current",
                   new_callable=AsyncMock, return_value={"has_event": True, "title": "会议", "source": "feishu_mock"}):
            from agent.services.adapter import adapter
            result = await adapter.dispatch("query_calendar", {"scope": "current"})
        assert result["has_event"] is True
        assert result["title"] == "会议"

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_not_implemented(self):
        """adapter dispatch 未知 tool 抛 NotImplementedError。"""
        from agent.services.adapter import adapter
        with pytest.raises(NotImplementedError, match="Unknown tool"):
            await adapter.dispatch("nonexistent_tool", {})


class TestAdapterPlayMusic:
    """adapter dispatch play_music 空 query/真实 query 测试。"""

    @pytest.mark.asyncio
    async def test_play_music_without_query_returns_error(self):
        """play_music 不传 query → MISSING_QUERY。"""
        from agent.services.adapter import adapter
        result = await adapter.dispatch("play_music", {})
        assert result.get("status") == "error"
        assert result.get("code") == "MISSING_QUERY"
        assert "query" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_play_music_with_query_calls_search(self):
        """play_music 传 query → 调 search_songs（fallback，无 Provider 时）。"""
        with patch("agent.services.adapter.adapter._get_search_service",
                   return_value=None):
            with patch("agent.services.adapter.adapter.music.search_songs",
                       new_callable=AsyncMock,
                       return_value=[{"song_id": "509781655", "name": "想你就写信"}]):
                from agent.services.adapter import adapter
                result = await adapter.dispatch("play_music", {"query": "周杰伦"})
        assert result["success"] is True
        assert len(result["songs"]) == 1
        assert result["songs"][0]["song_id"] == "509781655"

    @pytest.mark.asyncio
    async def test_play_url_not_found_returns_error(self):
        """play_music song_id 无有效 play_url → PLAY_URL_NOT_FOUND。"""
        with patch("agent.services.adapter.adapter.music.get_play_url",
                   new_callable=AsyncMock, return_value=None):
            from agent.services.adapter import adapter
            result = await adapter.dispatch("play_music", {"song_id": "default_morning_001"})
        assert result.get("status") == "error"
        assert result.get("code") == "PLAY_URL_NOT_FOUND"
