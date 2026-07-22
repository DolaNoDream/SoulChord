"""dj_host 图节点单元测试。

覆盖（5 测试）：
1. 无 current_song → 跳过
2. 同一首歌已生成话术 → 去重跳过
3. DJHostService 返回 text → pending_payload.dj_speech 正确填充
4. DJHostService 返回空 → 不设 dj_speech
5. RuntimeDJState 追踪更新

使用方法：
    cd dev
    python -m pytest tests/test_dj_host_node.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock


def _make_state(*, song_id="song_123", song_name="晴天", artist="周杰伦",
                 playlist_queue=None, program_mood="warm", today_theme="测试",
                 day_period="evening", nickname="", user_mood="",
                 last_speech_song_id="", last_speech_at_ms=0,
                 has_dj_host=True, returns_text="DJ 话术"):
    """构造标准测试 state。"""
    state = {
        "trigger_type": "dj_monologue",
        "runtime_snapshot": {
            "current_song": {
                "song_id": song_id,
                "id": song_id,
                "name": song_name,
                "artist": artist,
            },
            "playlist_queue": playlist_queue or [],
            "program_mood": program_mood,
        },
        "program": {"today_theme": today_theme},
        "user": {"nickname": nickname},
        "environment": {"day_period": day_period, "user_mood": user_mood},
        "dependencies": {
            "runtime_dj_state": {
                "last_dj_speech_song_id": last_speech_song_id,
                "last_dj_speech_at_ms": last_speech_at_ms,
            },
        },
        "__refs__": {},
    }

    if has_dj_host:
        mock_svc = AsyncMock()
        mock_svc.generate_speech.return_value = returns_text
        state["__refs__"]["dj_host_service"] = mock_svc

    return state


# ═══════════════════════════════════════════════════════════════
# Test cases
# ═══════════════════════════════════════════════════════════════
class TestDJHostNode:
    """dj_host 节点测试。"""

    @pytest.mark.asyncio
    async def test_no_current_song_skips(self):
        """TC-01: 无 current_song → 跳过，无 pending_payload。"""
        from agent.nodes.dj_host import dj_host_node

        state = _make_state(song_id="")
        state["runtime_snapshot"]["current_song"] = None

        result = await dj_host_node(state)
        assert result.get("pending_payload") is None, "无歌曲时应跳过"
        assert result.get("should_speak") is False

    @pytest.mark.asyncio
    async def test_duplicate_speech_skips(self):
        """TC-02: 同一首歌已生成话术 (<60s) → 去重跳过。"""
        from agent.nodes.dj_host import dj_host_node

        state = _make_state(last_speech_song_id="song_123", last_speech_at_ms=9999999999000)

        result = await dj_host_node(state)
        assert result.get("pending_payload") is None, "已生成话术时应跳过"
        assert result.get("should_speak") is False

    @pytest.mark.asyncio
    async def test_dj_speech_produced(self):
        """TC-03: 正常路 → pending_payload.dj_speech 含 text。"""
        from agent.nodes.dj_host import dj_host_node

        state = _make_state(returns_text="接下来为你带来一首特别的歌...")

        result = await dj_host_node(state)

        payload = result.get("pending_payload") or {}
        dj_speech = payload.get("dj_speech") or {}
        assert dj_speech.get("text") == "接下来为你带来一首特别的歌...", \
            f"dj_speech.text 错误: {dj_speech.get('text')}"
        assert result.get("should_speak") is True
        assert result.get("should_play_music") is False  # 队列空 → False

    @pytest.mark.asyncio
    async def test_dj_speech_with_next_song(self):
        """TC-04: 有下一首歌 → should_play_music=True。"""
        from agent.nodes.dj_host import dj_host_node

        state = _make_state(
            playlist_queue=[{"song_id": "song_456", "name": "江南", "artist": "林俊杰"}],
            returns_text="下一首江南送给你...",
        )

        result = await dj_host_node(state)

        payload = result.get("pending_payload") or {}
        dj_speech = payload.get("dj_speech") or {}
        assert dj_speech.get("text") == "下一首江南送给你..."
        assert result.get("should_speak") is True
        assert result.get("should_play_music") is True  # 有下一首 → True

    @pytest.mark.asyncio
    async def test_empty_speech_no_payload(self):
        """TC-05: DJHostService 返回空 → 不设 dj_speech。"""
        from agent.nodes.dj_host import dj_host_node

        state = _make_state(returns_text="")

        result = await dj_host_node(state)
        assert result.get("pending_payload") is None, "空话术时不设 payload"
        assert result.get("should_speak") is False

    @pytest.mark.asyncio
    async def test_rds_tracking_updated(self):
        """TC-06: 生成话术后 → RuntimeDJState 追踪字段更新。"""
        from agent.nodes.dj_host import dj_host_node

        state = _make_state(returns_text="来听这首歌...")

        rds = state["dependencies"]["runtime_dj_state"]
        assert rds["last_dj_speech_song_id"] == ""  # 更新前

        await dj_host_node(state)

        assert rds["last_dj_speech_song_id"] == "song_123", "song_id 应更新"
        assert rds["last_dj_speech_at_ms"] > 0, "时间戳应更新"
