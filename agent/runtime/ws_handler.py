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
    "pause": EventType.PLAYER_PLAY_END,      # 记录暂停状态
    "resume": EventType.PLAYER_SONG_STARTED, # 记录恢复播放
}


async def handle_ws_connection(ws: WebSocket, event_queue):
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
                await _handle_chat(event_queue, msg_subtype, payload, msg_id)
            elif msg_type == "player_event":
                logger.debug("WS player_event at top-level type, prefer status.player_event")
                await _handle_player_event(event_queue, msg_subtype, payload)
            elif msg_type == "status" and msg_subtype == "player_event":
                await _handle_player_event(event_queue, payload.get("event", ""), payload)
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


async def _handle_chat(event_queue, subtype: str, payload: dict, msg_id: str):
    """chat.user_text / chat.voice_text → EventQueue。"""
    text = payload.get("text", "")
    if not text:
        logger.warning("Empty chat text ignored")
        return

    if subtype == "voice_text":
        event_type = EventType.VOICE_TEXT
    else:
        event_type = EventType.CHAT_SEND

    event = Event.from_user(event_type, {
        "text": text,
        "subtype": subtype,
        "msg_id": msg_id,
        "confidence": payload.get("confidence", 1.0),
    })
    await event_queue.put(event)
    logger.info("WS chat enqueued: type=%s text=%.60s", event_type.value, text)


async def _handle_player_event(event_queue, subtype: str, payload: dict):
    """player_event.* → player_mirror + EventQueue。"""
    internal_type = _PLAYER_EVENT_MAP.get(subtype)
    if internal_type is None:
        logger.warning("Unknown player_event subtype=%s", subtype)
        return

    # 写 player_mirror
    mirror_ok = update_player_event({"subtype": subtype, **payload})
    if not mirror_ok:
        logger.warning("player_mirror write failed for subtype=%s", subtype)

    # 推 EventQueue
    event = Event.from_system(internal_type, {"subtype": subtype, **payload})
    await event_queue.put(event)
    logger.info("WS player_event enqueued: %s", subtype)


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
