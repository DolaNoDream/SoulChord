"""emit_response 节点 — 构建 WS 消息 → ws_out_queue + error 推送。

★ v0.1.2 P0-1：return dict（partial update），不调 state.update()
职责：
  1. 从 pending_payload 构建 WS 消息（chat.reply / music.play / tts.synthesize）
  2. 从 last_error 构建 error WS 消息
  3. 入队 ws_out_queue（后台 sender task 消费 → ConnectionManager.broadcast）
  4. 更新 turn_count / last_active_at_ms

注意：emit_response.py 内函数使用惰性导入 agent.runtime.ws_sender，
     避免测试导入时触发 agent.runtime.__init__ → graph → emit_response 循环依赖。
"""

import logging
import time

logger = logging.getLogger(__name__)


async def emit_response_node(state: dict) -> dict:
    """根据 pending_payload + last_error 构建 WS 消息并放入 ws_out_queue。

    WS 消息类型：
      - chat.reply（welcome_text / Agent 回复）
      - music.play（first_song / 切歌）
      - tts.synthesize（transition speech TTS 播报）
      - error（LLM 失败 / 工具调用失败等内部错误）
    """
    # 惰性导入避免循环依赖
    from agent.runtime.ws_sender import (
        enqueue_or_drop,
        build_chat_reply,
        build_music_play,
        build_tts_synthesize,
        build_error,
    )

    pending = state.get("pending_payload") or {}
    now_ts = int(time.time() * 1000)

    # ① status.* — 仅日志（welcome 已在连接时由 ws_handler 推送）
    status_update = pending.get("status_update")
    if status_update:
        logger.info("[EMIT] status.%s: mode=%s",
                     status_update.get("type", "unknown"),
                     status_update.get("init_mode"))

    # ② chat.reply
    chat_reply = pending.get("chat_reply")
    if chat_reply:
        msg = build_chat_reply(chat_reply)
        enqueue_or_drop(msg)
        logger.info("[EMIT] chat.reply: %.80s", chat_reply)

    # ③ music.play
    music_play = pending.get("music_play")
    if music_play:
        song = music_play.get("song", {})
        play_url = music_play.get("play_url", "")
        msg = build_music_play(
            song,
            play_url,
            auto_play=music_play.get("auto_play", True),
            reason=music_play.get("reason"),
        )
        enqueue_or_drop(msg)
        logger.info("[EMIT] music.play: %s (auto_play=%s)",
                     song.get("name", "?"), music_play.get("auto_play"))

    # ④ transition speech → tts.synthesize
    ts = pending.get("transition_speech")
    if ts:
        text = ts.get("text", "")
        mood = ts.get("mood", "neutral")
        theme = ts.get("theme", "")
        enqueue_or_drop(build_tts_synthesize(text, voice="warm", mood=mood, theme=theme))
        logger.info("[EMIT] tts.synthesize: %.60s (mood=%s)", text[:60], mood)

    # ⑤ error（Phase 2-lite）
    last_error = state.get("last_error")
    if last_error:
        code_raw = last_error.get("code", 9999)
        code = code_raw if isinstance(code_raw, int) else 9999
        msg = last_error.get("msg") or last_error.get("message") or str(last_error)
        enqueue_or_drop(build_error(code, msg))
        logger.warning("[EMIT] error: code=%s", code)

    turn_count = state.get("turn_count", 0) + 1
    return {
        "turn_count": turn_count,
        "last_active_at_ms": now_ts,
    }
