"""LLMService 单元测试 — call_json 返回值协议 + 重试 + 错误降级。

测试覆盖：
  1. call_json 成功返回（mock API）
  2. 第一次 JSON 解析失败 → 重试成功
  3. 两次 JSON 解析都失败 → 返回 error
  4. API 调用异常 → 返回 error
  5. 未 configure 调用 → raise RuntimeError
  6. _parse_json 静态方法边界

不使用 pytest-mock（用 unittest.mock 避免额外依赖）。
"""

import json
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.services.llm_service import LLMService


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def svc():
    """返回已 configure 的 LLMService，client 会惰性初始化。"""
    s = LLMService()
    s.configure(api_key="sk-test", base_url="https://test.api/v1", model="test-model")
    return s


# ═══════════════════════════════════════════════════════════════
# Test 1: 成功路径
# ═══════════════════════════════════════════════════════════════
class TestCallJsonSuccess:
    """call_json 成功返回 {"ok": True, "data": {...}}。"""

    @pytest.mark.asyncio
    async def test_returns_ok_with_data(self, svc):
        """Mock API 返回合法 JSON → ok=True + data。"""
        expected = {"program_decision": {}, "playlist_decision": {"action": "keep"}}
        svc._client = AsyncMock()
        svc._client.chat.completions.create = AsyncMock(
            return_value=_mock_api_response(json.dumps(expected))
        )

        result = await svc.call_json("test prompt")

        assert result["ok"] is True
        assert result["data"] == expected

    @pytest.mark.asyncio
    async def test_returns_ok_with_complex_data(self, svc):
        """复杂嵌套 JSON 也可正常解析。"""
        expected = {
            "program_decision": {"today_theme": "放松", "current_segment": "music"},
            "playlist_decision": {"action": "add", "songs": [{"song_id": "1", "name": "A"}], "reason": "test"},
            "dialogue_decision": {"should_speak": True, "text": "你好", "style": "warm"},
            "tool_calls": [],
        }
        svc._client = AsyncMock()
        svc._client.chat.completions.create = AsyncMock(
            return_value=_mock_api_response(json.dumps(expected))
        )

        result = await svc.call_json("test prompt")

        assert result["ok"] is True
        assert result["data"]["dialogue_decision"]["text"] == "你好"


# ═══════════════════════════════════════════════════════════════
# Test 2: 重试逻辑
# ═══════════════════════════════════════════════════════════════
class TestRetryLogic:
    """第一次 JSON 解析失败 → 重试成功。"""

    @pytest.mark.asyncio
    async def test_retry_on_json_parse_failure(self, svc):
        """第一次返回非法 JSON → 重试一次 → 第二次合法。"""
        expected = {"key": "value"}
        mock_create = AsyncMock(side_effect=[
            _mock_api_response("not valid json {"),
            _mock_api_response(json.dumps(expected)),
        ])
        svc._client = AsyncMock()
        svc._client.chat.completions.create = mock_create

        result = await svc.call_json("test prompt")

        assert result["ok"] is True
        assert result["data"] == expected
        # 验证调用了 2 次（第一次失败 + 重试）
        assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_prompt_contains_reminder(self, svc):
        """重试时 prompt 追加了 retry 提示。"""
        expected = {"ok": True}
        calls = []

        async def side_effect(model, messages, response_format, temperature):
            calls.append(messages[0]["content"])
            if len(calls) == 1:
                return _mock_api_response("invalid")
            return _mock_api_response(json.dumps(expected))

        svc._client = AsyncMock()
        svc._client.chat.completions.create = AsyncMock(side_effect=side_effect)

        result = await svc.call_json("original prompt")

        assert result["ok"] is True
        # 第一次：原始 prompt
        assert "original prompt" in calls[0]
        # 第二次：原始 prompt + retry 后缀
        assert len(calls) == 2
        assert "Return JSON only" in calls[1]

    @pytest.mark.asyncio
    async def test_double_failure_returns_error(self, svc):
        """两次都返回非法 JSON → ok=False + 错误码 LLM_JSON_PARSE_FAILED。"""
        svc._client = AsyncMock()
        svc._client.chat.completions.create = AsyncMock(
            return_value=_mock_api_response("not json")
        )

        result = await svc.call_json("test prompt")

        assert result["ok"] is False
        assert result["error"]["code"] == "LLM_JSON_PARSE_FAILED"

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, svc):
        """API 返回空字符串 → _call_api 返回 ok=True + content=""
        → _parse_json 失败 → 重试后仍失败 → LLM_JSON_PARSE_FAILED。"""
        svc._client = AsyncMock()
        svc._client.chat.completions.create = AsyncMock(
            return_value=_mock_api_response("")
        )

        result = await svc.call_json("test prompt")

        assert result["ok"] is False
        # 空字符串 content="" → _parse_json 返回 error → 重试 → 仍为空 → JSON parse failed
        assert result["error"]["code"] == "LLM_JSON_PARSE_FAILED"


# ═══════════════════════════════════════════════════════════════
# Test 3: API 异常
# ═══════════════════════════════════════════════════════════════
class TestApiError:
    """API 调用异常 → 结构化 error，不 raise。"""

    @pytest.mark.asyncio
    async def test_api_exception_returns_error(self, svc):
        """API 抛出异常 → ok=False + LLM_API_ERROR（异常类型 + 信息被保留）。"""
        svc._client = AsyncMock()
        svc._client.chat.completions.create = AsyncMock(
            side_effect=ConnectionError("API unreachable")
        )

        result = await svc.call_json("test prompt")

        assert result["ok"] is False
        assert result["error"]["code"] == "LLM_API_ERROR"
        assert "ConnectionError: API unreachable" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_api_exception_no_retry(self, svc):
        """API 异常不重试（只对 JSON 解析失败重试）。"""
        mock_create = AsyncMock(side_effect=TimeoutError("timeout"))
        svc._client = AsyncMock()
        svc._client.chat.completions.create = mock_create

        result = await svc.call_json("test prompt")

        assert result["ok"] is False
        # API 异常不应该重试，只调一次
        assert mock_create.call_count == 1


# ═══════════════════════════════════════════════════════════════
# Test 4: 配置检查
# ═══════════════════════════════════════════════════════════════
class TestConfigure:
    """configure / 未配置检查。"""

    def test_not_configured_raises(self):
        """未 configure 就 call_json → RuntimeError。"""
        svc = LLMService()
        with pytest.raises(RuntimeError, match="not configured"):
            svc._ensure_client()

    def test_configured_does_not_raise(self):
        """configure 后 _ensure_client 不抛。"""
        svc = LLMService()
        svc.configure(api_key="sk-test")
        svc._ensure_client()
        assert svc._client is not None


# ═══════════════════════════════════════════════════════════════
# Test 5: _parse_json 边界
# ═══════════════════════════════════════════════════════════════
class TestParseJson:
    """_parse_json 静态方法边界测试。"""

    def test_valid_json(self):
        """合法 JSON → ok=True。"""
        result = LLMService._parse_json('{"a": 1}')
        assert result["ok"] is True
        assert result["data"] == {"a": 1}

    def test_invalid_json(self):
        """非法 JSON → ok=False。"""
        result = LLMService._parse_json("{invalid}")
        assert result["ok"] is False
        assert "LLM_JSON_PARSE_FAILED" in result["error"]["code"]

    def test_empty_string(self):
        result = LLMService._parse_json("")
        assert result["ok"] is False

    def test_whitespace_only(self):
        result = LLMService._parse_json("   ")
        assert result["ok"] is False

    def test_non_dict_json(self):
        """JSON 数组 → ok=False（只接受 dict）。"""
        result = LLMService._parse_json("[1, 2, 3]")
        assert result["ok"] is False

    def test_null_json(self):
        result = LLMService._parse_json("null")
        assert result["ok"] is False


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _mock_api_response(content: str):
    """构造 mock OpenAI API response。"""
    import types
    choice = types.SimpleNamespace()
    choice.message = types.SimpleNamespace()
    choice.message.content = content
    response = types.SimpleNamespace()
    response.choices = [choice]
    return response
