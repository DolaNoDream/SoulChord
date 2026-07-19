"""feedback_extractor 节点 — 处理用户反馈事件（user_like/dislike/skip/play_end）。

★ v0.6 D 项：song_finished 不进此节点
★ v0.1.2 P0-1：return dict（partial update）
★ 输出给 action_planner：feedback_record
"""

import logging
import time

from agent.state.state_manager import state_manager

logger = logging.getLogger(__name__)


async def feedback_extractor_node(state: dict) -> dict:
    """处理 player_event 反馈事件，写 Memory，返回 feedback_record。"""
    trigger_event = state.get("trigger_event", {}) or {}
    subtype = trigger_event.get("subtype", "")
    song = trigger_event.get("song") or {}
    song_id = song.get("song_id") or trigger_event.get("song_id")

    if not song_id:
        logger.warning("feedback_extractor: missing song_id in trigger_event")
        return {
            "feedback_record": None,
            "last_error": {"code": "MISSING_SONG_ID", "msg": "No song_id in trigger_event"},
        }

    now_ms = int(time.time() * 1000)

    if subtype == "user_like":
        return await _record_feedback(song_id, "like", 1.0, now_ms)
    elif subtype == "user_dislike":
        return await _record_feedback(song_id, "dislike", 1.0, now_ms)
    elif subtype in ("user_skip", "skip"):
        return await _record_feedback(song_id, "skip", 1.0, now_ms)
    elif subtype == "play_end":
        return await _handle_play_end(song_id, trigger_event, now_ms)
    else:
        logger.warning("feedback_extractor: unhandled subtype=%s", subtype)
        return {"feedback_record": None, "last_error": {"code": "UNHANDLED_SUBTYPE", "subtype": subtype}}


async def _record_feedback(song_id: str, action: str, confidence: float, now_ms: int) -> dict:
    """写入 Memory + 返回 feedback_record。"""
    feedback_key = f"song_{song_id}"
    feedback_value = {
        "action": action,
        "song_id": song_id,
        "confidence": confidence,
        "source": "user_input",
        "ts": now_ms,
    }
    try:
        state_manager.memory.write("feedback", feedback_key, feedback_value, ttl_s=None)
    except Exception as e:
        logger.warning("feedback_extractor: memory.write failed: %s", e)
        return {
            "feedback_record": None,
            "last_error": {"code": "MEMORY_WRITE_FAILED", "msg": str(e)},
        }

    return {
        "feedback_record": {
            "action": action,
            "song_id": song_id,
            "confidence": confidence,
            "source": "user_input",
        },
    }


async def _handle_play_end(song_id: str, trigger_event: dict, now_ms: int) -> dict:
    """play_end 推断 like / skip。

    按 played_ms / duration_ms 比值：
      ≥ 0.8 → like
      < 0.3 → skip
      0.3-0.8 → 中性，不写
    """
    played_ms = trigger_event.get("played_ms", 0)
    duration_ms = trigger_event.get("duration_ms", 0)

    if duration_ms <= 0:
        return {"feedback_record": None}

    ratio = played_ms / duration_ms
    if ratio >= 0.8:
        return await _record_feedback(song_id, "like", ratio, now_ms)
    elif ratio < 0.3:
        return await _record_feedback(song_id, "skip", 1.0 - ratio, now_ms)
    else:
        # 中性区间，不写 Memory
        return {"feedback_record": {"action": "neutral", "song_id": song_id, "confidence": ratio}}
