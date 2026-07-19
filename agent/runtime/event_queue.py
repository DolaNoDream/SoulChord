"""异步 PriorityQueue EventQueue + Event / EventType。

★ v0.6 B 项：Priority P0/P1/P3 显式编号。
P0=USER（最高）/ P1=SYSTEM / P3=TIMER（最低）
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.shared.enums import EventType, EventPriority


@dataclass(order=True)
class Event:
    """事件体。

    priority 决定排队顺序（低值 = 高优先）。
    """
    priority: EventPriority
    timestamp_ms: int = field(compare=False)
    type: EventType = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)

    @classmethod
    def from_user(cls, event_type: EventType, payload: dict) -> "Event":
        """构造用户触发事件（Priority=USER=P0）。"""
        return cls(
            priority=EventPriority.USER,
            timestamp_ms=int(time.time() * 1000),
            type=event_type,
            payload=payload,
        )

    @classmethod
    def from_system(cls, event_type: EventType, payload: dict) -> "Event":
        """构造系统事件（Priority=SYSTEM=P1）。"""
        return cls(
            priority=EventPriority.SYSTEM,
            timestamp_ms=int(time.time() * 1000),
            type=event_type,
            payload=payload,
        )

    @classmethod
    def from_timer(cls, event_type: EventType, payload: dict) -> "Event":
        """构造定时事件（Priority=TIMER=P3）。"""
        return cls(
            priority=EventPriority.TIMER,
            timestamp_ms=int(time.time() * 1000),
            type=event_type,
            payload=payload,
        )

    def to_dict(self) -> dict:
        return {
            "priority": self.priority.value,
            "timestamp_ms": self.timestamp_ms,
            "type": self.type.value,
            "payload": self.payload,
        }


class EventQueue:
    """asyncio.PriorityQueue 封装。"""

    def __init__(self, maxsize: int = 1000):
        self._queue: asyncio.PriorityQueue[Event] = asyncio.PriorityQueue(maxsize=maxsize)

    async def put(self, event: Event):
        await self._queue.put(event)

    async def get(self) -> Event:
        return await self._queue.get()

    def put_nowait(self, event: Event):
        self._queue.put_nowait(event)

    def qsize(self) -> int:
        return self._queue.qsize()
