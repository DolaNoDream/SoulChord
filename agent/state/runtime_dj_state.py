"""RuntimeDJState — 长寿 in-memory DJ 执行态封装。

定义：
  - RuntimeDJState = 当前执行态（current_song / playlist_queue / current_scene / program_mood / ...）
  - 长寿 in RuntimeContext（不镜像到 AgentState；snapshot 由 Runtime 在 invoke 前注入）
  - Node 读 RuntimeDJState 经 AgentState.runtime_snapshot（冷快照）
  - 只 Node 写 in-memory 字段（current_scene / pending_actions）可经 state["dependencies"]["runtime_dj_state"] 直接改
    其他字段必须经 state_manager.player / state_manager.program

★ v0.6.1 D 项 + ★ v0.1.2 P0-1/P0-3
"""

import copy
from typing import Optional

from agent.state import program_state as ps_mod
from agent.state import player_state as pm_mod
from agent.shared.enums import ProgramSegment, ProgramMood, InteractionLevel

# 默认 RuntimeDJState（启动时用）
DEFAULT_RUNTIME_DJ_STATE: dict = {
    # 当前播放（来自 player_mirror.json）
    "current_song": None,
    "current_position_ms": 0,
    "is_playing": False,
    # 节目片段
    "current_segment": "intro",
    "segment_started_at_ms": 0,
    # 播放队列
    "playlist_queue": [],
    "queue_strategy": {},
    # 当前场景（in-memory only）
    "current_scene": "default",
    # DJ 风格
    "program_mood": "neutral",
    "interaction_level": "low",
    # 待执行动作（in-memory only）
    "pending_actions": [],
    # DJ 话术追踪（in-memory only）
    "last_dj_speech_at_ms": 0,
    "last_dj_speech_song_id": "",
    "dj_speech_suppressed": False,
    # ★ P0-2: 用户中断标记 — chat_send 入队时设置，play_end 消费后清除
    "pending_user_interrupt": False,
    # 元数据
    "updated_at_ms": 0,
    "updated_by": "system",
}


def build_runtime_dj_state_from_disk() -> dict:
    """从 disk 重建 RuntimeDJState（lifespan 第 4 步调用）。

    合并 player_mirror.json + program_state.json 到完整 RuntimeDJState。
    """
    state = dict(DEFAULT_RUNTIME_DJ_STATE)

    # 1. 从 player_mirror.json 恢复播放状态
    mirror = pm_mod.load_player_mirror()
    if mirror:
        state["current_song"] = mirror.get("current_song")
        state["current_position_ms"] = mirror.get("current_position_ms", 0)
        state["is_playing"] = mirror.get("is_playing", False)
        state["playlist_queue"] = mirror.get("playlist_queue", [])
        state["queue_strategy"] = mirror.get("queue_strategy", {})

    # 2. 从 program_state.json 恢复节目状态
    ps = ps_mod.load_program_state()
    if ps:
        state["current_segment"] = ps.get("current_segment", "intro")
        state["program_mood"] = ps.get("program_mood", "neutral")
        state["interaction_level"] = _map_interaction_level(
            ps.get("speak_frequency", "low")
        )

    # 3. segment_started_at_ms 重置为 now
    import time
    state["segment_started_at_ms"] = int(time.time() * 1000)
    state["updated_at_ms"] = int(time.time() * 1000)

    return state


def snapshot_runtime_dj_state(rds: dict) -> dict:
    """对 RuntimeDJState 做冷拷贝快照。

    由 Runtime/EventDispatcher 在 invoke 前调用。
    """
    return copy.deepcopy(rds)


def sync_from_program_state(rds: dict, ps: dict):
    """用 program_state 同步 RuntimeDJState 的节目字段。"""
    rds["current_segment"] = ps.get("current_segment", rds.get("current_segment", "intro"))
    rds["program_mood"] = ps.get("program_mood", rds.get("program_mood", "neutral"))
    rds["interaction_level"] = _map_interaction_level(
        ps.get("speak_frequency", "low")
    )
    import time
    rds["updated_at_ms"] = int(time.time() * 1000)


def _map_interaction_level(speak_freq: str) -> str:
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "silent": "silent",
    }
    return mapping.get(speak_freq, "low")
