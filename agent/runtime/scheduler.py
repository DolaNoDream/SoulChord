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

    def __init__(self, event_queue: EventQueue, config: Optional[SchedulerConfig] = None, runtime_dj_state: Optional[dict] = None):
        self._queue = event_queue
        self._config = config or SchedulerConfig()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._runtime_dj_state = runtime_dj_state
        self._dj_speech_interval_s = getattr(config, 'speech_interval_s', 120) if config else 120

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
                    "timer_type": name,
                })
                await self._queue.put(event)
                logger.debug("Scheduler pushed %s (loop=%s)", event_type.value, name)

                # ★ DJ backstop：heartbeat 循环检查是否需要推 DJ_MONOLOGUE
                if name == "heartbeat":
                    await self._check_dj_monologue_backstop()
            except asyncio.CancelledError:
                logger.info("Scheduler loop %s cancelled", name)
                break
            except Exception as e:
                logger.error("Scheduler loop %s error: %s", name, e)
        logger.info("Scheduler loop %s stopped", name)

    async def _check_dj_monologue_backstop(self):
        """检查是否需要推 DJ_MONOLOGUE 兜底事件。

        条件（全部满足）：
          1. 有 current_song
          2. current_song_id ≠ last_dj_speech_song_id（尚未为此歌曲生成话术）
          3. 距上次说话 > speech_interval_s

        注意：此方法只在 heartbeat 循环中被调用（30s 间隔）。
        """
        rds = self._runtime_dj_state
        if not rds:
            return

        current_song = rds.get("current_song")
        if not current_song:
            return

        song_id = current_song.get("song_id") or current_song.get("id", "")
        if not song_id:
            return

        last_speech_song = rds.get("last_dj_speech_song_id", "")
        last_speech_at = rds.get("last_dj_speech_at_ms", 0)
        now_ms = int(time.time() * 1000)

        # ★ 防止与 ws_handler play_start 触发的 DJ_MONOLOGUE 竞态：
        #   如果 play_start 刚推过 DJ_MONOLOGUE（< 30s 内），backstop 跳过
        last_play_start_dj_ts = rds.get("last_play_start_dj_ts", 0)
        if now_ms - last_play_start_dj_ts < 30000:
            logger.debug("Scheduler backstop skip: play_start DJ pushed %dms ago",
                         now_ms - last_play_start_dj_ts)
            return

        # ★ 首次说话（last_speech_at_ms==0）用短冷却 5s，之后用配置的 speech_interval_s
        cooldown_ms = 5000 if last_speech_at == 0 else self._dj_speech_interval_s * 1000
        if (song_id != last_speech_song
                and now_ms - last_speech_at > cooldown_ms):
            from agent.shared.enums import EventType as ET
            backstop_event = Event.from_timer(ET.DJ_MONOLOGUE, {
                "song_id": song_id,
                "trigger": "scheduler_backstop",
                "ts": now_ms,
            })
            await self._queue.put(backstop_event)
            logger.info("Scheduler backstop: pushed DJ_MONOLOGUE for song=%s", song_id)
