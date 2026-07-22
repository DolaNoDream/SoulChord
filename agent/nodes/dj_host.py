"""dj_host 节点 — DJ 话术生成。

由 DJ_MONOLOGUE 事件触发，接收 context_builder 的 5 域上下文，
调用 DJHostService 生成自然过渡语，输出到 pending_payload.dj_speech。

数据流：
  router → context_builder → dj_host → action_planner → action_executor → emit_response
"""

import logging
import time

logger = logging.getLogger(__name__)


async def dj_host_node(state: dict) -> dict:
    """生成 DJ 话术（Graph Node）。

    从 runtime_snapshot/program/user/environment 构建 context，
    调 DJHostService.generate_speech()，结果写入 pending_payload.dj_speech。

    Returns:
        dict 含 pending_payload 和 next_node。
    """
    snapshot = state.get("runtime_snapshot") or {}
    playlist_queue = snapshot.get("playlist_queue", [])
    current_song = snapshot.get("current_song")

    # 守卫：无当前歌曲 → 无话可说
    if not current_song:
        logger.debug("DJ Host: no current_song, skip")
        return {"pending_payload": None, "should_speak": False, "next_node": "action_planner"}

    current_song_id = current_song.get("song_id") or current_song.get("id", "")
    if not current_song_id:
        logger.debug("DJ Host: current_song has no id, skip")
        return {"pending_payload": None, "should_speak": False, "next_node": "action_planner"}

    # 去重检查：同一首歌已生成过话术 → 跳过
    rds = state.get("dependencies", {}).get("runtime_dj_state")
    if rds:
        last_id = rds.get("last_dj_speech_song_id", "")
        last_at = rds.get("last_dj_speech_at_ms", 0)
        now_ms = int(time.time() * 1000)
        if current_song_id == last_id and now_ms - last_at < 60000:
            logger.debug("DJ Host: speech already done for song=%s (<60s), skip", current_song_id)
            return {"pending_payload": None, "should_speak": False, "next_node": "action_planner"}

    # 构建 context
    next_song = playlist_queue[0] if playlist_queue else None
    program = state.get("program") or {}
    env = state.get("environment") or {}
    user = state.get("user") or {}

    context = {
        "persona_name": "Soul",
        "persona_style": "warm",
        "target_song_id": current_song_id,
        "current_song": current_song,
        "next_song": next_song,
        "queue_empty": len(playlist_queue) == 0,
        "program_mood": snapshot.get("program_mood", "neutral"),
        "today_theme": program.get("today_theme", "今晚"),
        "day_period": env.get("day_period", "unknown"),
        "user_nickname": user.get("nickname", ""),
        "user_mood": env.get("user_mood", ""),
        "user": user,
        "environment": env,
    }

    # 调 DJHostService
    refs = state.get("__refs__") or {}
    dj_host = refs.get("dj_host_service")
    if not dj_host:
        logger.warning("DJ Host: dj_host_service not injected in __refs__")
        return {"pending_payload": None, "should_speak": False, "next_node": "action_planner"}

    try:
        text = await dj_host.generate_speech(context)
    except Exception as e:
        logger.error("DJ Host: service error: %s", e)
        return {"pending_payload": None, "should_speak": False, "next_node": "action_planner"}

    if not text:
        logger.debug("DJ Host: empty speech (L4 silent fallback)")
        return {"pending_payload": None, "should_speak": False, "next_node": "action_planner"}

    # 更新 RuntimeDJState 追踪
    if rds:
        rds["last_dj_speech_at_ms"] = int(time.time() * 1000)
        rds["last_dj_speech_song_id"] = current_song_id

    logger.info("DJ Host: generated speech (%d chars) for song=%s", len(text), current_song_id)
    return {
        "pending_payload": {
            "dj_speech": {
                "text": text,
                "mood": snapshot.get("program_mood", "neutral"),
                "source": "dj_host",
            },
        },
        "should_speak": True,
        "should_play_music": bool(next_song is not None),
        "next_node": "action_planner",
    }
