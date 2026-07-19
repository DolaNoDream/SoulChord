"""EventService — 封装 EventQueue 操作。

允许 Graph Node 在 invoke 内向 EventQueue 推新事件（如 REPLAN_REQUEST）。

注意：避免顶层导入 agent.runtime.event_queue（防止循环依赖）。
Event/EventType 在方法内惰性导入。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EventService:
    """事件队列服务。"""

    def __init__(self):
        self._queue = None

    def bind(self, queue):
        """绑定 EventQueue 实例（lifespan 注入）。"""
        self._queue = queue

    async def push_event(self, event_type, payload: dict) -> bool:
        """推一个新事件到队列。"""
        if self._queue is None:
            logger.warning("EventService: queue not bound")
            return False
        try:
            from agent.runtime.event_queue import Event
            event = Event.from_system(event_type, payload)
            await self._queue.put(event)
            return True
        except Exception as e:
            logger.error("EventService.push_event failed: %s", e)
            return False

    async def push_replan(self, reason: str, **extra) -> bool:
        """快捷推 REPLAN_REQUEST 事件。"""
        from agent.shared.enums import EventType
        import time
        payload = {"reason": reason, "ts": int(time.time() * 1000), **extra}
        return await self.push_event(EventType.REPLAN_REQUEST, payload)


event_service = EventService()
