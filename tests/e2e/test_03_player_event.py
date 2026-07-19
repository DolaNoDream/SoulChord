"""E2E 冒烟测试 — player_event 链路（含 song_finished 回归断言）。

覆盖：
  1. ws_handler._handle_player_event → EventQueue + player_mirror 更新
  2. song_finished + queue 有歌 → play_song + music.play WS
  3. song_finished + queue 空 → transition speech + REPLAN_REQUEST
     ★ 重点断言：feedback_record is None，memory 未写入，REPLAN 存在
  4. song_started → 最短路 emit
"""

import json
import pytest
from unittest.mock import patch, AsyncMock

from agent.runtime.event_queue import EventType
from agent.runtime.ws_handler import _handle_player_event
from agent.runtime.ws_sender import ws_out_queue
from tests.e2e.conftest import drain_queue, build_initial_state


# ═══════════════════════════════════════════════════════════════
# 1. ws_handler._handle_player_event
# ═══════════════════════════════════════════════════════════════

class TestHandlePlayerEvent:
    """_handle_player_event → EventQueue + player_mirror 更新。"""

    @pytest.mark.asyncio
    async def test_song_started_enqueues_and_mirror(self, e2e_context):
        """song_started → EventQueue 有事件 + player_mirror 更新。"""
        q = e2e_context["event_queue"]
        data_dir = e2e_context["init_data"]

        await _handle_player_event(q, "song_started", {
            "song": {"song_id": "s001", "name": "Test Song", "duration_ms": 200000},
        })

        # EventQueue
        assert q.qsize() == 1
        event = await q.get()
        assert event.type == EventType.PLAYER_SONG_STARTED
        assert event.payload["song"]["song_id"] == "s001"

        # player_mirror.json 更新
        mirror_path = data_dir / "player_mirror.json"
        with open(mirror_path, "r") as f:
            mirror = json.load(f)
        assert mirror.get("current_song", {}).get("song_id") == "s001"

    @pytest.mark.asyncio
    async def test_song_finished_enqueues(self, e2e_context):
        """song_finished → EventQueue 有事件。"""
        q = e2e_context["event_queue"]

        await _handle_player_event(q, "song_finished", {
            "song_id": "s001", "played_ms": 180000, "duration_ms": 200000,
        })

        assert q.qsize() == 1
        event = await q.get()
        assert event.type == EventType.PLAYER_SONG_FINISHED
        assert event.payload["song_id"] == "s001"

    @pytest.mark.asyncio
    async def test_unknown_subtype_ignored(self, e2e_context):
        """未知 subtype → 不入队。"""
        q = e2e_context["event_queue"]

        await _handle_player_event(q, "unknown_type", {})
        assert q.qsize() == 0


# ═══════════════════════════════════════════════════════════════
# 2. song_finished + queue 有歌
# ═══════════════════════════════════════════════════════════════

class TestSongFinishedQueueHasNext:
    """song_finished + playlist_queue 有下一首 → play_song。"""

    @pytest.mark.asyncio
    async def test_song_finished_plays_next_song(self, e2e_context):
        """queue 有歌 → should_play_music=True + music.play WS。"""
        ctx = e2e_context

        state = build_initial_state(
            ctx, trigger_type="player_event",
            trigger_event={"subtype": "song_finished", "song_id": "s001"},
            runtime_snapshot={
                "playlist_queue": [
                    {"song_id": "s002", "name": "下一首", "artist": "Artist"},
                ],
                "program_mood": "warm",
            },
            program={"today_theme": "E2E 测试"},
            actions=[],
        )

        with patch(
            "agent.nodes.action_executor._music.get_play_url",
            new_callable=AsyncMock,
            return_value="https://music.example.com/e2e/s002.mp3",
        ):
            result = await ctx["graph"].ainvoke(state)

        # Graph 结果
        assert result.get("should_play_music") is True, "应播下一首"
        assert result.get("should_speak") is False
        pending = result.get("pending_payload") or {}
        assert pending["music_play"]["song"]["id"] == "s002"
        assert pending["music_play"]["auto_play"] is True

        # feedback_record is None（★ 回归断言）
        assert result.get("feedback_record") is None, \
            "song_finished 不应写 feedback"

        # turn_count
        assert result.get("turn_count", 0) >= 1

        # ws_out_queue 有 music.play
        msgs = drain_queue(ws_out_queue)
        music_msgs = [m for m in msgs
                      if m.get("type") == "music" and m.get("subtype") == "play"]
        assert len(music_msgs) == 1, "queue 有歌时应推 music.play"
        assert music_msgs[0]["payload"]["song"]["id"] == "s002"
        # play_url 由 action_executor enrich
        assert music_msgs[0]["payload"]["play_url"] != ""

    @pytest.mark.asyncio
    async def test_song_finished_no_feedback_written(self, e2e_context):
        """song_finished 后 memory.json feedback 无新增。"""
        ctx = e2e_context
        data_dir = ctx["init_data"]
        mem_path = data_dir / "memory.json"

        # 记录当前 feedback 条目数
        with open(mem_path, "r") as f:
            before = json.load(f)
        feedback_before = len(before.get("feedback", {}))

        state = build_initial_state(
            ctx, trigger_type="player_event",
            trigger_event={"subtype": "song_finished", "song_id": "s001"},
            runtime_snapshot={
                "playlist_queue": [{"song_id": "s002", "name": "Next"}],
                "program_mood": "neutral",
            },
            program={"today_theme": "测试"},
            actions=[],
        )

        with patch(
            "agent.nodes.action_executor._music.get_play_url",
            new_callable=AsyncMock,
            return_value="https://music.example.com/e2e/s002.mp3",
        ):
            await ctx["graph"].ainvoke(state)

        # memory feedback 应无变化
        with open(mem_path, "r") as f:
            after = json.load(f)
        feedback_after = len(after.get("feedback", {}))
        assert feedback_after == feedback_before, \
            "song_finished 不应向 memory.feedback 写任何内容"


# ═══════════════════════════════════════════════════════════════
# 3. song_finished + queue 空 — 重点回归
# ═══════════════════════════════════════════════════════════════

class TestSongFinishedQueueEmpty:
    """song_finished + queue 空 → transition speech + REPLAN_REQUEST。

    ★ 这是当前架构最容易回归的位置（v0.6 D 项 + v0.6.1 E 项）。
    """

    @pytest.mark.asyncio
    async def test_song_finished_queue_empty_transition_speech(self, e2e_context):
        """queue 空 → transition speech + should_speak + 推 REPLAN。"""
        ctx = e2e_context
        q = ctx["event_queue"]

        state = build_initial_state(
            ctx, trigger_type="player_event",
            trigger_event={"subtype": "song_finished", "song_id": "s001"},
            runtime_snapshot={
                "playlist_queue": [],
                "program_mood": "warm",
            },
            program={"today_theme": "晚间测试"},
            actions=[],
        )

        result = await ctx["graph"].ainvoke(state)

        # ── 核心断言（★ 回归点）──

        # transition speech: should_speak=True, actions 含 tts_speak
        assert result.get("should_speak") is True, "queue 空应说 transition speech"
        assert result.get("should_play_music") is False, "不应播歌"

        actions = result.get("actions", [])
        assert len(actions) == 1
        assert actions[0]["type"] == "tts_speak"
        assert "晚间测试" in actions[0]["params"]["text"]

        pending = result.get("pending_payload") or {}
        ts = pending.get("transition_speech") or {}
        assert "text" in ts
        assert ts["source"] == "song_finished_queue_empty"
        assert ts["mood"] == "warm"
        assert "晚间测试" in ts["text"]

        # ★ feedback_record is None（song_finished 不进 feedback_extractor）
        assert result.get("feedback_record") is None

        # ★ REPLAN_REQUEST 已推入 EventQueue
        assert q.qsize() == 1, "应推 REPLAN_REQUEST 到 EventQueue"
        replan_event = await q.get()
        assert replan_event.type == EventType.REPLAN_REQUEST
        assert "queue_empty" in replan_event.payload.get("reason", "")

        # turn_count
        assert result.get("turn_count", 0) >= 1

        # ── ws_out_queue ──
        msgs = drain_queue(ws_out_queue)
        tts_msgs = [m for m in msgs
                    if m.get("type") == "tts" and m.get("subtype") == "synthesize"]
        assert len(tts_msgs) == 1, "应推 tts.synthesize"
        # action_executor 在 Graph internal state 中 enrich 了 audio_url
        ts = result.get("pending_payload", {}).get("transition_speech", {}) or {}
        assert isinstance(ts, dict)
        if ts.get("audio_url"):
            assert ts["audio_url"].startswith("mock://")

    @pytest.mark.asyncio
    async def test_song_finished_queue_empty_no_memory_write(self, e2e_context):
        """queue 空场景：memory.feedback 无新增（feedback_extractor 未经过）。"""
        ctx = e2e_context
        data_dir = ctx["init_data"]
        mem_path = data_dir / "memory.json"

        with open(mem_path, "r") as f:
            before = json.load(f)
        feedback_before = len(before.get("feedback", {}))

        state = build_initial_state(
            ctx, trigger_type="player_event",
            trigger_event={"subtype": "song_finished", "song_id": "s001"},
            runtime_snapshot={
                "playlist_queue": [],
                "program_mood": "reflective",
            },
            program={"today_theme": "深夜"},
            actions=[],
        )

        await ctx["graph"].ainvoke(state)

        with open(mem_path, "r") as f:
            after = json.load(f)
        feedback_after = len(after.get("feedback", {}))
        assert feedback_after == feedback_before, \
            "song_finished queue 空也不应写 feedback"

    @pytest.mark.asyncio
    async def test_song_finished_queue_empty_energetic_mood(self, e2e_context):
        """energetic mood → 对应的 transition speech 模板。"""
        ctx = e2e_context

        state = build_initial_state(
            ctx, trigger_type="player_event",
            trigger_event={"subtype": "song_finished", "song_id": "s001"},
            runtime_snapshot={
                "playlist_queue": [],
                "program_mood": "energetic",
            },
            program={"today_theme": "夜跑"},
            actions=[],
        )

        result = await ctx["graph"].ainvoke(state)

        ts = result["pending_payload"]["transition_speech"]
        assert "夜跑" in ts["text"]
        assert "节奏" in ts["text"] or "旅程" in ts["text"]


# ═══════════════════════════════════════════════════════════════
# 4. song_started → 最短路 emit
# ═══════════════════════════════════════════════════════════════

class TestSongStartedShortestPath:
    """song_started → router → emit_response（最短路）。"""

    @pytest.mark.asyncio
    async def test_song_started_increments_turn_count(self, e2e_context):
        """song_started → turn_count 递增。"""
        ctx = e2e_context

        state = build_initial_state(
            ctx, trigger_type="player_event",
            trigger_event={"subtype": "song_started", "song_id": "s001",
                           "name": "测试歌曲"},
            runtime_snapshot={
                "current_song": {"song_id": "s001", "name": "测试歌曲"},
            },
            turn_count=5,
        )

        result = await ctx["graph"].ainvoke(state)

        assert result.get("turn_count", 0) == 6
        assert result.get("init_plan") is None
        # 无 feedback
        assert result.get("feedback_record") is None
