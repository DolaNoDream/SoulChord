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
        assert pld["action"] in ("keep", "replace", "add")
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
            "initial_playlist": [{"song_id": "1", "name": "LLM Song", "artist": "LLM", "scene_match": "default"}],
            "first_song_id": "1",
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
        assert result["next_node"] == "action_planner"

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
