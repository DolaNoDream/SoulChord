"""EventDispatcher — Runtime while True 消费 EventQueue → Graph 单次 invoke。

★ v0.6 A 项：Runtime 负责生命周期 / Graph 负责单次推理 / 禁 while True: graph.invoke()
★ v0.1.2 P1-4：Runtime 在 invoke 前注入 runtime_snapshot 到 AgentState
★ 修正：Dispatcher 只负责 invoke，不参与 Graph 内部路由
"""

import asyncio
import copy
import logging
from typing import Optional

from agent.runtime.event_queue import EventQueue, Event
from agent.state.runtime_dj_state import snapshot_runtime_dj_state
from agent.state.state_manager import state_manager
from agent.services.event_service import event_service
from agent.shared.enums import TriggerType

logger = logging.getLogger(__name__)


class EventDispatcher:
    """事件分发器。

    核心逻辑：
      while self._running:
          event = await queue.get()
          asyncio.create_task(self._handle(event))

    每次 _handle 构造 AgentState → graph.ainvoke → 完成。
    Graph 内部路由由 StateGraph 的 Node + conditional edge 处理。
    """

    def __init__(self, event_queue: EventQueue, runtime_dj_state: dict, llm_service=None):
        self._queue = event_queue
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.runtime_dj_state = runtime_dj_state
        self._llm_service = llm_service
        state_manager.runtime_dj_state = runtime_dj_state

    async def run(self):
        """一直循环消费 EventQueue（Runtime 生命周期）。"""
        self._running = True
        logger.info("EventDispatcher started (Runtime loop)")
        while self._running:
            try:
                event = await self._queue.get()
                asyncio.create_task(self._handle(event))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("EventDispatcher loop error: %s", e)
        logger.info("EventDispatcher stopped")

    def stop(self):
        self._running = False

    async def _handle(self, event: Event):
        """处理单个事件。

        1. 构造 AgentState（含 runtime_snapshot）
        2. graph.ainvoke（单次）
        3. 日志记录结果（emit 由 emit_response Node 内部处理）
        """
        if self._graph is None:
            await self._handle_without_graph(event)
            return

        snapshot = snapshot_runtime_dj_state(self.runtime_dj_state)
        initial_state = self._build_initial_state(event, snapshot)

        try:
            result = await self._graph.ainvoke(initial_state)
            self._log_result(event, result)
        except Exception as e:
            logger.error("Graph invoke failed for event=%s: %s", event.type, e)

    async def _handle_without_graph(self, event: Event):
        """Graph 未准备好时的简易处理（Init Planner 专用）。"""
        logger.info("Graph not ready, handling event directly: %s", event.type)
        from agent.runtime.dispatcher_helpers import handle_init_event_direct
        await handle_init_event_direct(event, self.runtime_dj_state)

    def _build_initial_state(self, event: Event, snapshot: dict) -> dict:
        """构造初始 AgentState。"""
        trigger_type = _map_event_type_to_trigger(event.type)
        return {
            "trigger_type": trigger_type,
            "trigger_event": event.payload,
            "event_priority": event.priority.value if hasattr(event.priority, 'value') else str(event.priority),
            "init_mode": event.payload.get("init_mode", "first_init"),
            "runtime_snapshot": snapshot,
            "dependencies": {
                "event_queue": self._queue,
                "state_manager": state_manager,
                "runtime_dj_state": self.runtime_dj_state,
            },
            "__refs__": {
                "event_service": event_service,
                "llm_service": self._llm_service,
            },
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 2,  # 允许一次完整工具循环：LLM→执行→LLM合成
            "actions": [],
            "pending_tool_calls": [],
            "pending_payload": None,
            "should_speak": False,
            "should_play_music": False,
            "turn_count": 0,
            "last_active_at_ms": 0,
            "user": {},
            "environment": {},
            "program": {},
            "playlist": {},
            "player_mirror": {},
            "llm_decision": None,
            "init_plan": None,
            "feedback_record": None,
            "last_error": None,
            "next_node": "",
        }

    def _log_result(self, event: Event, result: dict):
        """记录 graph invoke 结果（不 emit——emit_response Node 负责）。"""
        trigger_type = result.get("trigger_type", "?")
        pending = result.get("pending_payload") or {}
        actions = result.get("actions", [])
        tool_count = result.get("tool_loop_count", 0)
        turn = result.get("turn_count", 0)

        log_parts = [f"event={event.type}", f"trigger={trigger_type}", f"turn={turn}"]
        if pending.get("chat_reply"):
            log_parts.append(f"chat=yes")
        if pending.get("music_play"):
            log_parts.append(f"music=yes")
        if pending.get("transition_speech"):
            log_parts.append("transition=yes")
        if actions:
            log_parts.append(f"actions={len(actions)}")
        if tool_count:
            log_parts.append(f"tools={tool_count}")

        logger.info("Graph invoke done: %s", " | ".join(log_parts))

    _graph = None

    def set_graph(self, graph):
        self._graph = graph


def _map_event_type_to_trigger(event_type) -> str:
    """EventType → TriggerType 映射。"""
    mapping = {
        "agent_init": "system_init",
        "chat_send": "conversation",
        "voice_text": "conversation",
        "replan_request": "replan_event",
        "player_song_started": "player_event",
        "player_song_progress": "player_event",
        "player_song_finished": "player_event",
        "player_user_skip": "player_event",
        "player_user_like": "player_event",
        "player_user_dislike": "player_event",
        "player_play_end": "player_event",
        "timer_feishu": "timer_event",
        "timer_heartbeat": "system",
        "timer_playlist_health": "timer_event",
        "timer_program_tick": "timer_event",
        "user_control": "user_control",
        "system": "system",
    }
    return mapping.get(event_type.value if hasattr(event_type, 'value') else str(event_type), "system")
