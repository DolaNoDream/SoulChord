"""WS 异步发送 — ws_out_queue → ConnectionManager.broadcast。

Graph Node 不直接碰 WebSocket。经 ws_out_queue → sender task → broadcast。

两个后台循环：
  ws_sender_loop    — 消费 ws_out_queue 并 broadcast
  ws_heartbeat_loop — 服务端主动 ping（每 30s），断开 60s 无响应的客户端
"""

import asyncio
import logging

from agent.runtime.ws_manager import connection_manager

logger = logging.getLogger(__name__)

# 消息队列：Node 侧用 put_nowait，sender task 侧用 get
ws_out_queue: asyncio.Queue = asyncio.Queue(maxsize=500)

# 心跳间隔（秒）
HEARTBEAT_INTERVAL_S = 30
HEARTBEAT_TIMEOUT_S = 60


async def ws_sender_loop():
    """后台任务：消费 ws_out_queue → ConnectionManager.broadcast。"""
    logger.info("WS sender loop started")
    while True:
        try:
            msg = await ws_out_queue.get()
            await connection_manager.broadcast(msg)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("WS sender loop error: %s", e)
    logger.info("WS sender loop stopped")


async def ws_heartbeat_loop():
    """后台任务：服务端主动心跳检测。

    每 HEARTBEAT_INTERVAL_S（30s）广播 ping 给所有客户端，
    断开 HEARTBEAT_TIMEOUT_S（60s）无响应的连接。
    """
    logger.info("WS heartbeat loop started (interval=%ss, timeout=%ss)", HEARTBEAT_INTERVAL_S, HEARTBEAT_TIMEOUT_S)
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            if connection_manager.active_count == 0:
                continue
            # 广播 ping
            await connection_manager.broadcast({
                "type": "heartbeat",
                "subtype": "ping",
                "ts": _now_ms(),
            })
            # 断开超时连接
            await connection_manager.disconnect_stale(timeout_s=HEARTBEAT_TIMEOUT_S)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("WS heartbeat loop error: %s", e)
    logger.info("WS heartbeat loop stopped")


def enqueue_or_drop(msg: dict):
    """非阻塞入队；队列满时丢弃（日志警告）。"""
    try:
        ws_out_queue.put_nowait(msg)
    except asyncio.QueueFull:
        logger.warning("ws_out_queue full, dropping message: type=%s", msg.get("type"))


# ── 消息构建工具 ──


def build_welcome(session_id: str) -> dict:
    """status.welcome — 连接建立后推送。"""
    return {
        "type": "status",
        "subtype": "welcome",
        "ts": _now_ms(),
        "payload": {
            "session_id": session_id,
            "server_ts": _now_ms(),
            "agent": {"version": "0.2.0", "persona": "night_dj"},
        },
    }


def build_chat_reply(reply: str, **extra) -> dict:
    """chat.reply — Agent 回复。"""
    return {
        "type": "chat",
        "subtype": "reply",
        "ts": _now_ms(),
        "payload": {"text": reply, **extra},
    }


def build_music_play(song: dict, play_url: str, **kwargs) -> dict:
    """music.play — 播放歌曲指令。"""
    return {
        "type": "music",
        "subtype": "play",
        "ts": _now_ms(),
        "payload": {"song": song, "play_url": play_url, **kwargs},
    }


def build_tts_synthesize(text: str, **extra) -> dict:
    """tts.synthesize — DJ 语音合成。"""
    return {
        "type": "tts",
        "subtype": "synthesize",
        "ts": _now_ms(),
        "payload": {
            "text": text,
            "audio_url": "",
            "audio_duration_ms": 0,
            "voice": extra.pop("voice", "male_gentle"),
            "expression": extra.pop("expression", "talking"),
            **extra,
        },
    }


def build_error(code: int, msg: str, *, recoverable: bool = True, related_id: str = "") -> dict:
    """error — Agent 内部错误推送。"""
    return {
        "type": "error",
        "ts": _now_ms(),
        "payload": {
            "code": code,
            "msg": msg,
            "recoverable": recoverable,
            "related_id": related_id,
        },
    }


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)
