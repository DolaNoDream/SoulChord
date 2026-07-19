"""EventDispatcher 的 Graph 之外辅助处理。

Init Planner 在 Graph 未准备好时的简易路径。
"""

import logging
import time

from agent.runtime.event_queue import Event
from agent.state.state_manager import state_manager
from agent.state.runtime_dj_state import sync_from_program_state
from agent.shared.enums import EventType

logger = logging.getLogger(__name__)


async def handle_init_event_direct(event: Event, runtime_dj_state: dict):
    """Graph 未就绪时直接处理 AGENT_INIT 事件。

    简易路径：写 program_state → 同步 RuntimeDJState →（将来 emit WS 消息）。
    完整路径需要 Graph 7 节点（下一轮编码实现）。
    """
    if event.type != EventType.AGENT_INIT:
        logger.info("Ignoring non-init event before graph ready: %s", event.type)
        return

    payload = event.payload or {}
    init_mode = payload.get("reason", "first_init")
    logger.info("Direct init handling: init_mode=%s", init_mode)

    # 1. 构造基本的 ProgramState
    now_ts = int(time.time() * 1000)
    program_state = {
        "version": "1.0",
        "updated_at": now_ts,
        "program_date": state_manager.program.today_str(),
        "today_theme": "今日陪伴",
        "current_segment": "intro",
        "program_mood": "neutral",
        "program_goal": "陪伴用户",
        "voice_style": "warm",
        "speech_rate": 0.8,
        "speak_frequency": "low",
        "program_status": "running",
    }

    # 2. 写入 program_state.json
    ok = state_manager.program.save_program_state(program_state)
    if not ok:
        logger.error("Failed to save program_state on init")

    # 3. 同步 RuntimeDJState
    sync_from_program_state(runtime_dj_state, program_state)
    logger.info("Init complete: mode=%s, today_theme=%s", init_mode, program_state["today_theme"])
