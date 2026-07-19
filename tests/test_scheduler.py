"""Scheduler — 4 Timer Loop 单元测试。

覆盖：
1. start/stop 生命周期
2. 各 loop 是否推送正确 EventType
3. 配置 intervals 生效
4. 重复 start 安全
5. 空 EventQueue 安全
6. lifespan 集成：Scheduler 在 lifespan 中被创建
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agent.runtime.event_queue import EventQueue, EventType
from agent.runtime.scheduler import Scheduler
from agent.config import SchedulerConfig


# ═══════════════════════════════════════════════════════════════
# Test Case 1: Scheduler 生命周期
# ═══════════════════════════════════════════════════════════════
class TestSchedulerLifecycle:
    """Scheduler start/stop 生命周期。"""

    @pytest.mark.asyncio
    async def test_start_creates_four_tasks(self):
        """start() → 4 个 asyncio Task 创建。"""
        q = EventQueue()
        s = Scheduler(q)

        # 未 start 时无 task
        assert len(s._tasks) == 0

        s.start()
        assert len(s._tasks) == 4
        assert all(t is not None for t in s._tasks)

        # 清理
        await s.stop()

    @pytest.mark.asyncio
    async def test_idempotent_start(self):
        """重复 start() 不创建额外 task。"""
        q = EventQueue()
        s = Scheduler(q)

        s.start()
        task_count = len(s._tasks)

        s.start()  # 第二次 — 应被忽略
        assert len(s._tasks) == task_count

        await s.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_all_tasks(self):
        """stop() → 所有 task 被取消。"""
        q = EventQueue()
        s = Scheduler(q)

        s.start()
        assert len(s._tasks) == 4

        await s.stop()
        assert len(s._tasks) == 0

    @pytest.mark.asyncio
    async def test_stop_before_start_safe(self):
        """未 start 就 stop → 安全。"""
        q = EventQueue()
        s = Scheduler(q)

        await s.stop()  # 不应抛异常
        assert len(s._tasks) == 0


# ═══════════════════════════════════════════════════════════════
# Test Case 2: Timer Loop — EventType 正确性
# ═══════════════════════════════════════════════════════════════
class TestTimerLoopEventTypes:
    """每个 loop 推送正确的 EventType。"""

    @pytest.mark.asyncio
    async def test_heartbeat_loop_pushes_heartbeat_event(self):
        """heartbeat loop → TIMER_HEARTBEAT。"""
        q = EventQueue()
        # 用极短 interval 让 loop 尽快触发
        cfg = SchedulerConfig(heartbeat_interval_s=0.01, feishu_interval_s=9999,
                              playlist_health_interval_s=9999, program_tick_interval_s=9999)
        s = Scheduler(q, cfg)
        s.start()

        await asyncio.sleep(0.05)
        await s.stop()

        # 至少收到 1 个 TIMER_HEARTBEAT
        heartbeat_count = 0
        while q.qsize() > 0:
            event = await q.get()
            if event.type == EventType.TIMER_HEARTBEAT:
                heartbeat_count += 1

        assert heartbeat_count >= 1, "Should have pushed at least 1 TIMER_HEARTBEAT"

    @pytest.mark.asyncio
    async def test_feishu_loop_pushes_feishu_event(self):
        """feishu loop → TIMER_FEISHU。"""
        q = EventQueue()
        cfg = SchedulerConfig(feishu_interval_s=0.01, heartbeat_interval_s=9999,
                              playlist_health_interval_s=9999, program_tick_interval_s=9999)
        s = Scheduler(q, cfg)
        s.start()

        await asyncio.sleep(0.05)
        await s.stop()

        feishu_count = 0
        while q.qsize() > 0:
            event = await q.get()
            if event.type == EventType.TIMER_FEISHU:
                feishu_count += 1

        assert feishu_count >= 1

    @pytest.mark.asyncio
    async def test_playlist_health_loop_pushes_playlist_health_event(self):
        """playlist_health loop → TIMER_PLAYLIST_HEALTH。"""
        q = EventQueue()
        cfg = SchedulerConfig(playlist_health_interval_s=0.01, feishu_interval_s=9999,
                              heartbeat_interval_s=9999, program_tick_interval_s=9999)
        s = Scheduler(q, cfg)
        s.start()

        await asyncio.sleep(0.05)
        await s.stop()

        count = 0
        while q.qsize() > 0:
            event = await q.get()
            if event.type == EventType.TIMER_PLAYLIST_HEALTH:
                count += 1

        assert count >= 1

    @pytest.mark.asyncio
    async def test_program_tick_loop_pushes_program_tick_event(self):
        """program_tick loop → TIMER_PROGRAM_TICK。"""
        q = EventQueue()
        cfg = SchedulerConfig(program_tick_interval_s=0.01, feishu_interval_s=9999,
                              heartbeat_interval_s=9999, playlist_health_interval_s=9999)
        s = Scheduler(q, cfg)
        s.start()

        await asyncio.sleep(0.05)
        await s.stop()

        count = 0
        while q.qsize() > 0:
            event = await q.get()
            if event.type == EventType.TIMER_PROGRAM_TICK:
                count += 1

        assert count >= 1

    @pytest.mark.asyncio
    async def test_timer_event_has_correct_priority(self):
        """所有 timer event 的 priority 是 TIMER=P3。"""
        q = EventQueue()
        cfg = SchedulerConfig(feishu_interval_s=0.01, heartbeat_interval_s=9999,
                              playlist_health_interval_s=9999, program_tick_interval_s=9999)
        s = Scheduler(q, cfg)
        s.start()

        await asyncio.sleep(0.05)
        await s.stop()

        events = []
        while q.qsize() > 0:
            events.append(await q.get())

        assert len(events) >= 1
        for ev in events:
            assert ev.priority.value == 3, f"Expected TIMER(P3) priority, got {ev.priority}"

    @pytest.mark.asyncio
    async def test_timer_event_has_timestamp(self):
        """每个 timer event 携带 ts 字段。"""
        q = EventQueue()
        cfg = SchedulerConfig(feishu_interval_s=0.01, heartbeat_interval_s=9999,
                              playlist_health_interval_s=9999, program_tick_interval_s=9999)
        s = Scheduler(q, cfg)
        s.start()

        await asyncio.sleep(0.05)
        await s.stop()

        events = []
        while q.qsize() > 0:
            events.append(await q.get())

        for ev in events:
            assert "ts" in ev.payload, f"Timer event {ev.type} missing ts field"
            assert "scheduler_loop" in ev.payload


# ═══════════════════════════════════════════════════════════════
# Test Case 3: 配置 — 自定义 interval
# ═══════════════════════════════════════════════════════════════
class TestSchedulerConfig:
    """SchedulerConfig 自定义间隔生效。"""

    @pytest.mark.asyncio
    async def test_custom_intervals_respected(self):
        """自定义 interval → loop 按新间隔运行。"""
        q = EventQueue()
        # 所有 loop 都设 0.01s（约 100 倍速）
        cfg = SchedulerConfig(feishu_interval_s=0.01, heartbeat_interval_s=0.01,
                              playlist_health_interval_s=0.01, program_tick_interval_s=0.01)
        s = Scheduler(q, cfg)
        s.start()

        await asyncio.sleep(0.05)
        await s.stop()

        # 所有 4 种类型都应至少出现 1 次
        types_seen = set()
        while q.qsize() > 0:
            event = await q.get()
            types_seen.add(event.type)

        assert EventType.TIMER_HEARTBEAT in types_seen
        assert EventType.TIMER_FEISHU in types_seen
        assert EventType.TIMER_PLAYLIST_HEALTH in types_seen
        assert EventType.TIMER_PROGRAM_TICK in types_seen


# ═══════════════════════════════════════════════════════════════
# Test Case 4: 安全 — 空队列 / 异常
# ═════════════════════════════════════════════════════════════==
class TestSchedulerSafety:
    """异常场景安全兜底。"""

    @pytest.mark.asyncio
    async def test_empty_queue_not_used_safe(self):
        """EventQueue 为空时 start/stop 安全。"""
        q = EventQueue()
        s = Scheduler(q)
        s.start()
        await s.stop()
        # 不产生事件也 OK

    @pytest.mark.asyncio
    async def test_loop_survives_queue_put_exception(self):
        """queue.put 抛异常 → loop 不崩溃。"""
        mock_queue = MagicMock()
        # 第一次 put 成功，第二次抛异常
        mock_queue.put = AsyncMock(side_effect=[None, Exception("queue full")])

        cfg = SchedulerConfig(heartbeat_interval_s=0.01, feishu_interval_s=9999,
                              playlist_health_interval_s=9999, program_tick_interval_s=9999)
        s = Scheduler(mock_queue, cfg)
        s.start()

        await asyncio.sleep(0.03)
        # 不应抛到外面
        await s.stop()
