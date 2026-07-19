"""E2E 冒烟测试共享 fixtures — 可拆分链式依赖。

Fixture 层次（上游 → 下游）：
    data_dir → init_data → state_manager → runtime_dj_state
               event_queue
               graph
               mock_llm_service
                                    → e2e_context（组合）
"""

import asyncio
import copy
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── 全局辅助 ──


def drain_queue(q: asyncio.Queue) -> list:
    """清空 asyncio.Queue 并返回所有消息。"""
    msgs = []
    while not q.empty():
        try:
            msgs.append(q.get_nowait())
        except asyncio.QueueEmpty:
            break
    return msgs


def build_initial_state(ctx: dict, trigger_type: str, trigger_event: dict,
                        **overrides) -> dict:
    """构造 AgentState — 模拟 EventDispatcher._build_initial_state。

    Args:
        ctx: e2e_context fixture 返回的字典
        trigger_type: 如 "conversation", "system_init", "player_event"
        trigger_event: Event payload dict
        **overrides: 额外 state 覆盖

    Returns:
        完整 AgentState dict（可直接 graph.ainvoke）
    """
    snapshot = copy.deepcopy(ctx["runtime_dj_state"])

    state = {
        "trigger_type": trigger_type,
        "trigger_event": trigger_event,
        "event_priority": "P0",
        "init_mode": "resume",
        "runtime_snapshot": snapshot,
        "dependencies": {
            "event_queue": ctx["event_queue"],
            "state_manager": ctx["state_manager"],
            "runtime_dj_state": ctx["runtime_dj_state"],
        },
        "__refs__": {
            "event_service": ctx["event_service"],
            "llm_service": ctx["mock_llm_service"],
        },
        "messages": [],
        "tool_messages": [],
        "tool_loop_count": 0,
        "tool_loop_max": 1,
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
    state.update(overrides)
    return state


# ── Fixtures ──


@pytest.fixture
def data_dir(tmp_path):
    """临时 data 目录 + 覆盖全部 settings 路径（测试结束恢复）。"""
    from agent.config import settings

    d = tmp_path / "data"
    d.mkdir()

    # 保存原值
    saved = {
        "DATA_DIR": settings.DATA_DIR,
        "MEMORY_FILE": settings.MEMORY_FILE,
        "SETTINGS_FILE": settings.SETTINGS_FILE,
        "PLAYLISTS_FILE": settings.PLAYLISTS_FILE,
        "PROGRAM_STATE_FILE": settings.PROGRAM_STATE_FILE,
        "PLAYER_MIRROR_FILE": settings.PLAYER_MIRROR_FILE,
        "PLAYER_HISTORY_FILE": settings.PLAYER_HISTORY_FILE,
    }

    # 覆盖为临时路径
    settings.DATA_DIR = str(d)
    settings.MEMORY_FILE = str(d / "memory.json")
    settings.SETTINGS_FILE = str(d / "settings.json")
    settings.PLAYLISTS_FILE = str(d / "playlists.json")
    settings.PROGRAM_STATE_FILE = str(d / "program_state.json")
    settings.PLAYER_MIRROR_FILE = str(d / "player_mirror.json")
    settings.PLAYER_HISTORY_FILE = str(d / "player_history.json")

    yield d

    # 恢复原值
    for attr, val in saved.items():
        setattr(settings, attr, val)


@pytest.fixture
def init_data(data_dir):
    """data_initializer → 6 JSON 文件。"""
    from agent.state.data_initializer import init_data_files
    init_data_files()
    return data_dir


@pytest.fixture
def event_queue():
    """Fresh EventQueue + 绑定全局 event_service（测试后解绑）。"""
    from agent.runtime.event_queue import EventQueue
    from agent.services.event_service import event_service

    q = EventQueue()
    event_service.bind(q)

    yield q

    # 解绑，避免跨测试污染
    event_service._queue = None


@pytest.fixture
def state_manager(init_data):
    """预热后的 state_manager 单例。"""
    from agent.state.state_manager import state_manager
    state_manager.memory.warmup()
    return state_manager


@pytest.fixture
def runtime_dj_state(state_manager, init_data):
    """从 disk 重建 RuntimeDJState + 注入 state_manager（测试后清除）。"""
    from agent.state.runtime_dj_state import build_runtime_dj_state_from_disk
    from agent.state.state_manager import state_manager as sm

    rds = build_runtime_dj_state_from_disk()
    sm.runtime_dj_state = rds

    yield rds

    sm.runtime_dj_state = {}


@pytest.fixture
def graph():
    """编译后的 StateGraph（8 节点）。"""
    from agent.graph import build_graph
    return build_graph()


@pytest.fixture
def mock_llm_service():
    """Fixture 级 mock LLMService — 经 __refs__["llm_service"] 注入。

    默认返回 conversation 决策。测试可 override 返回值：
        mock_llm_service.call_json.return_value = {"ok": True, "data": {...}}
    """
    svc = AsyncMock()
    svc.call_json = AsyncMock(return_value={
        "ok": True,
        "data": {
            "program_decision": {
                "today_theme": None, "current_segment": None, "program_mood": None,
                "program_goal": None, "voice_style": None, "speech_rate": None,
                "speak_frequency": None,
            },
            "playlist_decision": {
                "action": "keep", "songs": [], "reason": "E2E test",
            },
            "dialogue_decision": {
                "should_speak": True, "text": "E2E 测试回复", "style": "warm",
            },
            "tool_calls": [],
        },
    })
    return svc


@pytest.fixture(autouse=True)
def drain_ws_out_queue():
    """每个测试前后清空 ws_out_queue（模块级全局队列）。"""
    from agent.runtime.ws_sender import ws_out_queue
    drain_queue(ws_out_queue)
    yield
    drain_queue(ws_out_queue)


@pytest.fixture
def e2e_context(init_data, state_manager, runtime_dj_state,
                event_queue, graph, mock_llm_service):
    """组合 fixture — 一次引用即可拿到全部 E2E 依赖。"""
    from agent.services.event_service import event_service
    return {
        "init_data": init_data,
        "state_manager": state_manager,
        "runtime_dj_state": runtime_dj_state,
        "event_queue": event_queue,
        "graph": graph,
        "mock_llm_service": mock_llm_service,
        "event_service": event_service,
    }
