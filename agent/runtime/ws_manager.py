"""ConnectionManager — WebSocket 连接管理。

管理 WS 连接集合，提供 broadcast 能力，跟踪心跳时间。
Graph Node 不直接碰 WebSocket；经 ws_out_queue → sender task → ConnectionManager.broadcast。
"""

import asyncio
import logging
import time

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """管理所有 WS 连接。"""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._last_pong: dict[WebSocket, float] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        now = time.time()
        async with self._lock:
            self._connections.add(ws)
            self._last_pong[ws] = now
        logger.info("WS client connected (%d total)", len(self._connections))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)
            self._last_pong.pop(ws, None)
        logger.info("WS client disconnected (%d remaining)", len(self._connections))

    def record_pong(self, ws: WebSocket):
        """记录客户端 pong 时间戳（从 ws_handler 调用，单 task 安全）。"""
        self._last_pong[ws] = time.time()

    async def broadcast(self, message: dict):
        """广播 JSON 消息给所有连接。发送失败的连接自动移除。"""
        async with self._lock:
            dead: set[WebSocket] = set()
            for ws in self._connections:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.add(ws)
            if dead:
                for ws in dead:
                    self._connections.discard(ws)
                    self._last_pong.pop(ws, None)
                logger.info("Removed %d dead WS connections (%d remain)", len(dead), len(self._connections))

    async def disconnect_stale(self, timeout_s: float = 60.0) -> int:
        """断开超过 timeout_s 未收到 pong 的连接。返回断开数。

        ★ v8.2：必须关闭底层 WebSocket，否则前端以为连接还在，后端广播却收不到。
        """
        now = time.time()
        async with self._lock:
            stale = [ws for ws in list(self._connections) if now - self._last_pong.get(ws, now) > timeout_s]
            for ws in stale:
                self._connections.discard(ws)
                self._last_pong.pop(ws, None)
        # ★ 真正关闭底层 WS 触发前端 onclose → 自动重连
        for ws in stale:
            try:
                await ws.close(code=1000, reason="heartbeat timeout")
            except Exception:
                pass
        if stale:
            logger.info("Disconnected %d stale WS connections (%d remain)", len(stale), len(self._connections))
        return len(stale)

    @property
    def active_count(self) -> int:
        return len(self._connections)


connection_manager = ConnectionManager()
