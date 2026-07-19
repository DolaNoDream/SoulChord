"""Scheduler — 4 个 Timer Loop 周期推事件到 EventQueue。

★ v0.6 A 项：Scheduler 在 Dispatcher 之后 start（避免事件来了 Graph 没准备好）
★ H15：4 Timer Loop：
  - feishu（5 min 轮询飞书日程）
  - heartbeat（30s 系统心跳 → system trigger → emit_response）
  - playlist_health（10 min 检查播放队列健康）
  - program_tick（30 min 节目时段切换）
★ H17：Scheduler program_tick = 驱动 Program State（不是健康检查）
"""

import asyncio
import logging
import time
from typing import Optional

from agent.config import SchedulerConfig
from agent.runtime.event_queue import Event, EventQueue
from agent.shared.enums import EventType

logger = logging.getLogger(__name__)


class Scheduler:
    """4 个 Timer Loop 周期推事件到 EventQueue。

    每个 Loop 是一个独立的 asyncio Task，通过 SchedulerConfig 配置间隔。
    start() 在 lifespan Step 7 调用（Dispatcher 之后）。
    """

    def __init__(self, event_queue: EventQueue, config: Optional[SchedulerConfig] = None):
        self._queue = event_queue
        self._config = config or SchedulerConfig()
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def start(self):
        """启动所有 4 个 Timer Loop（非阻塞，创建后台 Task）。"""
        if self._running:
            logger.warning("Scheduler already running")
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._loop("feishu", self._config.feishu_interval_s, EventType.TIMER_FEISHU)),
            asyncio.create_task(self._loop("heartbeat", self._config.heartbeat_interval_s, EventType.TIMER_HEARTBEAT)),
            asyncio.create_task(self._loop("playlist_health", self._config.playlist_health_interval_s, EventType.TIMER_PLAYLIST_HEALTH)),
            asyncio.create_task(self._loop("program_tick", self._config.program_tick_interval_s, EventType.TIMER_PROGRAM_TICK)),
        ]
        logger.info("Scheduler started: 4 timer loops (feishu=%ss, heartbeat=%ss, playlist_health=%ss, program_tick=%ss)",
                     self._config.feishu_interval_s, self._config.heartbeat_interval_s,
                     self._config.playlist_health_interval_s, self._config.program_tick_interval_s)

    async def stop(self):
        """停止所有 Timer Loop。"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Scheduler stopped")

    async def _loop(self, name: str, interval_s: int, event_type: EventType):
        """单个 Timer Loop：sleep → push event → repeat。"""
        logger.info("Scheduler loop %s started (interval=%ss)", name, interval_s)
        while self._running:
            try:
                await asyncio.sleep(interval_s)
                if not self._running:
                    break
                event = Event.from_timer(event_type, {
                    "ts": int(time.time() * 1000),
                    "scheduler_loop": name,
                })
                await self._queue.put(event)
                logger.debug("Scheduler pushed %s (loop=%s)", event_type.value, name)
            except asyncio.CancelledError:
                logger.info("Scheduler loop %s cancelled", name)
                break
            except Exception as e:
                logger.error("Scheduler loop %s error: %s", name, e)
        logger.info("Scheduler loop %s stopped", name)
