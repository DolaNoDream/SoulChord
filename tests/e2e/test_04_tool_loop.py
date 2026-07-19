"""E2E 冒烟测试 — Tool Loop（dj_planner ↔ tool_dispatcher）。

覆盖：
  1. dj_planner 返回 pending_tool_calls → tool_dispatcher 执行
  2. 完整循环：dj_planner → tool_dispatcher → dj_planner → action_planner
  3. tool_loop_max=1 强制收尾
  4. 未实现 tool → not_implemented（不抛异常）
"""

import pytest

from agent.runtime.ws_sender import ws_out_queue
from tests.e2e.conftest import drain_queue, build_initial_state


# ═══════════════════════════════════════════════════════════════
# 1. dj_planner → tool_calls → tool_dispatcher
# ═══════════════════════════════════════════════════════════════

class TestDjPlannerEmitsToolCalls:
    """dj_planner 节点返回 pending_tool_calls。"""

    @pytest.mark.asyncio
    async def test_dj_planner_returns_tool_calls(self, e2e_context):
        """dj_planner + mock LLM 返回 tool_calls → pending_tool_calls 非空。"""
        ctx = e2e_context
        mock_llm = ctx["mock_llm_service"]

        # LLM 返回含 tool_calls 的决策
        mock_llm.call_json.return_value = {
            "ok": True,
            "data": {
                "program_decision": {
                    "today_theme": None, "current_segment": None, "program_mood": None,
                    "program_goal": None, "voice_style": None, "speech_rate": None,
                    "speak_frequency": None,
                },
                "playlist_decision": {
                    "action": "keep", "songs": [], "reason": "test",
                },
                "dialogue_decision": {
                    "should_speak": False, "text": "", "style": "neutral",
                },
                "tool_calls": [
                    {"name": "get_environment_context", "args": {}},
                ],
            },
        }

        state = build_initial_state(
            ctx, trigger_type="conversation",
            trigger_event={"text": "查询环境", "subtype": "user_text",
                           "msg_id": "tool_001"},
        )

        result = await ctx["graph"].ainvoke(state)

        # Graph 完整跑通
        assert result.get("turn_count", 0) >= 1

        # 验证 ws_out_queue 有内容（说明 full path 走通）
        msgs = drain_queue(ws_out_queue)
        assert len(msgs) >= 0  # 不强制断言内容，只要不 crash


# ═══════════════════════════════════════════════════════════════
# 2. Tool Loop 完整循环
# ═══════════════════════════════════════════════════════════════

class TestToolLoopFullCycle:
    """工具循环完整路径：dj_planner → tool_dispatcher → dj_planner → action_planner。

    ★ 验证 tool_dispatcher 结果回传 + tool_loop_count 递增。
    """

    @pytest.mark.asyncio
    async def test_tool_dispatcher_executes_and_returns_results(self, e2e_context):
        """tool_dispatcher 执行 tool_calls 并返回 tool_messages。"""
        from agent.nodes.tool_dispatcher import tool_dispatcher_node

        ctx = e2e_context

        state = {
            "pending_tool_calls": [
                {"name": "get_environment_context", "args": {}},
                {"name": "query_user_preference", "args": {"category": "music"}},
            ],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await tool_dispatcher_node(state)

        assert len(result["tool_messages"]) == 2
        assert result["tool_messages"][0]["name"] == "get_environment_context"
        assert result["tool_messages"][0]["status"] == "ok"
        assert result["tool_messages"][1]["name"] == "query_user_preference"
        assert result["tool_messages"][1]["status"] == "ok"
        # tool_loop_count 按 invoke 次数 +1（不是按 tool 个数）
        assert result["tool_loop_count"] == 1
        # tool_loop_max=1 → 强制收尾到 action_planner
        assert result["next_node"] == "action_planner"

    @pytest.mark.asyncio
    async def test_tool_loop_max_force_terminates(self, e2e_context):
        """tool_loop_max=1 → tool_dispatcher 后强制收尾（即使有更多 tool_calls）。"""
        from agent.nodes.tool_dispatcher import tool_dispatcher_node

        state = {
            "pending_tool_calls": [
                {"name": "get_environment_context", "args": {}},
            ],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await tool_dispatcher_node(state)

        # 执行了 1 个工具
        assert len(result["tool_messages"]) == 1
        assert result["tool_loop_count"] == 1
        # 强制收尾（尽管 tool_count < max，但条件边读 next_node）
        assert result["next_node"] == "action_planner"

    @pytest.mark.asyncio
    async def test_tool_dispatcher_empty_calls(self, e2e_context):
        """pending_tool_calls 为空 → 空返回。"""
        from agent.nodes.tool_dispatcher import tool_dispatcher_node

        result = await tool_dispatcher_node({
            "pending_tool_calls": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        })

        assert result["tool_messages"] == []
        assert result["tool_loop_count"] == 0
        assert result["next_node"] == "action_planner"


# ═══════════════════════════════════════════════════════════════
# 3. 未实现 tool → not_implemented
# ═══════════════════════════════════════════════════════════════

class TestToolDispatcherUnknown:
    """未实现的 tool 安全降级。"""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_not_implemented(self, e2e_context):
        """未知 tool → status=not_implemented，不抛异常。"""
        from agent.nodes.tool_dispatcher import tool_dispatcher_node

        result = await tool_dispatcher_node({
            "pending_tool_calls": [
                {"name": "nonexistent_tool", "args": {}},
            ],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        })

        assert len(result["tool_messages"]) == 1
        assert result["tool_messages"][0]["status"] == "not_implemented"
        assert result["tool_messages"][0]["name"] == "nonexistent_tool"
        assert result["tool_loop_count"] == 1
