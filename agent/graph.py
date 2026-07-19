"""StateGraph 组装 — 7 节点 + 条件边 + 编译。

★ v0.6.1 A 项：Tool Loop 路由 dj_planner → tool_dispatcher → dj_planner（max=1）
★ v0.1.2 P0-2：tool_loop_count 普通字段（条件边从 state 读 next_node）
★ v0.1.3：AgentState TypedDict + 真实 StateGraph

★ H19 Runtime vs Graph 边界（不可违）：
   Runtime 负责生命周期（while True 消费 EventQueue）
   Graph 负责单次推理（每次事件触发一次完整 ainvoke）

   禁止 while True: graph.invoke()，3 条理由：
   1. 消耗 token：无事件时持续调用 LLM
   2. Agent 主动幻想：无真实事件输入但 LLM 仍要决策
   3. 无法响应优先级事件：抢占不到 PriorityQueue

   正确模式：
     while self._running:
         event = await queue.get()
         result = await graph.ainvoke(state)  # 单次，结束返回
         await emit_response(result)

   参见 dev/agent-design/workflow.md §3.6 反例框。
"""

import logging

from langgraph.graph import StateGraph, END

from agent.state.agent_state import AgentState
from agent.nodes.router import router_node
from agent.nodes.context_builder import context_builder_node
from agent.nodes.dj_planner import dj_planner_node
from agent.nodes.action_planner import action_planner_node
from agent.nodes.emit_response import emit_response_node
from agent.nodes.action_executor import action_executor_node
from agent.nodes.feedback_extractor import feedback_extractor_node
from agent.nodes.tool_dispatcher import tool_dispatcher_node

logger = logging.getLogger(__name__)


# ── 条件边路由函数 ──


def _route_from_router(state: AgentState) -> str:
    """router → 4 路分流：context_builder / feedback_extractor / action_planner / emit_response。"""
    return state.get("next_node", "emit_response")


def _route_from_dj_planner(state: AgentState) -> str:
    """dj_planner → tool_dispatcher / action_planner。"""
    return state.get("next_node", "action_planner")


def _route_from_tool_dispatcher(state: AgentState) -> str:
    """tool_dispatcher → dj_planner / action_planner。"""
    return state.get("next_node", "action_planner")


def build_graph():
    """构造 8 节点 StateGraph + 编译。

    Returns:
        CompiledGraph（可用 .ainvoke(state)）
    """
    builder = StateGraph(AgentState)

    # ── 注册全部 8 节点 ──
    builder.add_node("router", router_node)
    builder.add_node("context_builder", context_builder_node)
    builder.add_node("dj_planner", dj_planner_node)
    builder.add_node("action_planner", action_planner_node)
    builder.add_node("action_executor", action_executor_node)
    builder.add_node("emit_response", emit_response_node)
    builder.add_node("feedback_extractor", feedback_extractor_node)
    builder.add_node("tool_dispatcher", tool_dispatcher_node)

    # ── 入口 ──
    builder.set_entry_point("router")

    # ── router → conditional（4 路） ──
    builder.add_conditional_edges(
        "router",
        _route_from_router,
        {
            "context_builder": "context_builder",
            "feedback_extractor": "feedback_extractor",
            "action_planner": "action_planner",
            "emit_response": "emit_response",
        },
    )

    # ── context_builder → dj_planner ──
    builder.add_edge("context_builder", "dj_planner")

    # ── feedback_extractor → action_planner ──
    builder.add_edge("feedback_extractor", "action_planner")

    # ── dj_planner → conditional ──
    builder.add_conditional_edges(
        "dj_planner",
        _route_from_dj_planner,
        {
            "tool_dispatcher": "tool_dispatcher",
            "action_planner": "action_planner",
        },
    )

    # ── tool_dispatcher → conditional ──
    builder.add_conditional_edges(
        "tool_dispatcher",
        _route_from_tool_dispatcher,
        {
            "dj_planner": "dj_planner",
            "action_planner": "action_planner",
        },
    )

    # ── action_planner → action_executor → emit_response ──
    builder.add_edge("action_planner", "action_executor")
    builder.add_edge("action_executor", "emit_response")

    # ── emit_response → END ──
    builder.add_edge("emit_response", END)

    logger.info("StateGraph compiled: 8 nodes, 7 edges (3 conditional)")
    return builder.compile()
