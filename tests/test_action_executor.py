"""Action Executor + TTSService 单元测试。

覆盖（4 测试）：
1. TTSService.synthesize 返回正确 schema
2. action type=tts_speak → payload 含 audio_url
3. action type=play_song → payload 含 play_url
4. 异常捕获 → last_error 记录 + 不阻塞

使用方法：
    cd dev
    python -m pytest tests/test_action_executor.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ═══════════════════════════════════════════════════════════════
# Test Case 1: TTSService.synthesize 返回正确 schema
# ═══════════════════════════════════════════════════════════════
class TestTTSServiceMock:
    """TTSService mock synthesize schema 验证。"""

    @pytest.mark.asyncio
    async def test_synthesize_returns_correct_schema(self):
        """TC-01: synthesize 返回 audio_url / duration_ms / provider。"""
        from agent.services.tts_service import TTSService

        svc = TTSService()
        result = await svc.synthesize("你好，欢迎收听今天的节目")

        assert "audio_url" in result, "缺少 audio_url"
        assert "duration_ms" in result, "缺少 duration_ms"
        assert "provider" in result, "缺少 provider"
        assert result["audio_url"].startswith("mock://"), \
            f"audio_url 应为 mock 前缀，实际: {result['audio_url']}"
        assert isinstance(result["duration_ms"], int), \
            f"duration_ms 应为 int，实际: {type(result['duration_ms'])}"
        assert result["provider"] == "xunfei_mock", \
            f"provider 应为 xunfei_mock，实际: {result['provider']}"
        assert result["duration_ms"] >= 1000, \
            f"duration_ms 应 >= 1000，实际: {result['duration_ms']}"

    @pytest.mark.asyncio
    async def test_synthesize_empty_text_returns_zero_duration(self):
        """TC-01b: 空文本 → duration_ms=0, audio_url=''。"""
        from agent.services.tts_service import TTSService

        svc = TTSService()
        result = await svc.synthesize("")

        assert result["audio_url"] == "", "空文本应返回空 audio_url"
        assert result["duration_ms"] == 0, "空文本应返回 duration_ms=0"

    @pytest.mark.asyncio
    async def test_synthesize_whitespace_text_returns_zero_duration(self):
        """TC-01c: 纯空白文本 → duration_ms=0, audio_url=''。"""
        from agent.services.tts_service import TTSService

        svc = TTSService()
        result = await svc.synthesize("   ")

        assert result["audio_url"] == "", "纯空白应返回空 audio_url"
        assert result["duration_ms"] == 0, "纯空白应返回 duration_ms=0"


# ═══════════════════════════════════════════════════════════════
# Test Case 2: action_executor tts_speak → payload 含 audio_url
# ═══════════════════════════════════════════════════════════════
class TestActionExecutorTTS:
    """action type=tts_speak → pending_payload 被 enrich。"""

    @pytest.mark.asyncio
    async def test_tts_speak_enriches_payload(self):
        """TC-02: tts_speak 执行后 pending_payload.transition_speech 含 audio_url。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {
                    "type": "tts_speak",
                    "params": {"text": "这是一段测试语音"},
                    "reason": "test",
                }
            ],
            "pending_payload": {
                "transition_speech": {
                    "text": "这是一段测试语音",
                    "source": "test",
                },
            },
        }

        result = await action_executor_node(state)

        assert "pending_payload" in result
        ts = result["pending_payload"].get("transition_speech", {})
        assert ts.get("audio_url", "").startswith("mock://"), \
            f"应含 mock audio_url，实际: {ts.get('audio_url')}"
        assert isinstance(ts.get("duration_ms"), int), \
            f"duration_ms 应为 int"
        assert ts.get("provider") == "xunfei_mock"
        # 原始字段不应丢失
        assert ts.get("text") == "这是一段测试语音"
        assert ts.get("source") == "test"
        # 不应有 last_error
        assert "last_error" not in result, "正常执行不应有 last_error"

    @pytest.mark.asyncio
    async def test_tts_speak_empty_text_skips(self):
        """TC-02b: tts_speak 空文本 → 安全跳过，不写 last_error。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {
                    "type": "tts_speak",
                    "params": {"text": ""},
                    "reason": "test_empty",
                }
            ],
            "pending_payload": {},
        }

        result = await action_executor_node(state)

        assert "last_error" not in result, "空文本不应产生 last_error"
        ts = result["pending_payload"].get("transition_speech", {})
        assert ts.get("audio_url") is None, "空文本不应有 audio_url"


# ═══════════════════════════════════════════════════════════════
# Test Case 3: action_executor play_song → payload 含 play_url
# ═══════════════════════════════════════════════════════════════
class TestActionExecutorPlay:
    """action type=play_song → pending_payload 被 enrich。"""

    @pytest.mark.asyncio
    async def test_play_song_enriches_payload(self):
        """TC-03: play_song 执行后 pending_payload.music_play 含 play_url。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {
                    "type": "play_song",
                    "params": {"song_id": "509781655", "auto_play": True},
                    "reason": "test",
                }
            ],
            "pending_payload": {
                "music_play": {
                    "song": {"song_id": "509781655", "name": "测试歌曲"},
                    "auto_play": True,
                },
            },
        }

        with patch(
            "agent.nodes.action_executor._music.get_play_url",
            new_callable=AsyncMock,
            return_value="https://example.com/play/509781655.mp3",
        ):
            result = await action_executor_node(state)

        assert "pending_payload" in result
        mp = result["pending_payload"].get("music_play", {})
        assert "api/proxy/audio?url=" in mp.get("play_url", ""), \
            f"play_url 应被代理到 /api/proxy/audio，实际: {mp.get('play_url')}"
        # 原始字段不应丢失
        assert mp.get("auto_play") is True
        assert mp["song"]["song_id"] == "509781655"
        # 不应有 last_error
        assert "last_error" not in result, "正常执行不应有 last_error"

    @pytest.mark.asyncio
    async def test_play_song_none_url_sets_last_error(self):
        """TC-03e: play_url 返回 None → last_error 记录。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {
                    "type": "play_song",
                    "params": {"song_id": "default_morning_001", "auto_play": True},
                    "reason": "test",
                }
            ],
            "pending_payload": {
                "music_play": {
                    "song": {"song_id": "default_morning_001", "name": "默认歌曲"},
                    "auto_play": True,
                },
            },
        }

        with patch(
            "agent.nodes.action_executor._music.get_play_url",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await action_executor_node(state)

        assert "last_error" in result, "play_url=None 应产生 last_error"
        assert result["last_error"]["code"] == "PLAY_URL_NOT_FOUND", \
            f"错误码应为 PLAY_URL_NOT_FOUND，实际: {result['last_error'].get('code')}"
        assert "pending_payload" in result

    @pytest.mark.asyncio
    async def test_play_song_empty_id_skips(self):
        """TC-03b: play_song 空 song_id → 安全跳过，不写 last_error。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {
                    "type": "play_song",
                    "params": {"song_id": ""},
                    "reason": "test_empty",
                }
            ],
            "pending_payload": {},
        }

        result = await action_executor_node(state)

        assert "last_error" not in result, "空 song_id 不应产生 last_error"
        mp = result["pending_payload"].get("music_play", {})
        assert mp.get("play_url") is None, "空 song_id 不应有 play_url"

    @pytest.mark.asyncio
    async def test_empty_actions_passthrough(self):
        """TC-03c: actions=[] → 透传原有 pending_payload。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [],
            "pending_payload": {"chat_reply": "你好"},
        }

        result = await action_executor_node(state)

        assert result["pending_payload"]["chat_reply"] == "你好"
        assert "last_error" not in result


# ═══════════════════════════════════════════════════════════════
# Test Case 4: 异常捕获 → last_error + 不阻塞 graph
# ═══════════════════════════════════════════════════════════════
class TestActionExecutorFailureDegrades:
    """异常时 last_error 记录 + graph 不中断。"""

    @pytest.mark.asyncio
    async def test_tts_failure_sets_last_error(self):
        """TC-04: TTS 抛异常 → last_error 记录 + pending_payload 仍返回。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {
                    "type": "tts_speak",
                    "params": {"text": "测试异常"},
                    "reason": "test",
                }
            ],
            "pending_payload": {
                "transition_speech": {"text": "测试异常"},
            },
        }

        with patch(
            "agent.nodes.action_executor._tts.synthesize",
            new_callable=AsyncMock,
            side_effect=RuntimeError("TTS API unavailable"),
        ):
            result = await action_executor_node(state)

        # last_error 应被记录
        assert "last_error" in result, "异常时应记录 last_error"
        assert result["last_error"]["code"] == "TTS_FAILED", \
            f"错误码应为 TTS_FAILED，实际: {result['last_error'].get('code')}"
        # pending_payload 也应返回（不阻塞）
        assert "pending_payload" in result, "异常时也应返回 pending_payload"
        assert result["pending_payload"]["transition_speech"]["text"] == "测试异常"

    @pytest.mark.asyncio
    async def test_play_song_failure_sets_last_error(self):
        """TC-04b: MusicService 抛异常 → last_error 记录 + 不阻塞。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {
                    "type": "play_song",
                    "params": {"song_id": "mock_err"},
                    "reason": "test",
                }
            ],
            "pending_payload": {
                "music_play": {"song": {"song_id": "mock_err"}},
            },
        }

        with patch(
            "agent.nodes.action_executor._music.get_play_url",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Music API timeout"),
        ):
            result = await action_executor_node(state)

        assert "last_error" in result
        assert result["last_error"]["code"] == "PLAY_FAILED"
        assert "pending_payload" in result

    @pytest.mark.asyncio
    async def test_unknown_action_skips_safely(self):
        """TC-04c: 未知 action type → 安全跳过，不影响已有 payload。"""
        from agent.nodes.action_executor import action_executor_node

        state = {
            "actions": [
                {"type": "unknown_action", "params": {}, "reason": "test"},
            ],
            "pending_payload": {"chat_reply": "保持原样"},
        }

        result = await action_executor_node(state)

        assert "last_error" not in result, "未知 type 不应有 last_error"
        assert result["pending_payload"]["chat_reply"] == "保持原样"

    @pytest.mark.asyncio
    async def test_actions_none_is_safe(self):
        """TC-04d: actions=None → 安全返回空 payload。"""
        from agent.nodes.action_executor import action_executor_node

        state = {"pending_payload": {}}
        result = await action_executor_node(state)

        assert "last_error" not in result


# ═══════════════════════════════════════════════════════════════
# Test Case 5: Graph 集成 — action_executor 在链路中存在
# ═══════════════════════════════════════════════════════════════
class TestGraphHasActionExecutor:
    """Graph 编译后含 action_executor 节点。"""

    def test_graph_includes_action_executor(self):
        """TC-05: build_graph() 编译成功，含 action_executor 节点。"""
        from agent.graph import build_graph

        graph = build_graph()
        assert graph is not None, "Graph 应编译成功"

        # 通过 get_graph() 检查节点列表
        g = graph.get_graph()
        node_names = {n.id if hasattr(n, 'id') else str(n) for n in g.nodes}

        assert any("action_executor" in n for n in node_names), \
            f"graph 应含 action_executor 节点，实际节点: {node_names}"
