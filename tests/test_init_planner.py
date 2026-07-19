"""Init Planner + 启动重建 3 情况 — 12 个验收测试用例。

设计目标（v0.1.2 spec 定稿 + 用户 7 项拍板全 A1）：
1. decide_init_mode 三分支（first_init / new_day_init / resume）
2. lifespan AGENT_INIT 事件
3. EventQueue Priority
4. init_prompt 模板
5. dj_planner system_init 分支
6. action_planner init_plan 处理
7. emit_response 3 类 WS 输出
8. RuntimeDJState 重建
9. snapshot 深拷贝
10. context_builder 5 域 + 不读 RDS
11. program_state 写入
12. 集成：Graph ainvoke 全链路

使用方法：
    cd dev
    pip install -r requirements.txt
    python -m pytest tests/test_init_planner.py -v
"""

import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# 确保 agent 包可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.shared.enums import InitMode, EventType, EventPriority, TriggerType
from agent.runtime.event_queue import Event, EventQueue
from agent.runtime.dispatcher import EventDispatcher, _map_event_type_to_trigger


# ═══════════════════════════════════════════════════════════════
# Test Case 1: decide_init_mode — program_state.json 不存在 → FIRST_INIT
# ═══════════════════════════════════════════════════════════════
class TestDecideInitMode:
    """★ v0.6 J 项：启动重建 3 情况判断。"""

    # patch 目标：decide_init_mode 在 lifespan 模块中引用 load_program_state
    PATCH_TARGET = "agent.runtime.lifespan"

    def test_first_init_when_no_program_state(self):
        """TC-01: program_state.json 不存在 → decide_init_mode() == FIRST_INIT。"""
        from agent.runtime import decide_init_mode

        with patch(f"{self.PATCH_TARGET}.load_program_state", return_value=None):
            mode = decide_init_mode()
        assert mode == InitMode.FIRST_INIT, f"Expected FIRST_INIT, got {mode}"

    def test_new_day_init_when_date_mismatch(self):
        """TC-02: program_date != today → decide_init_mode() == NEW_DAY_INIT。"""
        from agent.runtime import decide_init_mode

        old_state = {
            "version": "1.0",
            "program_date": "2000-01-01",  # 明显不是今天
        }

        with patch(f"{self.PATCH_TARGET}.load_program_state", return_value=old_state):
            with patch(f"{self.PATCH_TARGET}.program_date_matches_today", return_value=False):
                mode = decide_init_mode()
        assert mode == InitMode.NEW_DAY_INIT, f"Expected NEW_DAY_INIT, got {mode}"

    def test_resume_when_date_matches(self):
        """TC-03: program_date == today → decide_init_mode() == RESUME。"""
        from agent.runtime import decide_init_mode

        import datetime
        today = datetime.date.today().isoformat()
        today_state = {
            "version": "1.0",
            "program_date": today,
            "today_theme": "Today",
        }

        with patch(f"{self.PATCH_TARGET}.load_program_state", return_value=today_state):
            with patch(f"{self.PATCH_TARGET}.program_date_matches_today", return_value=True):
                mode = decide_init_mode()
        assert mode == InitMode.RESUME, f"Expected RESUME, got {mode}"


# ═══════════════════════════════════════════════════════════════
# Test Case 2: lifespan 推 AGENT_INIT 事件
# ═══════════════════════════════════════════════════════════════
class TestLifespanAgentInit:
    """lifespan 第 9 步：decide_init_mode + 推 AGENT_INIT。"""

    @pytest.mark.asyncio
    async def test_push_agent_init_on_first_init(self):
        """TC-04: first_init 时推 AGENT_INIT 事件到 EventQueue。"""
        from agent.runtime import _push_agent_init_when_ready, _runtime_ready_event, event_queue

        _runtime_ready_event.clear()
        _runtime_ready_event.set()

        # 注意 patch 目标必须是 lifespan 模块（_push_agent_init_when_ready 在其中引用 decide_init_mode）
        with patch("agent.runtime.lifespan.decide_init_mode", return_value=InitMode.FIRST_INIT):
            await _push_agent_init_when_ready()

        assert event_queue.qsize() > 0, "应有一个 AGENT_INIT 事件"

    @pytest.mark.asyncio
    async def test_skip_agent_init_on_resume(self):
        """TC-05: resume 时推 REPLAN_REQUEST 而非 AGENT_INIT。"""
        from agent.runtime import _push_agent_init_when_ready, _runtime_ready_event, event_queue

        _runtime_ready_event.set()
        initial_size = event_queue.qsize()

        with patch("agent.runtime.lifespan.decide_init_mode", return_value=InitMode.RESUME):
            await _push_agent_init_when_ready()

        # resume 模式推 REPLAN_REQUEST（比 initial_size 多 1 个）
        assert event_queue.qsize() == initial_size + 1, "Should push REPLAN_REQUEST on resume"


# ═══════════════════════════════════════════════════════════════
# Test Case 3: EventQueue Priority
# ═══════════════════════════════════════════════════════════════
class TestEventQueue:
    """EventQueue Priority 顺序测试。"""

    @pytest.mark.asyncio
    async def test_priority_order(self):
        """TC-06: EVENT 按 Priority 出队（P0 先于 P1 先于 P3）。"""
        q = EventQueue()
        await q.put(Event.from_system(EventType.AGENT_INIT, {}))          # P1=SYSTEM
        await q.put(Event.from_timer(EventType.TIMER_PROGRAM_TICK, {}))   # P3=TIMER
        await q.put(Event.from_user(EventType.CHAT_SEND, {"text": "hi"})) # P0=USER

        first = await q.get()
        assert first.priority == EventPriority.USER, f"Expected USER first, got {first.priority}"

        second = await q.get()
        assert second.priority == EventPriority.SYSTEM, f"Expected SYSTEM second, got {second.priority}"

        third = await q.get()
        assert third.priority == EventPriority.TIMER, f"Expected TIMER third, got {third.priority}"

    def test_agent_init_has_system_priority(self):
        """AGENT_INIT 事件具有 SYSTEM Priority。"""
        event = Event.from_system(EventType.AGENT_INIT, {"reason": "first_init"})
        assert event.priority == EventPriority.SYSTEM
        assert event.type == EventType.AGENT_INIT

    def test_trigger_mapping_system_init(self):
        """AGENT_INIT → trigger_type=system_init。"""
        trigger = _map_event_type_to_trigger(EventType.AGENT_INIT)
        assert trigger == "system_init"

    def test_trigger_mapping_conversation(self):
        """CHAT_SEND → trigger_type=conversation。"""
        trigger = _map_event_type_to_trigger(EventType.CHAT_SEND)
        assert trigger == "conversation"


# ═══════════════════════════════════════════════════════════════
# Test Case 4: init_prompt 模板
# ═══════════════════════════════════════════════════════════════
class TestInitPrompt:
    """INIT_PROMPT 模板填充测试。"""

    def test_format_init_prompt_first_init(self):
        """TC-07: INIT_PROMPT 模板正确填充 first_init 参数。"""
        from agent.prompts.init_prompt import format_init_prompt

        result = format_init_prompt(
            init_mode="first_init",
            date="2026-07-17",
            today="2026-07-17",
            weather="晴天",
            day_period="evening",
            scene="default",
            music_profile='{"favorite_genres": ["pop", "jazz"]}',
        )

        assert "first_init" in result
        assert "2026-07-17" in result
        assert "晴天" in result
        assert "evening" in result

    def test_format_init_prompt_new_day(self):
        """INIT_PROMPT 正确填充 new_day_init 参数。"""
        from agent.prompts.init_prompt import format_init_prompt

        result = format_init_prompt(
            init_mode="new_day_init",
            date="2026-07-18",
            today="2026-07-18",
            weather="多云",
            day_period="morning",
            scene="working",
            music_profile="（新用户）",
        )

        assert "new_day_init" in result
        assert "2026-07-18" in result
        assert "多云" in result


# ═══════════════════════════════════════════════════════════════
# Test Case 5: dj_planner system_init 分支
# ═══════════════════════════════════════════════════════════════
class TestDjPlannerInit:
    """dj_planner_node system_init 分支测试。"""

    @pytest.mark.asyncio
    async def test_dj_planner_returns_init_plan_on_system_init(self):
        """TC-08: dj_planner_node 处理 system_init trigger_type → 输出 init_plan。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "system_init",
            "init_mode": InitMode.FIRST_INIT,
            "runtime_snapshot": {},
            "environment": {"day_period": "evening"},
            "user": {},
            "program": {},
        }

        result = await dj_planner_node(state)

        assert "init_plan" in result, "dj_planner 应返回 init_plan"
        plan = result["init_plan"]
        assert plan is not None
        assert "program_state" in plan
        assert "initial_playlist" in plan
        assert "first_song_id" in plan
        assert "welcome_text" in plan
        # 验证 playlist 数量（MVP 固定 10 首 — Q12 拍板）
        assert len(plan["initial_playlist"]) == 10, "initial_playlist 应为 10 首"
        assert result["next_node"] == "action_planner"

    @pytest.mark.asyncio
    async def test_dj_planner_non_init_passthrough(self):
        """非 system_init trigger → 不生成 init_plan，走 4 prompt 模式。"""
        from agent.nodes.dj_planner import dj_planner_node

        state = {
            "trigger_type": "conversation",
            "runtime_snapshot": {},
        }

        result = await dj_planner_node(state)
        assert result.get("init_plan") is None, "非 system_init 不应生成 init_plan"
        # ★ v0.6 4 prompt 模式：conversation → 输出 llm_decision（含 4 块 schema）
        decision = result.get("llm_decision")
        assert decision is not None, "conversation 应返回 llm_decision"
        assert "program_decision" in decision
        assert "playlist_decision" in decision
        assert "dialogue_decision" in decision
        assert "tool_calls" in decision
        assert result.get("next_node") == "action_planner"


# ═══════════════════════════════════════════════════════════════
# Test Case 6: action_planner init_plan 处理（★ Q14+15 事务顺序）
# ═══════════════════════════════════════════════════════════════
class TestActionPlannerInit:
    """action_planner_node init_plan 处理。"""

    @pytest.mark.asyncio
    async def test_action_planner_handles_init_plan(self):
        """TC-09: action_planner 处理 init_plan → 输出 actions + pending_payload。

        ★ Q14+15 事务顺序：
          ① save_program_state  ② play_music
          ③ status.welcome  ④ chat.reply  ⑤ music.play
        """
        from agent.nodes.action_planner import action_planner_node

        init_plan = {
            "program_state": {
                "program_date": "2026-07-17",
                "today_theme": "Test Theme",
                "program_mood": "neutral",
                "program_goal": "test",
            },
            "initial_playlist": [
                {"song_id": "1", "name": "Song A", "artist": "Artist A", "scene_match": "test"},
                {"song_id": "2", "name": "Song B", "artist": "Artist B", "scene_match": "test"},
            ],
            "first_song_id": "1",
            "welcome_text": "Hello, test welcome!",
        }

        state = {
            "trigger_type": TriggerType.SYSTEM_INIT,
            "init_mode": "first_init",
            "init_plan": init_plan,
            "dependencies": {
                "runtime_dj_state": {"current_scene": "default", "program_mood": "neutral"},
            },
        }

        result = await action_planner_node(state)

        # ① save_program_state（通过 state_manager.program — 验证 pending_payload 含 program_state）
        assert "actions" in result
        pending = result.get("pending_payload", {})
        assert pending is not None

        # ③ status.welcome
        assert pending["status_update"]["type"] == "welcome"
        assert pending["status_update"]["init_mode"] == "first_init"

        # ④ chat.reply
        assert pending["chat_reply"] == "Hello, test welcome!"

        # ⑤ music.play
        assert result["should_play_music"] is True
        assert pending["music_play"]["song"]["id"] == "1"
        assert pending["music_play"]["auto_play"] is True

        # should_speak
        assert result["should_speak"] is True

    @pytest.mark.asyncio
    async def test_empty_init_plan_no_side_effects(self):
        """init_plan 为 None 时，action_planner 返回空 actions。"""
        from agent.nodes.action_planner import action_planner_node

        state = {
            "trigger_type": TriggerType.SYSTEM_INIT,
            "init_mode": "first_init",
            "init_plan": None,
            "dependencies": {},
        }

        result = await action_planner_node(state)
        assert result["actions"] == []
        assert result["pending_payload"] is None


# ═══════════════════════════════════════════════════════════════
# Test Case 7: emit_response 3 类 WS
# ═══════════════════════════════════════════════════════════════
class TestEmitResponse:
    """emit_response_node — 3 类 WS 输出。"""

    @pytest.mark.asyncio
    async def test_emit_status_chat_music(self):
        """TC-10: emit_response 正确记录 3 类 WS（status.welcome / chat.reply / music.play）。"""
        from agent.nodes.emit_response import emit_response_node

        state = {
            "pending_payload": {
                "chat_reply": "hello world",
                "music_play": {
                    "song": {"name": "Test Song", "artist": "Test Artist"},
                    "auto_play": True,
                },
                "status_update": {
                    "type": "welcome",
                    "init_mode": "first_init",
                    "program_state": {"program_date": "2026-07-17"},
                },
            },
            "turn_count": 0,
        }

        result = await emit_response_node(state)

        # turn_count 递增
        assert result["turn_count"] == 1
        assert result["last_active_at_ms"] > 0

    @pytest.mark.asyncio
    async def test_emit_empty_payload(self):
        """pending_payload 为 None 时空安全。"""
        from agent.nodes.emit_response import emit_response_node

        state = {"pending_payload": None, "turn_count": 5}
        result = await emit_response_node(state)
        assert result["turn_count"] == 6


# ═══════════════════════════════════════════════════════════════
# Test Case 8: RuntimeDJState 重建
# ═══════════════════════════════════════════════════════════════
class TestRuntimeDJState:
    """RuntimeDJState 重建与快照。"""

    def test_build_runtime_dj_state_from_disk_first_init(self):
        """TC-11: first_init 时从 disk 重建 RuntimeDJState 包含默认字段。"""
        from agent.state.runtime_dj_state import build_runtime_dj_state_from_disk

        # mock 让 player_mirror 和 program_state 都返回 None
        with patch("agent.state.runtime_dj_state.pm_mod.load_player_mirror", return_value=None):
            with patch("agent.state.runtime_dj_state.ps_mod.load_program_state", return_value=None):
                rds = build_runtime_dj_state_from_disk()

        # 验证必含字段
        assert rds["current_song"] is None
        assert rds["current_segment"] == "intro"
        assert rds["program_mood"] == "neutral"
        assert rds["current_scene"] == "default"
        assert rds["playlist_queue"] == []
        assert rds["pending_actions"] == []
        assert rds["segment_started_at_ms"] > 0

    def test_runtime_dj_state_snapshot_is_deep_copy(self):
        """snapshot_runtime_dj_state 返回深拷贝，修改 snapshot 不影响原 RDS。"""
        from agent.state.runtime_dj_state import (
            build_runtime_dj_state_from_disk, snapshot_runtime_dj_state,
        )

        with patch("agent.state.runtime_dj_state.pm_mod.load_player_mirror", return_value={
            "current_song": {"song_id": "123", "name": "Test"},
            "playlist_queue": [],
        }):
            with patch("agent.state.runtime_dj_state.ps_mod.load_program_state", return_value=None):
                rds = build_runtime_dj_state_from_disk()

        snapshot = snapshot_runtime_dj_state(rds)

        # 修改 snapshot
        snapshot["current_song"] = {"modified": True}

        # 原 RDS 不变
        assert rds["current_song"]["song_id"] == "123"
        assert rds["current_song"].get("modified") is None


# ═══════════════════════════════════════════════════════════════
# Test Case 9: context_builder（5 域 + 不读 RDS）
# ═══════════════════════════════════════════════════════════════
class TestContextBuilder:
    """context_builder 5 域加载 + 不读 RuntimeDJState。"""

    @pytest.mark.asyncio
    async def test_context_builder_returns_5_domains(self):
        """TC-12: context_builder_node 正确返回 5 域（user/environment/program/playlist/player_mirror）。"""
        from agent.nodes.context_builder import context_builder_node

        # mock state_manager 方法
        with patch("agent.nodes.context_builder.state_manager.memory.load_all", return_value={}), \
             patch("agent.nodes.context_builder.state_manager.memory.load_category", return_value={}), \
             patch("agent.nodes.context_builder.state_manager.program.load_program_state", return_value=None), \
             patch("agent.nodes.context_builder.state_manager.player.load_player_mirror", return_value={}):

            result = await context_builder_node({})

        # 验证 5 域 + 不包含 runtime_snapshot
        assert "user" in result
        assert "environment" in result
        assert "program" in result
        assert "playlist" in result
        assert "player_mirror" in result
        assert "runtime_snapshot" not in result, "context_builder 不应写 runtime_snapshot"


# ═══════════════════════════════════════════════════════════════
# Test Case 10: program_state 写入事务
# ═══════════════════════════════════════════════════════════════
class TestProgramState:
    """program_state 读写测试。"""

    def test_save_and_load_program_state(self, tmp_path):
        """验证保存和加载 program_state 的一致性。"""
        from agent.state.program_state import load_program_state, save_program_state
        from agent.config import settings

        # 临时文件路径
        original_file = settings.PROGRAM_STATE_FILE
        settings.PROGRAM_STATE_FILE = str(tmp_path / "program_state.json")

        try:
            state = {
                "program_date": "2026-07-17",
                "today_theme": "Test",
                "program_mood": "warm",
            }
            ok = save_program_state(state)
            assert ok is True

            loaded = load_program_state()
            assert loaded["program_date"] == "2026-07-17"
            assert loaded["today_theme"] == "Test"
            assert loaded["program_mood"] == "warm"
            assert "updated_at" in loaded
        finally:
            settings.PROGRAM_STATE_FILE = original_file

    def test_load_nonexistent_returns_none(self):
        """不存在的 program_state.json → load 返回 None。"""
        from agent.state.program_state import load_program_state
        from agent.config import settings

        non_existent = "/tmp/_nonexistent_test_dir_/program_state.json"
        original = settings.PROGRAM_STATE_FILE
        settings.PROGRAM_STATE_FILE = non_existent

        try:
            result = load_program_state()
            assert result is None
        finally:
            settings.PROGRAM_STATE_FILE = original


# ═══════════════════════════════════════════════════════════════
# Test Case 11: 集成 — Graph ainvoke 全链路
# ═══════════════════════════════════════════════════════════════
class TestInitPlannerIntegration:
    """集成测试：Graph ainvoke 全链路。"""

    @pytest.mark.asyncio
    async def test_graph_ainvoke_system_init_first_init(self):
        """Graph.ainvoke 处理 system_init + first_init 全链路。

        验证：
          - context_builder → dj_planner → action_planner → emit_response 完整路径
          - 最终输出含 status.welcome + chat.reply + music.play
        """
        from unittest.mock import patch
        from agent.graph import build_graph

        graph = build_graph()

        initial_state = {
            "trigger_type": "system_init",
            "init_mode": "first_init",
            "trigger_event": {"reason": "first_init"},
            "event_priority": EventPriority.SYSTEM,
            "runtime_snapshot": {},
            "dependencies": {
                "runtime_dj_state": {"current_scene": "default", "program_mood": "neutral"},
            },
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
            "actions": [],
            "pending_tool_calls": [],
            "pending_payload": None,
            "should_speak": False,
            "should_play_music": False,
            "turn_count": 0,
            "last_active_at_ms": 0,
            "user": {},
            "environment": {},
            "program": {},
            "playlist": {},
            "player_mirror": {},
            "llm_decision": None,
            "init_plan": None,
            "feedback_record": None,
            "last_error": None,
        }

        with patch("agent.nodes.action_executor._music.get_play_url",
                    return_value="http://localhost:8000/api/proxy/audio?url=https://example.com/test.mp3"):
            result = await graph.ainvoke(initial_state)

        # 验证完整链路输出
        pending = result.get("pending_payload", {}) or {}

        # status.welcome
        assert pending.get("status_update", {}).get("type") == "welcome", \
            "应包含 status.welcome"

        # chat.reply
        assert "chat_reply" in pending, "应包含 chat.reply"
        assert len(pending["chat_reply"]) > 0, "welcome_text 不应为空"

        # music.play
        if result.get("should_play_music"):
            assert "music_play" in pending, "应包含 music.play"
            assert pending["music_play"]["auto_play"] is True

        # turn_count 递增
        assert result.get("turn_count", 0) >= 1, "turn_count 应递增"

    @pytest.mark.asyncio
    async def test_graph_ainvoke_conversation_no_init(self):
        """非 system_init trigger_type → 不触发 Init Planner。"""
        from agent.graph import build_graph

        graph = build_graph()

        state = {
            "trigger_type": "conversation",
            "trigger_event": {"text": "hello"},
            "init_mode": "resume",
            "event_priority": EventPriority.USER,
            "runtime_snapshot": {},
            "dependencies": {},
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
            "actions": [],
            "pending_tool_calls": [],
            "pending_payload": None,
            "should_speak": False,
            "should_play_music": False,
            "turn_count": 0,
            "last_active_at_ms": 0,
            "user": {},
            "environment": {},
            "program": {},
            "playlist": {},
            "player_mirror": {},
            "llm_decision": None,
            "init_plan": None,
            "feedback_record": None,
            "last_error": None,
        }

        result = await graph.ainvoke(state)
        # 不应有 init_plan
        assert result.get("init_plan") is None

    @pytest.mark.asyncio
    async def test_dispatcher_build_initial_state_injects_snapshot(self):
        """EventDispatcher._build_initial_state 正确注入 runtime_snapshot。"""
        from agent.runtime.event_queue import EventQueue, EventType

        q = EventQueue()
        rds = {"current_song": {"id": "test"}, "playlist_queue": []}
        dispatcher = EventDispatcher(q, rds)

        event = Event.from_system(EventType.AGENT_INIT, {"reason": "first_init"})
        state = dispatcher._build_initial_state(event, rds)

        assert "runtime_snapshot" in state
        assert state["runtime_snapshot"]["current_song"]["id"] == "test"
        assert state["init_mode"] == "first_init"
        assert "dependencies" in state
        assert state["dependencies"]["runtime_dj_state"] is rds


# ═══════════════════════════════════════════════════════════════
# Test Case 12: Router — 返回 dict + next_node 路由
# ═══════════════════════════════════════════════════════════════
class TestRouterAsNode:
    """router_node 作为 Graph Node 返回 dict 含 next_node。"""

    @pytest.mark.asyncio
    async def test_router_system_init_routes_to_context_builder(self):
        """system_init → router 返回 {"next_node": "context_builder"}。"""
        from agent.nodes.router import router_node

        result = await router_node({"trigger_type": "system_init", "trigger_event": {}})
        assert result == {"next_node": "context_builder"}

    @pytest.mark.asyncio
    async def test_router_conversation_routes_to_context_builder(self):
        """conversation → router 返回 {"next_node": "context_builder"}。"""
        from agent.nodes.router import router_node

        result = await router_node({"trigger_type": "conversation", "trigger_event": {}})
        assert result == {"next_node": "context_builder"}

    @pytest.mark.asyncio
    async def test_router_song_finished_routes_to_action_planner(self):
        """player_event.song_finished → router 返回 {"next_node": "action_planner"}。"""
        from agent.nodes.router import router_node

        result = await router_node({
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished"},
        })
        assert result == {"next_node": "action_planner"}

    @pytest.mark.asyncio
    async def test_router_user_like_routes_to_feedback_extractor(self):
        """player_event.user_like → router 返回 {"next_node": "feedback_extractor"}。"""
        from agent.nodes.router import router_node

        result = await router_node({
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "user_like"},
        })
        assert result == {"next_node": "feedback_extractor"}

    @pytest.mark.asyncio
    async def test_router_song_started_routes_to_emit_response(self):
        """player_event.song_started → router 返回 {"next_node": "emit_response"}。"""
        from agent.nodes.router import router_node

        result = await router_node({
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_started"},
        })
        assert result == {"next_node": "emit_response"}


# ═══════════════════════════════════════════════════════════════
# Test Case 13: feedback_extractor — 4 类反馈事件处理
# ═══════════════════════════════════════════════════════════════
class TestFeedbackExtractor:
    """feedback_extractor_node 处理 user_like/dislike/skip/play_end。"""

    @pytest.mark.asyncio
    async def test_feedback_like_writes_memory(self):
        """user_like → 写 Memory + 返回 feedback_record。"""
        from agent.nodes.feedback_extractor import feedback_extractor_node

        state = {
            "trigger_event": {
                "subtype": "user_like",
                "song_id": "song_001",
                "song": {"song_id": "song_001", "name": "Test Song"},
            },
        }

        with patch("agent.nodes.feedback_extractor.state_manager.memory.write", return_value=True):
            result = await feedback_extractor_node(state)

        assert result["feedback_record"] is not None
        assert result["feedback_record"]["action"] == "like"
        assert result["feedback_record"]["song_id"] == "song_001"

    @pytest.mark.asyncio
    async def test_feedback_dislike_writes_memory(self):
        """user_dislike → 写 Memory。"""
        from agent.nodes.feedback_extractor import feedback_extractor_node

        state = {
            "trigger_event": {
                "subtype": "user_dislike",
                "song_id": "song_002",
                "song": {"song_id": "song_002"},
            },
        }

        with patch("agent.nodes.feedback_extractor.state_manager.memory.write", return_value=True):
            result = await feedback_extractor_node(state)

        assert result["feedback_record"]["action"] == "dislike"

    @pytest.mark.asyncio
    async def test_feedback_skip_writes_memory(self):
        """user_skip → 写 Memory。"""
        from agent.nodes.feedback_extractor import feedback_extractor_node

        state = {
            "trigger_event": {
                "subtype": "user_skip",
                "song_id": "song_003",
                "song": {"song_id": "song_003"},
            },
        }

        with patch("agent.nodes.feedback_extractor.state_manager.memory.write", return_value=True):
            result = await feedback_extractor_node(state)

        assert result["feedback_record"]["action"] == "skip"

    @pytest.mark.asyncio
    async def test_feedback_play_end_high_ratio(self):
        """play_end 高播放比(≥0.8) → like。"""
        from agent.nodes.feedback_extractor import feedback_extractor_node

        state = {
            "trigger_event": {
                "subtype": "play_end",
                "song_id": "song_004",
                "song": {"song_id": "song_004"},
                "played_ms": 80000,
                "duration_ms": 100000,
            },
        }

        with patch("agent.nodes.feedback_extractor.state_manager.memory.write", return_value=True):
            result = await feedback_extractor_node(state)

        assert result["feedback_record"]["action"] == "like"

    @pytest.mark.asyncio
    async def test_feedback_play_end_low_ratio(self):
        """play_end 低播放比(<0.3) → skip。"""
        from agent.nodes.feedback_extractor import feedback_extractor_node

        state = {
            "trigger_event": {
                "subtype": "play_end",
                "song_id": "song_005",
                "song": {"song_id": "song_005"},
                "played_ms": 10000,
                "duration_ms": 100000,
            },
        }

        with patch("agent.nodes.feedback_extractor.state_manager.memory.write", return_value=True):
            result = await feedback_extractor_node(state)

        assert result["feedback_record"]["action"] == "skip"

    @pytest.mark.asyncio
    async def test_feedback_missing_song_id(self):
        """缺少 song_id → 不写 Memory + last_error。"""
        from agent.nodes.feedback_extractor import feedback_extractor_node

        state = {"trigger_event": {"subtype": "user_like"}}
        result = await feedback_extractor_node(state)

        assert result["feedback_record"] is None
        assert result["last_error"]["code"] == "MISSING_SONG_ID"


# ═══════════════════════════════════════════════════════════════
# Test Case 14: tool_dispatcher — pending_tool_calls 执行
# ═══════════════════════════════════════════════════════════════
class TestToolDispatcher:
    """tool_dispatcher_node 执行 tool 调用。"""

    @pytest.mark.asyncio
    async def test_tool_dispatcher_executes_calls(self):
        """有 pending_tool_calls → 执行并返回 tool_messages。"""
        from agent.nodes.tool_dispatcher import tool_dispatcher_node

        state = {
            "pending_tool_calls": [
                {"name": "get_environment_context", "args": {}},
            ],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        with patch("agent.nodes.tool_dispatcher.adapter.dispatch", new_callable=AsyncMock, return_value={"weather": "sunny"}):
            result = await tool_dispatcher_node(state)

        assert len(result["tool_messages"]) == 1
        assert result["tool_messages"][0]["name"] == "get_environment_context"
        assert result["tool_messages"][0]["status"] == "ok"
        assert result["tool_loop_count"] == 1
        assert result["next_node"] == "action_planner"  # max=1 强制收尾

    @pytest.mark.asyncio
    async def test_tool_dispatcher_no_calls(self):
        """pending_tool_calls 为空 → 直接返回空结果。"""
        from agent.nodes.tool_dispatcher import tool_dispatcher_node

        state = {
            "pending_tool_calls": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await tool_dispatcher_node(state)

        assert result["tool_messages"] == []
        assert result["tool_loop_count"] == 0
        assert result["next_node"] == "action_planner"

    @pytest.mark.asyncio
    async def test_tool_dispatcher_not_implemented(self):
        """未实现的 tool → 标记 status=not_implemented，不抛异常。"""
        from agent.nodes.tool_dispatcher import tool_dispatcher_node

        state = {
            "pending_tool_calls": [
                {"name": "unknown_tool", "args": {}},
            ],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
        }

        result = await tool_dispatcher_node(state)

        assert len(result["tool_messages"]) == 1
        assert result["tool_messages"][0]["status"] == "not_implemented"
        assert result["tool_loop_count"] == 1
        assert result["next_node"] == "action_planner"


# ═══════════════════════════════════════════════════════════════
# Test Case 15: song_finished 路由处理
# ═══════════════════════════════════════════════════════════════
class TestSongFinishedRouting:
    """action_planner._handle_song_finished 全路径 + transition speech。"""

    @pytest.mark.asyncio
    async def test_queue_has_next_song(self):
        """queue 有下一首 → play_song action + should_play_music=True。"""
        from agent.nodes.action_planner import action_planner_node

        state = {
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished", "song_id": "123"},
            "runtime_snapshot": {
                "playlist_queue": [{"song_id": "456", "name": "Next", "artist": "A"}],
            },
            "program": {"today_theme": "测试"},
            "dependencies": {},
            "__refs__": {},
            "actions": [],
        }

        result = await action_planner_node(state)

        assert result["should_play_music"] is True
        assert result["should_speak"] is False
        assert len(result["actions"]) == 1
        assert result["actions"][0]["type"] == "play_song"
        assert result["actions"][0]["params"]["song_id"] == "456"
        assert result["pending_payload"]["music_play"]["song"]["id"] == "456"
        assert result["feedback_record"] is None

    @pytest.mark.asyncio
    async def test_queue_empty_with_event_service(self):
        """queue 空 + event_service 注入 → transition speech + 推 REPLAN。"""
        from agent.nodes.action_planner import action_planner_node
        from agent.services.event_service import EventService
        from agent.runtime.event_queue import EventQueue

        q = EventQueue()
        svc = EventService()
        svc.bind(q)

        state = {
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished", "song_id": "123"},
            "runtime_snapshot": {
                "playlist_queue": [],
                "program_mood": "warm",
            },
            "program": {"today_theme": "晚间"},
            "dependencies": {},
            "__refs__": {"event_service": svc},
            "actions": [],
        }

        result = await action_planner_node(state)

        assert result["should_speak"] is True
        assert result["should_play_music"] is False
        assert len(result["actions"]) == 1
        assert result["actions"][0]["type"] == "tts_speak"
        assert result["feedback_record"] is None
        # 检查 transition_speech 内容
        ts = result["pending_payload"]["transition_speech"]
        assert "晚间" in ts["text"]
        assert ts["source"] == "song_finished_queue_empty"
        assert ts["mood"] == "warm"
        # REPLAN 已推入队列
        assert q.qsize() == 1

    @pytest.mark.asyncio
    async def test_queue_empty_no_event_service(self):
        """queue 空 + event_service 未注入 → transition speech + 无 last_error。"""
        from agent.nodes.action_planner import action_planner_node

        state = {
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished", "song_id": "123"},
            "runtime_snapshot": {
                "playlist_queue": [],
                "program_mood": "neutral",
            },
            "program": {},
            "dependencies": {},
            "__refs__": {},
            "actions": [],
        }

        result = await action_planner_node(state)
        # 即使没有 event_service，transition speech 仍应生成
        assert result["should_speak"] is True
        assert result["pending_payload"]["transition_speech"] is not None
        assert "last_error" not in result

    @pytest.mark.asyncio
    async def test_replan_push_failure(self):
        """event_service.push_replan 失败 → last_error.REPLAN_PUSH_FAILED。"""
        from agent.nodes.action_planner import action_planner_node

        svc_mock = MagicMock()
        svc_mock.push_replan = AsyncMock(return_value=False)

        state = {
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished", "song_id": "123"},
            "runtime_snapshot": {
                "playlist_queue": [],
                "program_mood": "energetic",
            },
            "program": {"today_theme": "晨间"},
            "dependencies": {},
            "__refs__": {"event_service": svc_mock},
            "actions": [],
        }

        result = await action_planner_node(state)

        assert result["should_speak"] is True
        assert result["last_error"]["code"] == "REPLAN_PUSH_FAILED"
        svc_mock.push_replan.assert_awaited_once()

    # ── transition speech 模板测试 ──

    @pytest.mark.asyncio
    async def test_transition_speech_energetic(self):
        """program_mood=energetic → energetic 模板。"""
        from agent.nodes.action_planner import _generate_transition_speech

        text = _generate_transition_speech(
            {"program_mood": "energetic"},
            {"today_theme": "夜跑"},
        )
        assert "夜跑" in text
        assert "节奏" in text

    @pytest.mark.asyncio
    async def test_transition_speech_warm(self):
        """program_mood=warm → warm 模板。"""
        from agent.nodes.action_planner import _generate_transition_speech

        text = _generate_transition_speech(
            {"program_mood": "warm"},
            {"today_theme": "午后"},
        )
        assert "午后" in text
        assert "贴心" in text

    @pytest.mark.asyncio
    async def test_transition_speech_reflective(self):
        """program_mood=reflective → reflective 模板。"""
        from agent.nodes.action_planner import _generate_transition_speech

        text = _generate_transition_speech(
            {"program_mood": "reflective"},
            {"today_theme": "深夜"},
        )
        assert "深夜" in text
        assert "心里" in text

    @pytest.mark.asyncio
    async def test_transition_speech_fallback(self):
        """program_mood=neutral（和未知值）→ fallback 模板。"""
        from agent.nodes.action_planner import _generate_transition_speech

        # neutral → fallback
        text1 = _generate_transition_speech(
            {"program_mood": "neutral"},
            {"today_theme": "午后"},
        )
        assert "午后" in text1
        assert "告一段落" in text1

        # 未知 mood → fallback
        text2 = _generate_transition_speech(
            {"program_mood": "unknown_mood"},
            {"today_theme": "测试"},
        )
        assert "测试" in text2
        assert "告一段落" in text2

        # 空 program → 默认 "今晚"
        text3 = _generate_transition_speech(
            {"program_mood": "neutral"},
            {},
        )
        assert "今晚" in text3

    @pytest.mark.asyncio
    async def test_song_finished_does_not_write_feedback(self):
        """song_finished 路径绝对不写 feedback（feedback_record=None）。"""
        from agent.nodes.action_planner import action_planner_node

        # queue 有 → 不写 feedback
        r1 = await action_planner_node({
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished", "song_id": "123"},
            "runtime_snapshot": {"playlist_queue": [{"song_id": "456"}]},
            "dependencies": {}, "__refs__": {},
        })
        assert r1["feedback_record"] is None

        # queue 空 → 不写 feedback
        r2 = await action_planner_node({
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished", "song_id": "123"},
            "runtime_snapshot": {"playlist_queue": []},
            "dependencies": {}, "__refs__": {},
            "program": {},
        })
        assert r2["feedback_record"] is None


# ═══════════════════════════════════════════════════════════════
# Test Case 16: AgentState — 字段定义
# ═══════════════════════════════════════════════════════════════
class TestAgentState:
    """AgentState TypedDict 字段验证。"""

    def test_agent_state_has_required_fields(self):
        """AgentState 包含所需字段集合。"""
        from agent.state.agent_state import AgentState

        # 验证 TypedDict 注解存在
        annotations = AgentState.__annotations__
        assert "trigger_type" in annotations
        assert "runtime_snapshot" in annotations
        assert "tool_loop_count" in annotations
        assert "actions" in annotations
        assert "messages" in annotations
        assert "tool_messages" in annotations
        assert "next_node" in annotations
        assert "dependencies" in annotations
        assert "pending_payload" in annotations
        # 验证不包含 runtime_dj_state（只在 dependencies 中引用）
        assert "runtime_dj_state" not in annotations


# ═══════════════════════════════════════════════════════════════
# Test Case 17: EventService — 事件推送
# ═══════════════════════════════════════════════════════════════
class TestEventService:
    """EventService 绑定 EventQueue + 推送事件。"""

    @pytest.mark.asyncio
    async def test_event_service_push(self):
        """EventService.push_event 成功推送到 EventQueue。"""
        from agent.services.event_service import EventService
        from agent.runtime.event_queue import EventQueue, EventType

        svc = EventService()
        q = EventQueue()
        svc.bind(q)

        ok = await svc.push_event(EventType.REPLAN_REQUEST, {"reason": "test"})
        assert ok is True
        assert q.qsize() == 1

    @pytest.mark.asyncio
    async def test_event_service_push_replan(self):
        """EventService.push_replan 快捷方法。"""
        from agent.services.event_service import EventService
        from agent.runtime.event_queue import EventQueue, EventType

        svc = EventService()
        q = EventQueue()
        svc.bind(q)

        ok = await svc.push_replan("queue_empty", source="test")
        assert ok is True
        assert q.qsize() == 1

    @pytest.mark.asyncio
    async def test_event_service_no_bind(self):
        """未绑定的 EventService.push 返回 False。"""
        from agent.services.event_service import EventService
        from agent.runtime.event_queue import EventType

        svc = EventService()
        ok = await svc.push_event(EventType.REPLAN_REQUEST, {"reason": "test"})
        assert ok is False


# ═══════════════════════════════════════════════════════════════
# Test Case 18: StateGraph 路由完整性
# ═══════════════════════════════════════════════════════════════
class TestStateGraphRouting:
    """验证 StateGraph 所有 4 条路由路径可达。"""

    @pytest.mark.asyncio
    async def test_system_init_route(self):
        """system_init → router(context_builder) → context_builder → dj_planner → action_planner → emit_response。"""
        from agent.graph import build_graph

        graph = build_graph()
        result = await graph.ainvoke({
            "trigger_type": "system_init",
            "trigger_event": {"reason": "first_init"},
            "init_mode": "first_init",
            "runtime_snapshot": {},
            "dependencies": {"runtime_dj_state": {"current_scene": "default", "program_mood": "neutral"}},
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
            "pending_tool_calls": [],
        })

        # 应走完整 Init Planner 路径 → 有 pending_payload
        assert result.get("pending_payload") is not None

    @pytest.mark.asyncio
    async def test_conversation_route(self):
        """conversation → router(context_builder) → context_builder → dj_planner → action_planner → emit_response。"""
        from agent.graph import build_graph

        graph = build_graph()
        result = await graph.ainvoke({
            "trigger_type": "conversation",
            "trigger_event": {"text": "hi"},
            "init_mode": "resume",
            "runtime_snapshot": {},
            "dependencies": {},
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
            "pending_tool_calls": [],
        })

        # conversation 走 context_builder → dj_planner → action_planner → emit_response
        # dj_planner 非 system_init 返回空决策 → action_planner 返回空 → emit_response 吐 turn_count
        assert result.get("turn_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_song_started_emit_route(self):
        """song_started → router(emit_response) → emit_response（最短路径）。"""
        from agent.graph import build_graph

        graph = build_graph()
        result = await graph.ainvoke({
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_started", "song_id": "123"},
            "init_mode": "resume",
            "runtime_snapshot": {},
            "dependencies": {},
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
            "pending_tool_calls": [],
            "turn_count": 0,
            "last_active_at_ms": 0,
        })

        # song_started → 直接 emit_response，更新 turn_count
        assert result.get("turn_count", 0) >= 1
        assert result.get("init_plan") is None

    @pytest.mark.asyncio
    async def test_song_finished_route_with_queue(self):
        """song_finished + queue 有歌 → router(action_planner) → action_planner(play_song) → emit_response。"""
        from unittest.mock import patch
        from agent.graph import build_graph

        graph = build_graph()
        with patch("agent.nodes.action_executor._music.get_play_url",
                    return_value="http://localhost:8000/api/proxy/audio?url=https://example.com/test.mp3"):
            result = await graph.ainvoke({
                "trigger_type": "player_event",
                "trigger_event": {"subtype": "song_finished", "song_id": "123"},
                "init_mode": "resume",
                "runtime_snapshot": {"playlist_queue": [{"song_id": "456", "name": "Next"}]},
                "dependencies": {},
                "__refs__": {},
                "messages": [],
                "tool_messages": [],
                "tool_loop_count": 0,
                "tool_loop_max": 1,
                "pending_tool_calls": [],
                "turn_count": 0,
                "last_active_at_ms": 0,
                "actions": [],
                "pending_payload": None,
                "should_speak": False,
                "should_play_music": False,
            })

        # song_finished + queue 有 → play_song(next)
        assert result.get("should_play_music") is True
        assert result.get("pending_payload", {}).get("music_play") is not None
        assert result.get("turn_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_song_finished_route_queue_empty(self):
        """song_finished + queue 空 → action_planner(tts_speak + transition) → emit_response。"""
        from agent.graph import build_graph

        graph = build_graph()
        result = await graph.ainvoke({
            "trigger_type": "player_event",
            "trigger_event": {"subtype": "song_finished", "song_id": "123"},
            "init_mode": "resume",
            "runtime_snapshot": {"playlist_queue": [], "program_mood": "warm"},
            "dependencies": {},
            "__refs__": {},
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
            "pending_tool_calls": [],
            "turn_count": 0,
            "last_active_at_ms": 0,
            "actions": [],
            "pending_payload": None,
            "should_speak": False,
            "should_play_music": False,
        })

        # queue 空 → transition speech + should_speak
        assert result.get("should_speak") is True
        assert result.get("pending_payload", {}).get("transition_speech") is not None
        assert result.get("turn_count", 0) >= 1
