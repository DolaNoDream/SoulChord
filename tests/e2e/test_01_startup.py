"""E2E 冒烟测试 — Agent 启动（6 JSON + Graph + RDS + System Init 全链路）。

覆盖：
  1. init_data_files 生成 6 JSON + schema 校验
  2. 幂等性：重复调用不覆盖已有数据
  3. build_runtime_dj_state_from_disk 完整
  4. build_graph 编译 + 8 节点
  5. context_builder 5 域（从 chat chain 移入此文件）
  6. decide_init_mode 3 分支
  7. system_init 全链路：init_plan → welcome + music.play → ws_out_queue
"""

import json
import os
import pytest
from unittest.mock import patch

from agent.shared.enums import InitMode
from tests.e2e.conftest import drain_queue, build_initial_state


# ═══════════════════════════════════════════════════════════════
# 1. init_data_files — 6 JSON
# ═══════════════════════════════════════════════════════════════

class TestInitDataFiles:
    """data_initializer.init_data_files() 验证。"""

    def test_creates_6_json_files(self, init_data):
        """6 个 JSON 文件全部存在。"""
        assert os.path.exists(init_data / "memory.json")
        assert os.path.exists(init_data / "settings.json")
        assert os.path.exists(init_data / "playlists.json")
        assert os.path.exists(init_data / "program_state.json")
        assert os.path.exists(init_data / "player_mirror.json")
        assert os.path.exists(init_data / "player_history.json")

    def test_memory_json_schema(self, init_data):
        """memory.json 含 4 category: profile/preference/context/feedback。"""
        with open(init_data / "memory.json", "r") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "profile" in data
        assert "preference" in data
        assert "context" in data
        assert "feedback" in data

    def test_program_state_json_schema(self, init_data):
        """program_state.json 含 11 个字段（v0.6）。"""
        with open(init_data / "program_state.json", "r") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        # 核心字段（至少 5 个）
        assert "program_date" in data
        assert "today_theme" in data
        assert "current_segment" in data
        assert "program_mood" in data
        assert "program_status" in data

    def test_player_mirror_json_schema(self, init_data):
        """player_mirror.json 含播放状态字段。"""
        with open(init_data / "player_mirror.json", "r") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "current_song" in data
        assert "playlist_queue" in data

    def test_playlists_json_schema(self, init_data):
        """playlists.json 为 dict。"""
        with open(init_data / "playlists.json", "r") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_player_history_json_schema(self, init_data):
        """player_history.json 初始为空列表。"""
        with open(init_data / "player_history.json", "r") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_init_data_files_idempotent(self, init_data):
        """重复调用 init_data_files 不覆盖已有数据。"""
        # 修改 memory.json
        mem_path = init_data / "memory.json"
        with open(mem_path, "r") as f:
            original = json.load(f)
        original["profile"]["nickname"] = {"value": "E2E_Test"}
        with open(mem_path, "w") as f:
            json.dump(original, f)

        # 再次调用 init_data_files
        from agent.state.data_initializer import init_data_files
        init_data_files()

        # 确认 nickname 未被覆盖
        with open(mem_path, "r") as f:
            after = json.load(f)
        assert after["profile"]["nickname"]["value"] == "E2E_Test"

    def test_settings_json_creatable(self, init_data):
        """settings.json 可读写，含必要字段。"""
        from agent.state.settings_store import DEFAULT_SETTINGS
        with open(init_data / "settings.json", "r") as f:
            data = json.load(f)
        # 默认 settings 至少含 theme 字段
        if "theme" in DEFAULT_SETTINGS:
            assert "theme" in data


# ═══════════════════════════════════════════════════════════════
# 2. build_runtime_dj_state_from_disk
# ═══════════════════════════════════════════════════════════════

class TestBuildRuntimeDJState:
    """RuntimeDJState 从 disk 重建。"""

    def test_build_returns_dict_with_all_fields(self, init_data):
        """build_runtime_dj_state_from_disk 返回完整 dict。"""
        from agent.state.runtime_dj_state import build_runtime_dj_state_from_disk

        rds = build_runtime_dj_state_from_disk()

        assert isinstance(rds, dict)
        assert "current_song" in rds
        assert "current_segment" in rds
        assert "program_mood" in rds
        assert "current_scene" in rds
        assert "playlist_queue" in rds
        assert "pending_actions" in rds
        assert "segment_started_at_ms" in rds
        assert "updated_at_ms" in rds
        assert "updated_by" in rds
        # 默认值正确
        assert rds["current_song"] is None
        assert rds["playlist_queue"] == []
        assert rds["pending_actions"] == []
        assert rds["current_scene"] == "default"
        assert rds["program_mood"] == "neutral"

    def test_build_with_mock_program_state(self, init_data):
        """program_state.json 有值时，RDS 正确同步。"""
        from agent.state.program_state import save_program_state

        save_program_state({
            "program_date": "2026-07-17",
            "today_theme": "夏日测试",
            "current_segment": "music",
            "program_mood": "warm",
            "program_status": "running",
        })

        from agent.state.runtime_dj_state import build_runtime_dj_state_from_disk
        rds = build_runtime_dj_state_from_disk()

        assert rds["current_segment"] == "music"
        assert rds["program_mood"] == "warm"


# ═══════════════════════════════════════════════════════════════
# 3. build_graph — 8 节点
# ═══════════════════════════════════════════════════════════════

class TestBuildGraph:
    """StateGraph 编译。"""

    def test_graph_compiles_with_8_nodes(self, graph):
        """build_graph 编译成功，含 8 个节点。"""
        assert graph is not None

        g = graph.get_graph()
        # LangGraph get_graph().nodes 是一个 dict（key=node_name）
        node_names = set(g.nodes.keys()) if hasattr(g.nodes, 'keys') else set()

        expected = {"router", "context_builder", "dj_planner", "action_planner",
                     "action_executor", "emit_response", "feedback_extractor",
                     "tool_dispatcher"}
        for name in expected:
            assert name in node_names, f"缺少节点: {name}"
        assert len(node_names) >= len(expected)

    @pytest.mark.asyncio
    async def test_ainvoke_minimal_state_returns_without_error(self, graph):
        """最简 state ainvoke 不抛异常。"""
        result = await graph.ainvoke({
            "trigger_type": "system",
            "trigger_event": {"reason": "test"},
            "runtime_snapshot": {},
            "dependencies": {},
            "messages": [],
            "tool_messages": [],
            "tool_loop_count": 0,
            "tool_loop_max": 1,
            "pending_tool_calls": [],
        })
        assert result is not None
        # 返回值是 dict
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════
# 4. context_builder — 5 域（从 chat chain 移入）
# ═══════════════════════════════════════════════════════════════

class TestContextBuilderDomains:
    """context_builder_node 返回 5 域（不读 RuntimeDJState）。"""

    @pytest.mark.asyncio
    async def test_context_builder_returns_5_domains(self, e2e_context):
        """context_builder 返回 user/environment/program/playlist/player_mirror。"""
        from agent.nodes.context_builder import context_builder_node

        state = {"trigger_type": "conversation"}
        result = await context_builder_node(state)

        assert "user" in result
        assert "environment" in result
        assert "program" in result
        assert "playlist" in result
        assert "player_mirror" in result
        # 不包含 runtime_snapshot（由 Runtime 注入）
        assert "runtime_snapshot" not in result

    @pytest.mark.asyncio
    async def test_context_builder_environment_has_day_period(self, e2e_context):
        """environment 域含 day_period。"""
        from agent.nodes.context_builder import context_builder_node

        result = await context_builder_node({})
        env = result.get("environment", {})
        assert "day_period" in env
        assert env["day_period"] in ("morning", "before_noon", "noon", "afternoon",
                                     "evening", "night")


# ═══════════════════════════════════════════════════════════════
# 5. decide_init_mode — 3 分支
# ═══════════════════════════════════════════════════════════════

class TestDecideInitMode:
    """decide_init_mode 3 分支 + _push_agent_init_when_ready。"""

    PATCH_TARGET = "agent.runtime.lifespan"

    def test_first_init_when_no_program_state(self):
        """program_state.json 不存在 → FIRST_INIT。"""
        from agent.runtime import decide_init_mode

        with patch(f"{self.PATCH_TARGET}.load_program_state", return_value=None):
            mode = decide_init_mode()
        assert mode == InitMode.FIRST_INIT

    def test_new_day_init_when_date_mismatch(self):
        """日期不匹配 → NEW_DAY_INIT。"""
        from agent.runtime import decide_init_mode

        with patch(f"{self.PATCH_TARGET}.load_program_state",
                   return_value={"program_date": "2000-01-01"}):
            with patch(f"{self.PATCH_TARGET}.program_date_matches_today",
                       return_value=False):
                mode = decide_init_mode()
        assert mode == InitMode.NEW_DAY_INIT

    def test_resume_when_date_matches(self):
        """日期匹配 → RESUME。"""
        from agent.runtime import decide_init_mode

        import datetime
        today = datetime.date.today().isoformat()
        with patch(f"{self.PATCH_TARGET}.load_program_state",
                   return_value={"program_date": today}):
            with patch(f"{self.PATCH_TARGET}.program_date_matches_today",
                       return_value=True):
                mode = decide_init_mode()
        assert mode == InitMode.RESUME

    @pytest.mark.asyncio
    async def test_push_agent_init_on_first_init(self, event_queue):
        """FIRST_INIT → 推 AGENT_INIT 事件到 EventQueue。"""
        from agent.runtime import _push_agent_init_when_ready, _runtime_ready_event

        _runtime_ready_event.set()
        # patch lifespan 模块的 event_queue 为测试队列
        with patch("agent.runtime.lifespan.event_queue", event_queue):
            with patch("agent.runtime.lifespan.decide_init_mode",
                       return_value=InitMode.FIRST_INIT):
                await _push_agent_init_when_ready()

        assert event_queue.qsize() > 0

    @pytest.mark.asyncio
    async def test_skip_agent_init_on_resume(self, event_queue):
        """RESUME → 不推 AGENT_INIT。"""
        from agent.runtime import _push_agent_init_when_ready, _runtime_ready_event

        _runtime_ready_event.set()
        initial_size = event_queue.qsize()

        with patch("agent.runtime.lifespan.decide_init_mode",
                   return_value=InitMode.RESUME):
            await _push_agent_init_when_ready()

        assert event_queue.qsize() == initial_size


# ═══════════════════════════════════════════════════════════════
# 6. system_init 全链路
# ═══════════════════════════════════════════════════════════════

class TestSystemInitFullChain:
    """system_init → graph.ainvoke → ws_out_queue 全链路。"""

    @pytest.mark.asyncio
    async def test_system_init_produces_welcome_and_music(self, e2e_context):
        """system_init + first_init → 产出 status.welcome + music.play + chat.reply。"""
        from unittest.mock import patch
        ctx = e2e_context
        mock_llm = ctx["mock_llm_service"]

        # 覆盖 mock 返回 init_plan（system_init 专用）
        mock_llm.call_json.return_value = {
            "ok": True,
            "data": {
                "program_state": {
                    "program_date": "2026-07-17",
                    "today_theme": "夏日测试",
                    "current_segment": "intro",
                    "program_mood": "neutral",
                    "program_goal": "E2E 测试",
                    "voice_style": "warm",
                    "speech_rate": 0.8,
                    "speak_frequency": "low",
                    "program_status": "running",
                },
                "initial_playlist": [
                    {"name": "江南", "artist": "林俊杰", "scene_match": "default"},
                    {"name": "爱错(Live)", "artist": "王力宏", "scene_match": "default"},
                    {"name": "Happy", "artist": "Pharrell Williams", "scene_match": "default"},
                    {"name": "特别的人", "artist": "方大同", "scene_match": "default"},
                    {"name": "晴天", "artist": "周杰伦", "scene_match": "default"},
                ],
                "welcome_text": "E2E 测试欢迎！",
            },
        }

        state = build_initial_state(
            ctx,
            trigger_type="system_init",
            trigger_event={"reason": "first_init", "init_mode": "first_init",
                           "ts": 1234567890},
            init_mode="first_init",
        )

        with patch("agent.nodes.action_executor._music.get_play_url",
                    return_value="http://localhost:8000/api/proxy/audio?url=https://example.com/test.mp3"):
            result = await ctx["graph"].ainvoke(state)

        # ── 断言 Graph 结果 ──
        pending = result.get("pending_payload") or {}

        # status.welcome
        assert pending.get("status_update", {}).get("type") == "welcome"
        assert pending["status_update"]["init_mode"] == "first_init"

        # chat.reply
        assert pending.get("chat_reply") == "E2E 测试欢迎！"

        # music.play
        assert result.get("should_play_music") is True
        # LLM 输出 name+artist→系统匹配 real song_id，江南→108914
        assert pending["music_play"]["song"]["id"] == "108914"
        assert pending["music_play"]["song"]["artists"][0]["name"] == "林俊杰"
        assert pending["music_play"]["auto_play"] is True

        # turn_count
        assert result.get("turn_count", 0) >= 1

        # ── 断言 ws_out_queue ──
        from agent.runtime.ws_sender import ws_out_queue
        msgs = drain_queue(ws_out_queue)
        chat_msgs = [m for m in msgs
                     if m.get("type") == "chat" and m.get("subtype") == "reply"]
        music_msgs = [m for m in msgs
                      if m.get("type") == "music" and m.get("subtype") == "play"]
        assert len(chat_msgs) == 1
        assert chat_msgs[0]["payload"]["text"] == "E2E 测试欢迎！"
        assert len(music_msgs) == 1
        assert music_msgs[0]["payload"]["song"]["id"] == "108914"
        assert len(music_msgs[0]["payload"]["song"]["artists"]) >= 1

    @pytest.mark.asyncio
    async def test_system_init_without_llm_falls_back_to_mock(self, e2e_context):
        """无 LLMService（__refs__ 不注入）→ 回退 mock init_plan，不抛异常。"""
        ctx = e2e_context
        # 移除 mock_llm_service
        state = build_initial_state(
            ctx,
            trigger_type="system_init",
            trigger_event={"reason": "first_init", "init_mode": "first_init"},
            init_mode="first_init",
        )
        state["__refs__"] = {"event_service": ctx["event_service"], "llm_service": None}

        result = await ctx["graph"].ainvoke(state)

        # 无 LLM 也应走完全链路（用 mock init_plan）
        pending = result.get("pending_payload") or {}
        assert pending.get("status_update", {}).get("type") == "welcome"
        # last_error 不应有 LLM 相关错误
        last_error = result.get("last_error")
        if last_error:
            assert "LLM" not in last_error.get("code", "")
