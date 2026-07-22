"""WS handler — FastAPI WebSocket 端点 + 消息分发。

前端消息 → EventQueue + player_mirror 写入。
Graph 推理结果经 ws_out_queue → ConnectionManager broadcast（在 ws_sender.py）。

消息协议（Phase 1 + Phase 2-lite）：
  chat.user_text       → EventQueue CHAT_SEND
  chat.voice_text      → EventQueue VOICE_TEXT
  player_event.*       → player_mirror 更新 + EventQueue 对应 EventType
  heartbeat.ping       → 回复 pong（Phase 1）
  heartbeat.pong       → 记录 pong 时间（Phase 2-lite 服务端心跳检测）
"""

import logging
import time
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from agent.runtime.event_queue import Event, EventType
from agent.runtime.ws_manager import connection_manager
from agent.runtime.ws_sender import build_welcome, build_music_play, enqueue_or_drop
from agent.state.player_state import update_player_event, load_player_mirror

logger = logging.getLogger(__name__)

# ── player_event subtype → EventType 映射 ──
_PLAYER_EVENT_MAP = {
    "play_start": EventType.PLAYER_SONG_STARTED,  # 前端 play_start → 内部 song_started
    "song_started": EventType.PLAYER_SONG_STARTED,
    "song_progress": EventType.PLAYER_SONG_PROGRESS,
    "song_finished": EventType.PLAYER_SONG_FINISHED,
    "user_like": EventType.PLAYER_USER_LIKE,
    "user_dislike": EventType.PLAYER_USER_DISLIKE,
    "user_skip": EventType.PLAYER_USER_SKIP,
    "play_end": EventType.PLAYER_PLAY_END,
    # 前端 player controls — 映射到已有 EventType 供 feedback_extractor 处理
    "skip": EventType.PLAYER_USER_SKIP,      # 前端 next 按钮 → skip
    "pause": EventType.PLAYER_SONG_PROGRESS,  # 暂停只是状态更新，不触发切歌
    "resume": EventType.PLAYER_SONG_STARTED, # 记录恢复播放
}


async def handle_ws_connection(ws: WebSocket, event_queue, runtime_dj_state: dict = None):
    """处理单个 WS 连接生命周期。"""
    await connection_manager.connect(ws)

    # 推送 welcome
    session_id = str(uuid.uuid4())
    await ws.send_json(build_welcome(session_id))
    logger.info("WS welcome sent: session=%s", session_id)

    # ★ 从 player_mirror 恢复缓存的音乐播放状态。
    #   INIT 流程完成时机早于前端 WS 连接，其 WS 消息会被弃。
    #   此处从 mirror 中读取已保存的 current_song + play_url 补发 music.play。
    _send_cached_music_play(ws)

    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "")
            msg_subtype = raw.get("subtype", "")
            payload = raw.get("payload", {})
            msg_id = raw.get("id", "")

            if msg_type == "chat":
                await _handle_chat(event_queue, msg_subtype, payload, msg_id, runtime_dj_state)
            elif msg_type == "player_event":
                logger.debug("WS player_event at top-level type, prefer status.player_event")
                await _handle_player_event(event_queue, msg_subtype, payload, runtime_dj_state)
            elif msg_type == "status" and msg_subtype == "player_event":
                await _handle_player_event(event_queue, payload.get("event", ""), payload, runtime_dj_state)
            elif msg_type == "heartbeat":
                if msg_subtype == "ping":
                    # ★ v8.2：前端每 30s 发 ping，将其视为心跳避免 60s 后被断
                    connection_manager.record_pong(ws)
                    await _send_pong(ws)
                elif msg_subtype == "pong":
                    connection_manager.record_pong(ws)
                else:
                    logger.debug("Ignored heartbeat subtype=%s", msg_subtype)
            else:
                logger.debug("Ignored WS message: type=%s subtype=%s", msg_type, msg_subtype)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WS handler error: %s", e)
    finally:
        await connection_manager.disconnect(ws)


# ── 消息处理器 ──


async def _handle_chat(event_queue, subtype: str, payload: dict, msg_id: str, runtime_dj_state: dict = None):
    """chat.user_text / chat.voice_text → EventQueue。"""
    text = payload.get("text", "")
    if not text:
        logger.warning("Empty chat text ignored")
        return

    if subtype == "voice_text":
        event_type = EventType.VOICE_TEXT
    else:
        event_type = EventType.CHAT_SEND

    # ★ P0-2: 用户聊天 → 设置中断标记，后续 play_end 将跳过自动推进
    if runtime_dj_state:
        runtime_dj_state["pending_user_interrupt"] = True
        logger.debug("pending_user_interrupt set (chat)")

    event = Event.from_user(event_type, {
        "text": text,
        "subtype": subtype,
        "msg_id": msg_id,
        "confidence": payload.get("confidence", 1.0),
    })
    await event_queue.put(event)
    logger.info("WS chat enqueued: type=%s text=%.60s", event_type.value, text)


async def _handle_player_event(event_queue, subtype: str, payload: dict, runtime_dj_state: dict = None):
    """player_event.* → player_mirror + EventQueue。"""
    internal_type = _PLAYER_EVENT_MAP.get(subtype)
    if internal_type is None:
        logger.warning("Unknown player_event subtype=%s", subtype)
        return

    # ★ play_start → 同步更新 RDS current_song + 触发 DJ 介绍新歌
    #   重复 play_start（同一首歌发两次）只推送一次 DJ_MONOLOGUE，防止双 DJ 话术
    #   ★ P0-2: pending_user_interrupt 时跳过 DJ_MONOLOGUE（但仍更新 RDS.current_song）
    #   ★ v9.12 fix: RDS.current_song 必须更新 — play_start 是前端确认播放的唯一信号，
    #     跳过会导致 RDS.current_song 与实际播放不同步，影响后续 divergence check
    if subtype == "play_start" and runtime_dj_state is not None:
        song_id = payload.get("song_id", "")
        if song_id:
            _is_new_song = False
            current = runtime_dj_state.get("current_song") or {}
            if current.get("song_id") != song_id:
                runtime_dj_state["current_song"] = {
                    "song_id": song_id,
                    "name": payload.get("song_name", current.get("name", "")),
                    "artist": payload.get("song_artist", current.get("artist", "")),
                }
                _is_new_song = True
                logger.debug("RDS current_song updated via play_start: %s", song_id)

            # ★ DJ_MONOLOGUE：pending_user_interrupt 时跳过（用户说话时 DJ 不该插嘴）
            if _is_new_song and not runtime_dj_state.get("pending_user_interrupt"):
                dj_event = Event.from_system(EventType.DJ_MONOLOGUE, {
                    "song_id": song_id,
                    "trigger": "play_start",
                    "song_name": payload.get("song_name", ""),
                    "song_artist": payload.get("song_artist", ""),
                    "ts": int(time.time() * 1000),
                })
                await event_queue.put(dj_event)
                runtime_dj_state["last_play_start_dj_ts"] = int(time.time() * 1000)
                logger.info("WS pushed DJ_MONOLOGUE for play_start: song=%s", song_id)
            elif _is_new_song and runtime_dj_state.get("pending_user_interrupt"):
                logger.debug("play_start DJ_MONOLOGUE skipped: pending_user_interrupt set")
            else:
                logger.debug("play_start: song=%s already playing (duplicate play_start, skip)", song_id)

    # 写 player_mirror
    mirror_ok = update_player_event({"subtype": subtype, **payload})
    if not mirror_ok:
        logger.warning("player_mirror write failed for subtype=%s", subtype)

    # 推 EventQueue
    event = Event.from_system(internal_type, {"subtype": subtype, **payload})
    await event_queue.put(event)
    logger.info("WS player_event enqueued: %s", subtype)

    # ★ DJ 话术触发：song_progress ≥ 85% 时推 DJ_MONOLOGUE
    if subtype == "song_progress":
        progress = payload.get("progress", payload.get("position_ratio", 0))
        if isinstance(progress, (int, float)) and progress >= 0.85:
            song_id = payload.get("song_id", "")
            dj_event = Event.from_system(EventType.DJ_MONOLOGUE, {
                "song_id": song_id,
                "progress": progress,
                "trigger": "song_progress",
                "ts": int(time.time() * 1000),
            })
            await event_queue.put(dj_event)
            logger.info("WS pushed DJ_MONOLOGUE (progress=%.0f%% song=%s)", progress * 100, song_id)


async def _send_pong(ws: WebSocket):
    """heartbeat.ping → pong。"""
    await ws.send_json({
        "type": "heartbeat",
        "subtype": "pong",
        "ts": int(time.time() * 1000),
    })


def _send_cached_music_play(ws: WebSocket):
    """从 player_mirror 恢复缓存的 music.play（如有）。

    INIT 流程的 WS 消息早于前端连接，被静默丢弃。
    action_executor 已将播放状态持久化到 player_mirror.json，
    此处补发 music.play 消息，使前端可从 INIT 歌曲开始播放。
    """
    try:
        mirror = load_player_mirror()
        if not mirror:
            return
        current_song = mirror.get("current_song")
        play_url = mirror.get("play_url", "")
        if not current_song or not play_url:
            return
        msg = build_music_play(
            current_song,
            play_url,
            auto_play=True,
            reason="cached_from_init",
        )
        import asyncio
        asyncio.ensure_future(ws.send_json(msg))
        logger.info("WS sent cached music.play: song=%s", current_song.get("name", "?"))
    except Exception as e:
        logger.warning("Failed to send cached music.play: %s", e)
