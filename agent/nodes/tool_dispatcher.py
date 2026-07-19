"""tool_dispatcher 节点 — 执行 pending_tool_calls 并回填 tool_messages。

★ v0.1.1 A 项：Tool Loop 第二轮出口
★ v0.1.2 P0-2：tool_loop_count 普通字段（无 reducer），Node 自己 +1
★ v0.1.2 P0-1：return dict（partial update）
★ v0.1.2 P1-4：读 RuntimeDJState 经 state["runtime_snapshot"]
"""

import logging
import time

from agent.services.adapter import adapter

logger = logging.getLogger(__name__)


async def tool_dispatcher_node(state: dict) -> dict:
    """执行所有 pending_tool_calls，回填 tool_messages。

    返回 partial dict：
      - tool_messages: list[dict]（append reducer，自动累积）
      - tool_loop_count: int（普通字段，Node 自己 +1）
      - next_node: str（conditional edge 读取）
    """
    pending_calls = state.get("pending_tool_calls", [])
    if not pending_calls:
        return {
            "tool_messages": [],
            "tool_loop_count": state.get("tool_loop_count", 0),
            "next_node": "action_planner",
        }

    tool_messages = []
    for call in pending_calls:
        tool_name = call.get("name", "unknown")
        tool_args = call.get("args", {})
        start_ts = int(time.time() * 1000)

        try:
            result = await adapter.dispatch(tool_name, tool_args)
            duration_ms = int(time.time() * 1000) - start_ts
            tool_messages.append({
                "name": tool_name,
                "args": tool_args,
                "result": result,
                "ts": start_ts,
                "duration_ms": duration_ms,
                "status": "ok",
            })
            logger.info("Tool OK: %s (%.0fms)", tool_name, duration_ms)
        except NotImplementedError:
            duration_ms = int(time.time() * 1000) - start_ts
            tool_messages.append({
                "name": tool_name,
                "args": tool_args,
                "result": {"error": f"Tool not implemented: {tool_name}"},
                "ts": start_ts,
                "duration_ms": duration_ms,
                "status": "not_implemented",
            })
            logger.warning("Tool not implemented: %s", tool_name)
        except Exception as e:
            duration_ms = int(time.time() * 1000) - start_ts
            tool_messages.append({
                "name": tool_name,
                "args": tool_args,
                "result": {"error": str(e)},
                "ts": start_ts,
                "duration_ms": duration_ms,
                "status": "error",
            })
            logger.error("Tool error: %s: %s", tool_name, e)

    # ★ v0.1.2 P0-2：普通字段，Node 自己 +1
    new_count = state.get("tool_loop_count", 0) + 1
    max_count = state.get("tool_loop_max", 1)

    # ★ v0.1.1 A 项：最多 1 次回环，max=1 时直接 action_planner
    if new_count < max_count:
        next_node = "dj_planner"
    else:
        next_node = "action_planner"

    return {
        "tool_messages": tool_messages,
        "tool_loop_count": new_count,
        "next_node": next_node,
    }
