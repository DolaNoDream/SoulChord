"""DJ Planner 4 prompt 模式测试 — conversation / timer / replan / Tool Loop 路由。

★ v0.6 H20 加强：DJ Planner 统一负责所有节目策划事件
★ 输出 schema 统一：program_decision / playlist_decision / dialogue_decision / tool_calls
★ 测试重点：schema 验证 + routing，不测试 prompt 字符串细节
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.shared.enums import TriggerType


# ═══════════════════════════════════════════════════════════════
# Test 1: CONVERSATION → llm_decision schema
# ═══════════════════════════════════════════════════════════════
class TestConversationDecision:
    """CONVERSATION 事件的 4 块输出 schema 验证。"""

    @pytest.mark.asyncio
    async def test_conversation_returns_llm_decision(self):
        """conversation trigger → llm_decision 4 块 schema。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "conversation",
            "runtime_snapshot": {},
            "user": {"nickname": "测试用户"},
            "environment": {"day_period": "evening"},
            "program": {"today_theme": "测试主题"},
            "playlist": {},
            "player_mirror": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)

        assert result.get("init_plan") is None
        decision = result.get("llm_decision")
        assert decision is not None, "conversation 应返回 llm_decision"

        # 验证 4 块 topology
        assert "program_decision" in decision, "缺少 program_decision"
        assert "playlist_decision" in decision, "缺少 playlist_decision"
        assert "dialogue_decision" in decision, "缺少 dialogue_decision"
        assert "tool_calls" in decision, "缺少 tool_calls"

        # program_decision 字段
        pd = decision["program_decision"]
        for key in ("today_theme", "current_segment", "program_mood",
                     "program_goal", "voice_style", "speech_rate", "speak_frequency"):
            assert key in pd, f"program_decision 缺少字段: {key}"

        # playlist_decision 字段
        pld = decision["playlist_decision"]
        assert "action" in pld
        assert pld["action"] in ("keep", "replace", "add", "append", "insert_now")
        assert "songs" in pld
        assert isinstance(pld["songs"], list)
        assert "reason" in pld

        # dialogue_decision 字段
        dd = decision["dialogue_decision"]
        assert "should_speak" in dd
        assert "text" in dd
        assert "style" in dd

        # tool_calls 是 list[{name, args}]
        assert isinstance(decision["tool_calls"], list)
        for tc in decision["tool_calls"]:
            assert "name" in tc
            assert "args" in tc

        # 路由：无 tool_calls → action_planner
        assert result.get("next_node") == "action_planner"
        assert result.get("pending_tool_calls") == []


# ═══════════════════════════════════════════════════════════════
# Test 2: TIMER → llm_decision schema + timer_type 传播
# ═══════════════════════════════════════════════════════════════
class TestTimerDecision:
    """TIMER 事件的简化 4 块输出。"""

    @pytest.mark.asyncio
    async def test_timer_returns_llm_decision(self):
        """timer_event → llm_decision，dialogue_decision.should_speak=False。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "timer_event",
            "trigger_event": {"timer_type": "playlist_health", "reason": "health check"},
            "runtime_snapshot": {},
            "program": {"today_theme": "测试"},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)

        assert result.get("init_plan") is None
        decision = result.get("llm_decision")
        assert decision is not None, "timer_event 应返回 llm_decision"

        # 相同 4 块 topology
        assert "program_decision" in decision
        assert "playlist_decision" in decision
        assert "dialogue_decision" in decision
        assert "tool_calls" in decision

        # timer 特定：默认不说话
        dd = decision["dialogue_decision"]
        assert dd["should_speak"] is False
        assert dd["text"] == ""

        # routing：无 tool_calls
        assert result.get("next_node") == "action_planner"

    @pytest.mark.asyncio
    async def test_timer_without_timer_type(self):
        """timer_event 无 timer_type 字段 → 默认 heartbeat，不抛异常。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "timer_event",
            "trigger_event": {},
            "runtime_snapshot": {},
            "program": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)
        assert result.get("llm_decision") is not None
        assert result.get("next_node") == "action_planner"


# ═══════════════════════════════════════════════════════════════
# Test 3: REPLAN → llm_decision + playlist_decision.action="replace"
# ═══════════════════════════════════════════════════════════════
class TestReplanDecision:
    """REPLAN 事件的 4 块输出（复用 CONVERSATION_PROMPT）。"""

    @pytest.mark.asyncio
    async def test_replan_returns_llm_decision(self):
        """replan_event → llm_decision，playlist 重建（action=replace + 10 songs）。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "replan_event",
            "trigger_event": {"reason": "queue_empty_after_song_finished"},
            "runtime_snapshot": {},
            "program": {"today_theme": "今日陪伴", "program_mood": "warm"},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)

        assert result.get("init_plan") is None
        decision = result.get("llm_decision")
        assert decision is not None, "replan_event 应返回 llm_decision"

        # 4 块 topology
        assert "program_decision" in decision
        assert "playlist_decision" in decision
        assert "dialogue_decision" in decision

        # REPLAN 特定：playlist_decision.action="replace" + songs 非空
        pld = decision["playlist_decision"]
        assert pld["action"] == "replace", "REPLAN 应重建 playlist"
        assert len(pld["songs"]) > 0, "REPLAN 应输出歌曲"

        # routing: 有歌曲但无 tool_calls → _ensure_tool_calls 注入 play_music → tool_dispatcher
        assert result.get("next_node") == "tool_dispatcher"

    @pytest.mark.asyncio
    async def test_replan_without_reason(self):
        """replan_event 无 reason → 默认 reason，不抛异常。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "replan_event",
            "trigger_event": {},
            "runtime_snapshot": {},
            "program": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)
        assert result.get("llm_decision") is not None
        # 有歌曲 → _ensure_tool_calls 注入 play_music → tool_dispatcher
        assert result.get("next_node") == "tool_dispatcher"


# ═══════════════════════════════════════════════════════════════
# Test 4: Tool Loop 路由 — pending_tool_calls 提取 + next_node
# ═══════════════════════════════════════════════════════════════
class TestToolLoopRouting:
    """_package_decision — tool_calls 提取 + Tool Loop 路由规则。"""

    def test_tool_calls_extracted_to_pending(self):
        """tool_calls 非空 → 提取为 pending_tool_calls[{name, args}]。"""
        from agent.nodes.dj_planner import _package_decision

        decision = {
            "program_decision": {},
            "playlist_decision": {"action": "keep", "songs": [], "reason": ""},
            "dialogue_decision": {"should_speak": False, "text": "", "style": "warm"},
            "tool_calls": [
                {"name": "get_environment_context", "args": {}},
                {"name": "query_user_preference", "args": {"category": "context"}},
            ],
        }
        state = {"tool_loop_count": 0, "tool_loop_max": 1}

        result = _package_decision(decision, state)

        assert len(result["pending_tool_calls"]) == 2
        assert result["pending_tool_calls"][0]["name"] == "get_environment_context"
        assert result["pending_tool_calls"][0]["args"] == {}
        assert result["pending_tool_calls"][1]["name"] == "query_user_preference"

    def test_tool_loop_routes_to_dispatcher(self):
        """pending_tool_calls 非空 AND count < max → next_node=tool_dispatcher。"""
        from agent.nodes.dj_planner import _package_decision

        decision = {
            "program_decision": {},
            "playlist_decision": {"action": "keep", "songs": [], "reason": ""},
            "dialogue_decision": {"should_speak": False, "text": "", "style": "warm"},
            "tool_calls": [{"name": "get_environment_context", "args": {}}],
        }

        # count=0 < max=1 → tool_dispatcher
        result = _package_decision(decision, {"tool_loop_count": 0, "tool_loop_max": 1})
        assert result["next_node"] == "tool_dispatcher"

    def test_tool_loop_skips_when_max_reached(self):
        """count >= max → 即使有 pending_tool_calls 也走 action_planner（强制收尾）。"""
        from agent.nodes.dj_planner import _package_decision

        decision = {
            "program_decision": {},
            "playlist_decision": {"action": "keep", "songs": [], "reason": ""},
            "dialogue_decision": {"should_speak": False, "text": "", "style": "warm"},
            "tool_calls": [{"name": "play_music", "args": {"song_id": "123"}}],
        }

        # count=1 >= max=1 → action_planner
        result = _package_decision(decision, {"tool_loop_count": 1, "tool_loop_max": 1})
        assert result["next_node"] == "action_planner"

    def test_no_tool_calls_routes_to_action_planner(self):
        """tool_calls 为空 → next_node=action_planner。"""
        from agent.nodes.dj_planner import _package_decision

        decision = {
            "program_decision": {},
            "playlist_decision": {"action": "keep", "songs": [], "reason": ""},
            "dialogue_decision": {"should_speak": False, "text": "", "style": "warm"},
            "tool_calls": [],
        }
        result = _package_decision(decision, {"tool_loop_count": 0, "tool_loop_max": 1})
        assert result["pending_tool_calls"] == []
        assert result["next_node"] == "action_planner"


# ═══════════════════════════════════════════════════════════════
# Test 5: Prompt formatter context dict 解耦
# ═══════════════════════════════════════════════════════════════
class TestPromptContextDict:
    """format_conversation_prompt / format_timer_prompt 接受 context dict。"""

    def test_conversation_formatter_accepts_plain_dict(self):
        """format_conversation_prompt 接受普通 dict（无 AgentState 引用）。"""
        from agent.prompts.conversation_prompt import format_conversation_prompt

        context = {
            "trigger_type": "conversation",
            "user": {"nickname": "测试", "music_profile": "流行"},
            "environment": {"day_period": "evening"},
            "program": {"today_theme": "陪伴"},
            "playlist": {},
            "player_mirror": {},
            "runtime_snapshot": {},
        }
        prompt = format_conversation_prompt(context)
        assert isinstance(prompt, str)
        assert len(prompt) > 100, "prompt 不应为空"
        assert "CONVERSATION" in prompt, "应包含 mode 标记"

    def test_conversation_formatter_replan_reason(self):
        """replan_reason 非空 → prompt 含 REPLAN 标记 + reason。"""
        from agent.prompts.conversation_prompt import format_conversation_prompt

        context = {
            "trigger_type": "replan_event",
            "user": {},
            "environment": {},
            "program": {"today_theme": "陪伴"},
            "playlist": {},
            "player_mirror": {},
            "runtime_snapshot": {},
        }
        prompt = format_conversation_prompt(context, replan_reason="播放列表已空")
        assert "REPLAN" in prompt
        assert "播放列表已空" in prompt

    def test_timer_formatter_accepts_plain_dict(self):
        """format_timer_prompt 接受普通 dict。"""
        from agent.prompts.timer_prompt import format_timer_prompt

        context = {
            "timer_type": "playlist_health",
            "program": {"today_theme": "陪伴"},
            "player_mirror": {},
            "runtime_snapshot": {},
        }
        prompt = format_timer_prompt(context)
        assert isinstance(prompt, str)
        assert "playlist_health" in prompt

    def test_timer_formatter_unknown_type(self):
        """未知 timer_type → 不抛异常。"""
        from agent.prompts.timer_prompt import format_timer_prompt

        context = {
            "timer_type": "unknown_type",
            "program": {},
            "player_mirror": {},
            "runtime_snapshot": {},
        }
        prompt = format_timer_prompt(context)
        assert isinstance(prompt, str)

    def test_empty_context_does_not_crash(self):
        """空 context dict → 不抛异常（各字段给默认值）。"""
        from agent.prompts.conversation_prompt import format_conversation_prompt

        prompt = format_conversation_prompt({})
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ═══════════════════════════════════════════════════════════════
# Test 6: LLMService 注入路径 — 有 __refs__["llm_service"]
# ═══════════════════════════════════════════════════════════════
class TestLLMServiceIntegration:
    """LLMService 经 __refs__ 注入 → dj_planner 使用 LLM 路径。

    不调真实 DeepSeek API，mock LLMService.call_json 返回值。
    使用 unittest.mock（不依赖 pytest-mock）。
    """

    @staticmethod
    def _make_llm_mock(return_data: dict):
        """构造 mock LLMService，call_json 返回成功。"""
        from unittest.mock import AsyncMock
        mock_svc = AsyncMock()
        mock_svc.call_json = AsyncMock(return_value={
            "ok": True,
            "data": return_data,
        })
        return mock_svc

    @staticmethod
    def _make_llm_error(code: str = "LLM_JSON_PARSE_FAILED", message: str = "test error"):
        """构造 mock LLMService，call_json 返回失败。"""
        from unittest.mock import AsyncMock
        mock_svc = AsyncMock()
        mock_svc.call_json = AsyncMock(return_value={
            "ok": False,
            "error": {"code": code, "message": message},
        })
        return mock_svc

    # ── 6a: Conversation + LLMService ──

    @pytest.mark.asyncio
    async def test_conversation_calls_llm_when_in_refs(self):
        """有 __refs__["llm_service"] → 调 call_json，不调 mock。"""
        from agent.nodes.dj_planner import dj_planner_node

        llm_data = {
            "program_decision": {"today_theme": "LLM主题", "current_segment": "music",
                                 "program_mood": "warm", "program_goal": None,
                                 "voice_style": None, "speech_rate": None, "speak_frequency": None},
            "playlist_decision": {"action": "keep", "songs": [], "reason": "LLM决策"},
            "dialogue_decision": {"should_speak": True, "text": "LLM生成回复", "style": "warm"},
            "tool_calls": [],
        }
        mock_svc = self._make_llm_mock(llm_data)

        state = {
            "trigger_type": "conversation",
            "__refs__": {"llm_service": mock_svc},
            "runtime_snapshot": {},
            "user": {},
            "environment": {},
            "program": {},
            "playlist": {},
            "player_mirror": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)

        # LLM 被调用
        mock_svc.call_json.assert_awaited_once()
        # LLM 返回的数据被正确传递
        assert result["llm_decision"]["program_decision"]["today_theme"] == "LLM主题"
        assert result["llm_decision"]["dialogue_decision"]["text"] == "LLM生成回复"
        # 路由正常
        assert result["next_node"] == "action_planner"

    # ── 6b: Conversation + LLMService + Tool Call ──

    @pytest.mark.asyncio
    async def test_llm_returns_tool_calls_tool_loop_preserved(self):
        """LLM 返回 tool_calls → Tool Loop 路由不受影响（关键风险测试）。"""
        from agent.nodes.dj_planner import dj_planner_node

        llm_data = {
            "program_decision": {},
            "playlist_decision": {"action": "keep", "songs": [], "reason": ""},
            "dialogue_decision": {"should_speak": False, "text": "", "style": "warm"},
            "tool_calls": [
                {"name": "get_environment_context", "args": {}},
                {"name": "query_user_preference", "args": {"category": "context"}},
            ],
        }
        mock_svc = self._make_llm_mock(llm_data)

        state = {
            "trigger_type": "conversation",
            "__refs__": {"llm_service": mock_svc},
            "runtime_snapshot": {},
            "user": {},
            "environment": {},
            "program": {},
            "playlist": {},
            "player_mirror": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)

        # Tool Loop: count=0 < max=1 → tool_dispatcher
        assert result["next_node"] == "tool_dispatcher"
        assert len(result["pending_tool_calls"]) == 2
        assert result["pending_tool_calls"][0]["name"] == "get_environment_context"

    # ── 6c: Conversation + LLMService error → last_error ──

    @pytest.mark.asyncio
    async def test_llm_error_sets_last_error(self):
        """LLM 返回 ok=False → last_error 写入 state，路由到 action_planner。"""
        from agent.nodes.dj_planner import dj_planner_node

        mock_svc = self._make_llm_error(code="LLM_API_ERROR", message="API unreachable")

        state = {
            "trigger_type": "conversation",
            "__refs__": {"llm_service": mock_svc},
            "runtime_snapshot": {},
            "user": {},
            "environment": {},
            "program": {},
            "playlist": {},
            "player_mirror": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)

        # last_error 写入
        assert result["last_error"] is not None
        assert result["last_error"]["code"] == "LLM_API_ERROR"
        # llm_decision 为 None（没有有效决策）
        assert result["llm_decision"] is None
        # 路由到 action_planner（降级路径）
        assert result["next_node"] == "action_planner"

    # ── 6d: Init + LLMService ──

    @pytest.mark.asyncio
    async def test_init_calls_llm_when_in_refs(self):
        """system_init + __refs__ → LLM 生成 init_plan。"""
        from agent.nodes.dj_planner import dj_planner_node

        llm_plan = {
            "program_state": {"today_theme": "LLM初始化主题", "current_segment": "intro",
                              "program_mood": "warm", "program_goal": "LLM目标"},
            "initial_playlist": [{"name": "江南", "artist": "林俊杰", "scene_match": "default"}],
            "welcome_text": "LLM 欢迎语",
        }
        mock_svc = self._make_llm_mock(llm_plan)

        state = {
            "trigger_type": "system_init",
            "__refs__": {"llm_service": mock_svc},
            "runtime_snapshot": {},
            "init_mode": "first_init",
            "user": {},
            "environment": {},
            "program": {},
        }

        result = await dj_planner_node(state)

        mock_svc.call_json.assert_awaited_once()
        assert result["init_plan"]["program_state"]["today_theme"] == "LLM初始化主题"
        assert result["init_plan"]["welcome_text"] == "LLM 欢迎语"
        # ★ v9.1: INIT 注入 play_music 工具调用，路由到 tool_dispatcher
        assert result["next_node"] == "tool_dispatcher", "INIT + LLM 应走 tool_dispatcher"
        assert len(result["pending_tool_calls"]) == 1, "应注入 1 个 play_music 工具调用"
        assert result["pending_tool_calls"][0]["name"] == "play_music"

    # ── 6e: Timer + LLMService ──

    @pytest.mark.asyncio
    async def test_timer_calls_llm_when_in_refs(self):
        """timer_event + __refs__ → LLM 路径。"""
        from agent.nodes.dj_planner import dj_planner_node

        llm_data = {
            "program_decision": {},
            "playlist_decision": {"action": "keep", "songs": [], "reason": "LLM timer check"},
            "dialogue_decision": {"should_speak": False, "text": "", "style": "warm"},
            "tool_calls": [],
        }
        mock_svc = self._make_llm_mock(llm_data)

        state = {
            "trigger_type": "timer_event",
            "trigger_event": {"timer_type": "playlist_health"},
            "__refs__": {"llm_service": mock_svc},
            "runtime_snapshot": {},
            "program": {"today_theme": "test"},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)
        mock_svc.call_json.assert_awaited_once()
        assert result["llm_decision"]["playlist_decision"]["reason"] == "LLM timer check"
        assert result["next_node"] == "action_planner"

    # ── 6f: REPLAN + LLMService ──

    @pytest.mark.asyncio
    async def test_replan_calls_llm_when_in_refs(self):
        """replan_event + __refs__ → LLM 路径。"""
        from agent.nodes.dj_planner import dj_planner_node

        llm_data = {
            "program_decision": {"today_theme": "LLM REPLAN"},
            "playlist_decision": {
                "action": "replace",
                "songs": [{"song_id": "r1", "name": "REPLAN Song", "artist": "LLM", "scene_match": "default"}],
                "reason": "LLM replan",
            },
            "dialogue_decision": {"should_speak": False, "text": "", "style": "warm"},
            "tool_calls": [],
        }
        mock_svc = self._make_llm_mock(llm_data)

        state = {
            "trigger_type": "replan_event",
            "trigger_event": {"reason": "queue_empty"},
            "__refs__": {"llm_service": mock_svc},
            "runtime_snapshot": {},
            "program": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)
        mock_svc.call_json.assert_awaited_once()
        assert result["llm_decision"]["playlist_decision"]["action"] == "replace"
        assert len(result["llm_decision"]["playlist_decision"]["songs"]) == 1
        # _ensure_tool_calls 注入了 play_music → 走 tool_dispatcher
        assert result["next_node"] == "tool_dispatcher"

    # ── 6g: init LLM error → last_error ──

    @pytest.mark.asyncio
    async def test_init_llm_error_sets_last_error(self):
        """system_init + __refs__ LLM 失败 → last_error + 路由到 action_planner。"""
        from agent.nodes.dj_planner import dj_planner_node

        mock_svc = self._make_llm_error(code="LLM_API_ERROR", message="init failed")

        state = {
            "trigger_type": "system_init",
            "__refs__": {"llm_service": mock_svc},
            "runtime_snapshot": {},
            "init_mode": "first_init",
            "user": {},
            "environment": {},
            "program": {},
        }

        result = await dj_planner_node(state)
        assert result["last_error"]["code"] == "LLM_API_ERROR"
        assert result["init_plan"] is None
        assert result["next_node"] == "action_planner"

    # ── 6h: 无 __refs__ → mock fallback（不调 LLM） ──

    @pytest.mark.asyncio
    async def test_no_refs_falls_back_to_mock(self):
        """无 __refs__ → _get_llm_service 返回 None，走 mock 路径（向后兼容）。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "conversation",
            "runtime_snapshot": {},
            "user": {},
            "environment": {},
            "program": {},
            "playlist": {},
            "player_mirror": {},
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await dj_planner_node(state)
        # mock 路径：有 llm_decision，tool_calls 为空
        assert result["llm_decision"] is not None
        assert result["pending_tool_calls"] == []
        assert result["next_node"] == "action_planner"


# ═══════════════════════════════════════════════════════════════
# Test 8: _is_fake_song_id 校验
# ═══════════════════════════════════════════════════════════════
class TestIsFakeSongId:
    """_is_fake_song_id song_id 虚假 ID 检测。"""

    def test_real_numeric_song_id(self):
        """纯数字 song_id → 不视为虚假。"""
        from agent.nodes.action_planner import _is_fake_song_id
        assert _is_fake_song_id("509781655") is False

    def test_default_prefix_is_fake(self):
        """default_ 前缀 → 虚假。"""
        from agent.nodes.action_planner import _is_fake_song_id
        assert _is_fake_song_id("default_morning_001") is True

    def test_mock_prefix_is_fake(self):
        """mock_ 前缀 → 虚假。"""
        from agent.nodes.action_planner import _is_fake_song_id
        assert _is_fake_song_id("mock_song_001") is True

    def test_non_numeric_string_is_fake(self):
        """非纯数字字母组合（LLM 编造）→ 虚假。"""
        from agent.nodes.action_planner import _is_fake_song_id
        assert _is_fake_song_id("abc123xyz") is True

    def test_empty_string_is_fake(self):
        """空字符串 → 虚假。"""
        from agent.nodes.action_planner import _is_fake_song_id
        assert _is_fake_song_id("") is True


# ═══════════════════════════════════════════════════════════════
# Test: _resolve_song_from_tools — name/artist → real song_id
# ═══════════════════════════════════════════════════════════════


class TestResolveSongFromTools:
    """_resolve_song_from_tools 按 name+artist 匹配搜索结果的真实 song_id。"""

    def _make_tool_msg(self, songs: list[dict], query: str = "test") -> list:
        """Helper: 构造单条 play_music 工具消息。"""
        return [{"name": "play_music", "result": {"songs": songs, "query": query, "count": len(songs)}}]

    def test_exact_match(self):
        """精确 name+artist 匹配 → 返回对应歌曲。"""
        from agent.nodes.action_planner import _resolve_song_from_tools

        songs = [
            {"id": "108914", "name": "江南", "artists": [{"id": "", "name": "林俊杰"}]},
            {"id": "25642214", "name": "爱错(Live)", "artists": [{"id": "", "name": "王力宏"}]},
        ]
        msgs = self._make_tool_msg(songs)
        result = _resolve_song_from_tools("江南", "林俊杰", msgs)
        assert result is not None
        assert result["id"] == "108914"
        assert result["name"] == "江南"

    def test_fuzzy_name_match(self):
        """name 子串匹配 → 返回对应歌曲。"""
        from agent.nodes.action_planner import _resolve_song_from_tools

        songs = [
            {"id": "4336330", "name": "Here Comes The Sun", "artists": [{"id": "", "name": "The Beatles"}]},
        ]
        msgs = self._make_tool_msg(songs)
        # "here comes" 是 "Here Comes The Sun" 的子串
        result = _resolve_song_from_tools("here comes", "Beatles", msgs)
        assert result is not None
        assert result["id"] == "4336330"

    def test_multiple_results_artist_disambiguation(self):
        """多个搜索结果，匹配正确 artist → 返回正确版本。"""
        from agent.nodes.action_planner import _resolve_song_from_tools

        songs = [
            {"id": "111111", "name": "晴天", "artists": [{"id": "", "name": "Unknown Singer"}]},
            {"id": "3339230677", "name": "晴天", "artists": [{"id": "", "name": "周杰伦"}]},
        ]
        msgs = self._make_tool_msg(songs)
        # 只匹配 name 不匹配 artist 时返回第一首（search order）
        # 但 name+artist 都匹配应返回第二首
        result = _resolve_song_from_tools("晴天", "周杰伦", msgs)
        assert result is not None
        assert result["id"] == "3339230677"

    def test_no_match_returns_none(self):
        """完全不匹配 → 返回 None。"""
        from agent.nodes.action_planner import _resolve_song_from_tools

        songs = [
            {"id": "108914", "name": "江南", "artists": [{"id": "", "name": "林俊杰"}]},
        ]
        msgs = self._make_tool_msg(songs)
        result = _resolve_song_from_tools("七里香", "周杰伦", msgs)
        assert result is None

    def test_empty_tool_messages_returns_none(self):
        """无 tool_messages → 返回 None。"""
        from agent.nodes.action_planner import _resolve_song_from_tools

        result = _resolve_song_from_tools("江南", "林俊杰", [])
        assert result is None

    def test_non_play_music_tools_ignored(self):
        """非 play_music 工具消息被忽略。"""
        from agent.nodes.action_planner import _resolve_song_from_tools

        msgs = [
            {"name": "get_environment_context", "result": {"weather": "晴"}},
            {"name": "play_music", "result": {"songs": [{"id": "108914", "name": "江南", "artists": [{"name": "林俊杰"}]}]}},
        ]
        result = _resolve_song_from_tools("江南", "林俊杰", msgs)
        assert result is not None
        assert result["id"] == "108914"

    def test_empty_name_and_artist(self):
        """name 和 artist 都为空 → 返回 None。"""
        from agent.nodes.action_planner import _resolve_song_from_tools

        result = _resolve_song_from_tools("", "", [])
        assert result is None


# ═══════════════════════════════════════════════════════════════
# Test: _match_fallback_by_name_artist — 硬编码 fallback 匹配
# ═══════════════════════════════════════════════════════════════


class TestMatchFallbackByNameArtist:
    """_match_fallback_by_name_artist 匹配 _REAL_FALLBACK_SONGS。"""

    def test_match_existing_song(self):
        """匹配 fallback 列表中的歌曲 → 返回带 song_id 的 dict。"""
        from agent.nodes.action_planner import _match_fallback_by_name_artist

        result = _match_fallback_by_name_artist("江南", "林俊杰")
        assert result is not None
        assert result["song_id"] == "108914"
        assert result["name"] == "江南"

    def test_fuzzy_match_scene(self):
        """子串匹配 → 也能匹配。"""
        from agent.nodes.action_planner import _match_fallback_by_name_artist

        result = _match_fallback_by_name_artist("here comes", "beatles")
        assert result is not None
        assert result["song_id"] == "4336330"

    def test_no_match_returns_none(self):
        """fallback 列表中不存在的歌曲 → 返回 None。"""
        from agent.nodes.action_planner import _match_fallback_by_name_artist

        result = _match_fallback_by_name_artist("不存在的歌", "无人歌手")
        assert result is None

    def test_empty_input_returns_none(self):
        """name 和 artist 都为空 → 返回 None。仅 name 不为空时按 name 匹配。"""
        from agent.nodes.action_planner import _match_fallback_by_name_artist

        assert _match_fallback_by_name_artist("", "") is None
        # 有 name 无 artist → 按 name 匹配（允许）
        result = _match_fallback_by_name_artist("江南", "")
        assert result is not None
        assert result["song_id"] == "108914"


# ═══════════════════════════════════════════════════════════════
# Test: playlist_queue 不混入 fallback
# ═══════════════════════════════════════════════════════════════


class TestPlaylistQueueSearchOnly:
    """_handle_llm_decision 的 playlist_queue 只应包含 source="search" 的歌曲。"""

    @pytest.mark.asyncio
    async def test_queue_contains_search_results_only(self):
        """LLM 输出 + 有搜索结果 → queue 只包含搜索歌曲，无 fallback。"""
        from unittest.mock import patch
        from agent.nodes.action_planner import action_planner_node

        tool_msgs = [{
            "name": "play_music",
            "result": {
                "songs": [
                    {"id": "1001", "name": "Song A", "artists": [{"name": "Artist A"}]},
                    {"id": "1002", "name": "Song B", "artists": [{"name": "Artist B"}]},
                    {"id": "1003", "name": "Song C", "artists": [{"name": "Artist C"}]},
                    {"id": "1004", "name": "Song D", "artists": [{"name": "Artist D"}]},
                    {"id": "1005", "name": "Song E", "artists": [{"name": "Artist E"}]},
                ],
                "query": "test", "count": 5,
            },
        }]

        state = {
            "trigger_type": "replan_event",
            "trigger_event": {"reason": "low_watermark:3"},
            "runtime_snapshot": {"playlist_queue": []},
            "dependencies": {
                "runtime_dj_state": {
                    "playlist_queue": [],
                },
            },
            "__refs__": {},
            "actions": [],
            "tool_messages": tool_msgs,
            "llm_decision": {
                "playlist_decision": {
                    "action": "replace",
                    "songs": [{"name": "Song A", "artist": "Artist A"}],
                    "reason": "test",
                },
                "dialogue_decision": {"should_speak": False, "text": ""},
            },
            "tool_loop_count": 0,
            "tool_loop_max": 2,
        }

        with patch("agent.nodes.action_planner.state_manager.player.update_player_event",
                    return_value=None):
            result = await action_planner_node(state)

        # 第一首歌被播放（Song A）
        assert result["should_play_music"] is True
        assert result["actions"][0]["params"]["song_id"] == "1001"

        # 验证 playlist_queue 只包含 search 结果（不含 fallback 歌曲）
        rds = state["dependencies"]["runtime_dj_state"]
        queue = rds.get("playlist_queue", [])
        # Song A 是第一首，被排除；剩下 Song B/C/D/E 在队列
        assert len(queue) == 4, f"预期 4 首搜索歌曲，实际 {len(queue)}"
        for song in queue:
            assert song["source"] == "search", f"song_id={song['song_id']} 的 source 应为 search"

    @pytest.mark.asyncio
    async def test_queue_update_strategy_replan_appends(self):
        """REPLAN 事件 → queue_update="append"，新歌曲追加到队列尾部。"""
        from unittest.mock import patch
        from agent.nodes.action_planner import action_planner_node

        tool_msgs = [{
            "name": "play_music",
            "result": {
                "songs": [
                    {"id": "2001", "name": "New A", "artists": [{"name": "N A"}]},
                    {"id": "2002", "name": "New B", "artists": [{"name": "N B"}]},
                ],
                "query": "new", "count": 2,
            },
        }]

        state = {
            "trigger_type": "replan_event",
            "trigger_event": {"reason": "queue_empty_after_song_finished"},
            "runtime_snapshot": {"playlist_queue": []},
            "dependencies": {
                "runtime_dj_state": {
                    # 已有旧队列
                    "playlist_queue": [
                        {"song_id": "old1", "source": "search"},
                        {"song_id": "old2", "source": "search"},
                    ],
                },
            },
            "__refs__": {},
            "actions": [],
            "tool_messages": tool_msgs,
            "llm_decision": {
                "playlist_decision": {
                    "action": "append",
                    "songs": [{"name": "New A", "artist": "N A"}],
                    "reason": "replenish",
                },
                "dialogue_decision": {"should_speak": False, "text": ""},
            },
            "tool_loop_count": 0,
            "tool_loop_max": 2,
        }

        with patch("agent.nodes.action_planner.state_manager.player.update_player_event",
                    return_value=None):
            result = await action_planner_node(state)

        assert result["should_play_music"] is True
        rds = state["dependencies"]["runtime_dj_state"]
        queue = rds.get("playlist_queue", [])
        # REPLAN 事件 → append：旧队列 + 新歌曲（New A 是当前歌被排除）
        # 结果：old1, old2, New B (2002)
        assert len(queue) == 3, f"预期 3 首（2 旧 + 1 新），实际 {len(queue)}"
        assert queue[0]["song_id"] == "old1"
        assert queue[1]["song_id"] == "old2"
        assert queue[2]["song_id"] == "2002"

    @pytest.mark.asyncio
    async def test_queue_update_strategy_conversation_replaces(self):
        """用户对话事件 → queue_update="replace"，新旧队列替换。"""
        from unittest.mock import patch
        from agent.nodes.action_planner import action_planner_node

        tool_msgs = [{
            "name": "play_music",
            "result": {
                "songs": [
                    {"id": "3001", "name": "Fresh A", "artists": [{"name": "F A"}]},
                    {"id": "3002", "name": "Fresh B", "artists": [{"name": "F B"}]},
                ],
                "query": "fresh", "count": 2,
            },
        }]

        state = {
            "trigger_type": "conversation",
            "trigger_event": {"text": "帮我换一批歌"},
            "runtime_snapshot": {"playlist_queue": []},
            "dependencies": {
                "runtime_dj_state": {
                    "playlist_queue": [
                        {"song_id": "old1", "source": "search"},
                    ],
                },
            },
            "__refs__": {},
            "actions": [],
            "tool_messages": tool_msgs,
            "llm_decision": {
                "playlist_decision": {
                    "action": "replace",
                    "songs": [{"name": "Fresh A", "artist": "F A"}],
                    "reason": "user request",
                },
                "dialogue_decision": {"should_speak": False, "text": ""},
            },
            "tool_loop_count": 0,
            "tool_loop_max": 2,
        }

        with patch("agent.nodes.action_planner.state_manager.player.update_player_event",
                    return_value=None):
            result = await action_planner_node(state)

        assert result["should_play_music"] is True
        rds = state["dependencies"]["runtime_dj_state"]
        queue = rds.get("playlist_queue", [])
        # 对话 → replace：旧队列被完全替换为搜索歌曲
        # Fresh A(3001) 是当前歌被排除，剩下 Fresh B(3002)
        assert len(queue) == 1, f"预期 1 首新歌，实际 {len(queue)}"
        assert queue[0]["song_id"] == "3002"
        assert queue[0]["source"] == "search"

    @pytest.mark.asyncio
    async def test_queue_update_strategy_insert_now_preserves_queue(self):
        """insert_now 插播：只插入点名歌曲到队列头部，不替换现有队列。"""
        from unittest.mock import patch
        from agent.nodes.action_planner import action_planner_node

        tool_msgs = [{
            "name": "play_music",
            "result": {
                "songs": [
                    {"id": "4001", "name": "知我", "artists": [{"name": "xxx"}]},
                    {"id": "4002", "name": "知我(Live)", "artists": [{"name": "xxx"}]},
                    {"id": "4003", "name": "知我(伴奏)", "artists": [{"name": "xxx"}]},
                    {"id": "4004", "name": "其他歌", "artists": [{"name": "其他"}]},
                ],
                "query": "知我", "count": 4,
            },
        }]

        state = {
            "trigger_type": "conversation",
            "trigger_event": {"text": "放一首知我"},
            "runtime_snapshot": {"playlist_queue": []},
            "dependencies": {
                "runtime_dj_state": {
                    "playlist_queue": [
                        {"song_id": "old1", "name": "旧歌1", "source": "search"},
                        {"song_id": "old2", "name": "旧歌2", "source": "search"},
                        {"song_id": "old3", "name": "旧歌3", "source": "search"},
                    ],
                },
            },
            "__refs__": {},
            "actions": [],
            "tool_messages": tool_msgs,
            "llm_decision": {
                "playlist_decision": {
                    "action": "insert_now",
                    "songs": [{"name": "知我", "artist": "xxx"}],
                    "reason": "user_request",
                },
                "dialogue_decision": {"should_speak": True, "text": "好的，马上为你播放《知我》。"},
            },
            "tool_loop_count": 0,
            "tool_loop_max": 2,
        }

        with patch("agent.nodes.action_planner.state_manager.player.update_player_event",
                    return_value=None):
            result = await action_planner_node(state)

        assert result["should_play_music"] is True
        assert result["actions"][0]["type"] == "play_song"
        assert result["actions"][0]["params"]["song_id"] == "4001"
        rds = state["dependencies"]["runtime_dj_state"]
        queue = rds.get("playlist_queue", [])
        # 队列头部是知我，后面是旧队列
        assert len(queue) == 4, f"预期 4 首（1 插播 + 3 旧），实际 {len(queue)}"
        assert queue[0]["song_id"] == "4001", f"队首应为知我，实际 {queue[0]}"
        assert queue[1]["song_id"] == "old1"
        assert queue[2]["song_id"] == "old2"
        assert queue[3]["song_id"] == "old3"
        # 没有搜索结果的无关歌曲
        all_ids = {q["song_id"] for q in queue}
        assert "4002" not in all_ids, "知我(Live) 不应进入队列"
        assert "4003" not in all_ids, "知我(伴奏) 不应进入队列"
        assert "4004" not in all_ids, "其他歌 不应进入队列"

    @pytest.mark.asyncio
    async def test_queue_update_strategy_insert_now_no_search_flood(self):
        """insert_now 不把搜索结果全部塞入队列，只有点名歌曲。"""
        from unittest.mock import patch
        from agent.nodes.action_planner import action_planner_node

        tool_msgs = [{
            "name": "play_music",
            "result": {
                "songs": [
                    {"id": "5001", "name": "点歌", "artists": [{"name": "歌手"}]},
                    {"id": "5002", "name": "点歌(Live)", "artists": [{"name": "歌手"}]},
                    {"id": "5003", "name": "点歌(伴奏)", "artists": [{"name": "歌手"}]},
                    {"id": "5004", "name": "同歌手其他", "artists": [{"name": "歌手"}]},
                ],
                "query": "点歌", "count": 4,
            },
        }]

        state = {
            "trigger_type": "conversation",
            "trigger_event": {"text": "播放点歌"},
            "runtime_snapshot": {"playlist_queue": []},
            "dependencies": {
                "runtime_dj_state": {
                    "playlist_queue": [],  # 空队列
                },
            },
            "__refs__": {},
            "actions": [],
            "tool_messages": tool_msgs,
            "llm_decision": {
                "playlist_decision": {
                    "action": "insert_now",
                    "songs": [{"name": "点歌", "artist": "歌手"}],
                    "reason": "user_request",
                },
                "dialogue_decision": {"should_speak": True, "text": "来了。"},
            },
            "tool_loop_count": 0,
            "tool_loop_max": 2,
        }

        with patch("agent.nodes.action_planner.state_manager.player.update_player_event",
                    return_value=None):
            result = await action_planner_node(state)

        assert result["should_play_music"] is True
        assert result["actions"][0]["params"]["song_id"] == "5001"
        rds = state["dependencies"]["runtime_dj_state"]
        queue = rds.get("playlist_queue", [])
        # 队列只有点名歌曲，没有搜索结果的其他歌曲
        assert len(queue) == 1, f"预期 1 首（只有点名的歌），实际 {len(queue)}"
        assert queue[0]["song_id"] == "5001"

    @pytest.mark.asyncio
    async def test_fallback_not_in_normal_queue(self):
        """搜索结果存在时，_REAL_FALLBACK_SONGS 不进入 playlist_queue。"""
        from agent.nodes.action_planner import _REAL_FALLBACK_SONGS, _get_all_search_songs

        # 模拟 5 首真实搜索结果
        tool_msgs = [{
            "name": "play_music",
            "result": {
                "songs": [
                    {"id": "99901", "name": "Real 1", "artists": [{"name": "R1"}]},
                    {"id": "99902", "name": "Real 2", "artists": [{"name": "R2"}]},
                    {"id": "99903", "name": "Real 3", "artists": [{"name": "R3"}]},
                    {"id": "99904", "name": "Real 4", "artists": [{"name": "R4"}]},
                    {"id": "99905", "name": "Real 5", "artists": [{"name": "R5"}]},
                ],
                "query": "real", "count": 5,
            },
        }]

        search_songs = _get_all_search_songs(tool_msgs)
        search_ids = {s.get("id", "") for s in search_songs}
        fallback_ids = {s["song_id"] for s in _REAL_FALLBACK_SONGS}

        # 搜索结果的 song_id 与 fallback 的 song_id 不应重叠
        overlap = search_ids & fallback_ids
        assert len(overlap) == 0, f"搜索结果与 fallback 有重叠 song_id: {overlap}"

        # 验证搜索结果数量
        assert len(search_songs) == 5


# ═══════════════════════════════════════════════════════════════
# Test: _to_queue_songs 保留 source 字段
# ═══════════════════════════════════════════════════════════════
class TestToQueueSongsSource:
    """_to_queue_songs 正确保留 source 字段。"""

    def test_preserves_search_source(self):
        """source="search" 的歌曲 → 队列条目保留 source="search"。"""
        from agent.nodes.action_planner import _to_queue_songs

        songs = [
            {"id": "1001", "name": "Test", "artist": "TA", "source": "search"},
        ]
        result = _to_queue_songs(songs)
        assert result[0]["source"] == "search"

    def test_preserves_fallback_source(self):
        """source="fallback" 的歌曲 → 队列条目保留 source="fallback"。"""
        from agent.nodes.action_planner import _to_queue_songs

        songs = [
            {"song_id": "999001", "name": "F", "artist": "FA", "source": "fallback"},
        ]
        result = _to_queue_songs(songs)
        assert result[0]["source"] == "fallback"

    def test_default_source_is_search(self):
        """无 source 字段 → 默认为 "search"。"""
        from agent.nodes.action_planner import _to_queue_songs

        songs = [
            {"id": "1002", "name": "T2", "artist": "TA2"},
        ]
        result = _to_queue_songs(songs)
        assert result[0]["source"] == "search"


# ═══════════════════════════════════════════════════════════════
# Test: _REAL_FALLBACK_SONGS 有 source="fallback"
# ═══════════════════════════════════════════════════════════════
class TestFallbackSongsHaveSource:
    """_REAL_FALLBACK_SONGS 全部带有 source="fallback" 标记。"""

    def test_all_fallback_have_source_field(self):
        """每条 fallback 歌曲都有 source="fallback"。"""
        from agent.nodes.action_planner import _REAL_FALLBACK_SONGS

        for song in _REAL_FALLBACK_SONGS:
            assert song.get("source") == "fallback", \
                f"歌曲 {song['name']} 缺少 source='fallback'"

