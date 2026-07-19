"""WS Phase 2-lite 测试 — transition_speech / error WS push / heartbeat。

覆盖：
  1. emit_response → ws_out_queue 内容校验（transition_speech + error）
  2. ConnectionManager pong 跟踪 + stale disconnect
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.nodes.emit_response import emit_response_node
from agent.runtime.ws_sender import ws_out_queue
from agent.runtime.ws_manager import ConnectionManager


# ── 辅助：清空 ws_out_queue ──


def _drain_queue(q: asyncio.Queue) -> list:
    """清空队列并返回所有消息。"""
    msgs = []
    while not q.empty():
        try:
            msgs.append(q.get_nowait())
        except asyncio.QueueEmpty:
            break
    return msgs


# ═══════════════════════════════════════════════════════════════
# Test: emit_response → ws_out_queue — transition_speech
# ═══════════════════════════════════════════════════════════════


class TestEmitResponseWsOutput:
    """emit_response_node WS 输出内容校验（Phase 2-lite）。"""

    @pytest.fixture(autouse=True)
    def drain_before(self):
        _drain_queue(ws_out_queue)

    @pytest.mark.asyncio
    async def test_transition_speech_enqueues_tts_synthesize(self):
        """TC-WS1: transition_speech → ws_out_queue 含 tts.synthesize。"""
        state = {
            "pending_payload": {
                "transition_speech": {
                    "text": "今晚的歌都听完了，让我为你找一些更贴心的...",
                    "mood": "warm",
                    "theme": "今晚",
                }
            },
            "turn_count": 0,
            "last_error": None,
        }
        result = await emit_response_node(state)

        assert result["turn_count"] == 1
        msgs = _drain_queue(ws_out_queue)
        assert len(msgs) == 1

        tts_msgs = [m for m in msgs if m.get("type") == "tts" and m.get("subtype") == "synthesize"]
        assert len(tts_msgs) == 1
        assert tts_msgs[0]["payload"]["text"].startswith("今晚的歌都听完了")

    @pytest.mark.asyncio
    async def test_error_last_error_enqueues_error(self):
        """TC-WS2: last_error → ws_out_queue 含 error（无 subtype）。"""
        state = {
            "pending_payload": None,
            "turn_count": 5,
            "last_error": {"code": 2001, "message": "DeepSeek API timeout after 30s"},
        }
        result = await emit_response_node(state)

        assert result["turn_count"] == 6
        msgs = _drain_queue(ws_out_queue)
        error_msgs = [m for m in msgs if m.get("type") == "error"]
        assert len(error_msgs) == 1
        assert error_msgs[0]["payload"]["code"] == 2001
        assert "timeout" in error_msgs[0]["payload"]["msg"]

    @pytest.mark.asyncio
    async def test_error_with_msg_field(self):
        """TC-WS3: last_error 用 msg 字段（feedback_extractor 风格）也能正确推 error。"""
        state = {
            "pending_payload": None,
            "turn_count": 0,
            "last_error": {"code": 2002, "msg": "No song_id in trigger_event"},
        }
        await emit_response_node(state)
        msgs = _drain_queue(ws_out_queue)
        error_msgs = [m for m in msgs if m.get("type") == "error"]
        assert len(error_msgs) == 1
        assert error_msgs[0]["payload"]["code"] == 2002
        assert "song_id" in error_msgs[0]["payload"]["msg"]

    @pytest.mark.asyncio
    async def test_no_error_when_last_error_none(self):
        """TC-WS4: last_error=None 不推 error WS 消息。"""
        state = {
            "pending_payload": {"chat_reply": "Hello!"},
            "turn_count": 2,
            "last_error": None,
        }
        await emit_response_node(state)
        msgs = _drain_queue(ws_out_queue)
        error_msgs = [m for m in msgs if m.get("type") == "error"]
        assert len(error_msgs) == 0
        # chat.reply 正常推送
        chat_msgs = [m for m in msgs if m.get("type") == "chat"]
        assert len(chat_msgs) == 1

    @pytest.mark.asyncio
    async def test_both_pending_and_error(self):
        """TC-WS5: pending_payload 和 last_error 同时存在，两类消息都推。"""
        state = {
            "pending_payload": {
                "chat_reply": "推荐一首歌给你",
                "music_play": {
                    "song": {"id": "123", "name": "七里香"},
                    "play_url": "http://example.com/play",
                    "auto_play": True,
                },
            },
            "turn_count": 0,
            "last_error": {"code": 2002, "message": "search_songs failed"},
        }
        await emit_response_node(state)
        msgs = _drain_queue(ws_out_queue)

        chat_msgs = [m for m in msgs if m.get("type") == "chat"]
        music_msgs = [m for m in msgs if m.get("type") == "music" and m.get("subtype") == "play"]
        error_msgs = [m for m in msgs if m.get("type") == "error"]
        assert len(chat_msgs) == 1
        assert len(music_msgs) == 1
        assert len(error_msgs) == 1


# ═══════════════════════════════════════════════════════════════
# Test: ConnectionManager heartbeat / pong / stale
# ═══════════════════════════════════════════════════════════════


class TestConnectionManagerHeartbeat:
    """ConnectionManager 心跳跟踪 + stale disconnect。"""

    @pytest.mark.asyncio
    async def test_record_pong_prevents_stale(self):
        """TC-WS6: record_pong 更新后 disconnect_stale 不会断开。"""
        cm = ConnectionManager()

        fake_ws = AsyncMock()
        fake_ws.accept = AsyncMock()
        await cm.connect(fake_ws)
        assert cm.active_count == 1

        # 模拟 pong
        cm.record_pong(fake_ws)

        stale_count = await cm.disconnect_stale(timeout_s=0.1)
        assert stale_count == 0
        assert cm.active_count == 1

    @pytest.mark.asyncio
    async def test_no_pong_triggers_stale(self):
        """TC-WS7: 无 pong → disconnect_stale 断开连接。"""
        cm = ConnectionManager()

        fake_ws = AsyncMock()
        fake_ws.accept = AsyncMock()
        await cm.connect(fake_ws)
        assert cm.active_count == 1

        # 强制设为过去时间
        cm._last_pong[fake_ws] = 0.0

        stale_count = await cm.disconnect_stale(timeout_s=1.0)
        assert stale_count == 1
        assert cm.active_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        """TC-WS8: broadcast 发送失败自动移除连接。"""
        cm = ConnectionManager()

        broken_ws = AsyncMock()
        broken_ws.accept = AsyncMock()
        broken_ws.send_json = AsyncMock(side_effect=Exception("connection closed"))

        await cm.connect(broken_ws)
        assert cm.active_count == 1

        await cm.broadcast({"type": "heartbeat", "subtype": "ping"})
        assert cm.active_count == 0

    @pytest.mark.asyncio
    async def test_multiple_connections_broadcast(self):
        """TC-WS9: broadcast 正常发送给所有连接。"""
        cm = ConnectionManager()

        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await cm.connect(ws1)
        await cm.connect(ws2)
        assert cm.active_count == 2

        await cm.broadcast({"type": "test"})
        ws1.send_json.assert_awaited_once_with({"type": "test"})
        ws2.send_json.assert_awaited_once_with({"type": "test"})
