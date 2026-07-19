"""DJ Planner 节点 — plan_owner。

★ v0.1.1 B 项：plan_owner（决定**为什么做**，不写 actions[]）
★ v0.6 4 prompt 模式：INIT / CONVERSATION / TIMER / REPLAN
★ v0.1.2 P1-4：读 RuntimeDJState 经 state["runtime_snapshot"]
★ v0.1.2 P0-1：return dict（partial update），不调 state.update()
"""

import logging
from typing import Optional

from agent.prompts.init_prompt import format_init_prompt
from agent.prompts.conversation_prompt import format_conversation_prompt
from agent.prompts.timer_prompt import format_timer_prompt
from agent.shared.enums import InitMode, ProgramMood

logger = logging.getLogger(__name__)


async def dj_planner_node(state: dict) -> dict:
    """DJ Planner 主节点 — 单次 LLM 调用。

    4 prompt 模式分发（★ v0.6）：
      - system_init  → INIT_PROMPT（生成 init_plan）
      - conversation → CONVERSATION_PROMPT（标准 4 块）
      - timer_event  → TIMER_PROMPT（简化 4 块）
      - replan_event → CONVERSATION_PROMPT + reason（复用）
      - 其他         → 空返回

    Returns:
        dict（partial update）：llm_decision / init_plan / pending_tool_calls / next_node
    """
    trigger_type = state.get("trigger_type", "")
    snapshot = state.get("runtime_snapshot") or {}

    if trigger_type == "system_init":
        return await _handle_init(state, snapshot)
    elif trigger_type == "conversation":
        return await _handle_conversation(state, snapshot)
    elif trigger_type == "timer_event":
        return await _handle_timer(state, snapshot)
    elif trigger_type == "replan_event":
        return await _handle_replan(state, snapshot)
    else:
        # system / user_control / fallback — 无需 LLM 决策
        return {
            "llm_decision": None,
            "init_plan": None,
            "pending_tool_calls": [],
            "next_node": "action_planner",
        }


# ═══════════════════════════════════════════════════════════════
# 4 prompt 模式 handler
# ═══════════════════════════════════════════════════════════════


async def _handle_init(state: dict, snapshot: dict) -> dict:
    """INIT_PROMPT 分支 — 生成 init_plan。

    优先调 LLM（含重试 + 降级），无 LLMService 时回退 mock。
    """
    llm = _get_llm_service(state)
    init_mode = state.get("init_mode", InitMode.FIRST_INIT)
    env = state.get("environment", {}) or {}
    user = state.get("user", {}) or {}
    program = state.get("program", {}) or {}

    prompt = format_init_prompt(
        init_mode=init_mode if isinstance(init_mode, str) else init_mode.value,
        date=program.get("program_date", ""),
        today=program.get("program_date", ""),
        weather="",
        day_period=env.get("day_period", ""),
        scene=snapshot.get("current_scene", "default"),
        music_profile=str(user.get("music_profile", "")),
    )

    if llm:
        result = await llm.call_json(prompt)
        if result["ok"]:
            init_plan = result["data"]
        else:
            return _llm_error_result(result["error"])
    else:
        # 无 LLMService（测试 / 未配置）→ 回退 mock
        init_plan = _mock_init_plan(init_mode)

    return {
        "llm_decision": None,
        "init_plan": init_plan,
        "pending_tool_calls": [],
        "next_node": "action_planner",
    }


async def _handle_conversation(state: dict, snapshot: dict) -> dict:
    """CONVERSATION_PROMPT 分支 — 标准 4 块输出。

    优先调 LLM，无 LLMService 时回退 mock。
    """
    llm = _get_llm_service(state)
    context = _build_prompt_context(state, snapshot, trigger_type="conversation")
    prompt = format_conversation_prompt(context)

    if llm:
        result = await llm.call_json(prompt)
        if result["ok"]:
            decision = result["data"]
            return _package_decision(decision, state)
        else:
            return _llm_error_result(result["error"])

    # 无 LLMService → 回退 mock
    decision = _mock_conversation_decision(context)
    return _package_decision(decision, state)


async def _handle_timer(state: dict, snapshot: dict) -> dict:
    """TIMER_PROMPT 分支 — 简化 4 块输出。

    优先调 LLM，无 LLMService 时回退 mock。
    """
    llm = _get_llm_service(state)
    trigger_event = state.get("trigger_event") or {}
    context = _build_prompt_context(state, snapshot, trigger_type="timer_event")
    context["timer_type"] = trigger_event.get("timer_type", "heartbeat")
    prompt = format_timer_prompt(context)

    if llm:
        result = await llm.call_json(prompt)
        if result["ok"]:
            decision = result["data"]
            return _package_decision(decision, state)
        else:
            return _llm_error_result(result["error"])

    # 无 LLMService → 回退 mock
    decision = _mock_timer_decision(context)
    return _package_decision(decision, state)


async def _handle_replan(state: dict, snapshot: dict) -> dict:
    """REPLAN 分支 — 复用 CONVERSATION_PROMPT + reason。

    优先调 LLM，无 LLMService 时回退 mock。
    """
    llm = _get_llm_service(state)
    reason = (state.get("trigger_event") or {}).get("reason", "播放列表已空，需要重新规划")
    context = _build_prompt_context(state, snapshot, trigger_type="replan_event")
    prompt = format_conversation_prompt(context, replan_reason=reason)

    if llm:
        result = await llm.call_json(prompt)
        if result["ok"]:
            decision = result["data"]
            # ★ 安全网：LLM 若直接输出歌曲但没请求搜索，补一个 play_music 工具调用
            return _package_decision(_ensure_tool_calls(decision), state)
        else:
            return _llm_error_result(result["error"])

    # 无 LLMService → 回退 mock
    decision = _mock_replan_decision(context)
    return _package_decision(_ensure_tool_calls(decision), state)


# ═══════════════════════════════════════════════════════════════
# 内部工具函数
# ═══════════════════════════════════════════════════════════════


def _get_llm_service(state: dict):
    """从 __refs__ 获取 LLMService 实例。

    未提供（测试 / 未配置）→ 返回 None，调用方回退 mock。
    """
    refs = state.get("__refs__") or {}
    return refs.get("llm_service")


def _llm_error_result(error: dict) -> dict:
    """LLM 调用失败时的降级返回。

    Node 层面不 raise 异常，返回结构化 last_error + 路由到 action_planner。
    """
    logger.warning("LLM call failed: code=%s message=%s", error.get("code"), error.get("message"))
    return {
        "llm_decision": None,
        "init_plan": None,
        "pending_tool_calls": [],
        "last_error": error,
        "next_node": "action_planner",
    }


def _build_prompt_context(state: dict, snapshot: dict, trigger_type: str) -> dict:
    """从 AgentState 提取 prompt 所需的 context dict。

    返回纯 dict（无 AgentState 引用），保持 prompt formatter 与 LangGraph 解耦。
    """
    trigger_event = state.get("trigger_event") or {}
    return {
        "trigger_type": trigger_type,
        "user_text": trigger_event.get("text", ""),  # 用户刚说的原文
        "tool_results": _format_tool_results(state.get("tool_messages", [])),
        "user": state.get("user", {}),
        "environment": state.get("environment", {}),
        "program": state.get("program", {}),
        "playlist": state.get("playlist", {}),
        "player_mirror": state.get("player_mirror", {}),
        "runtime_snapshot": snapshot,
    }


def _format_tool_results(tool_messages: list) -> str:
    """将 tool_messages 格式化为 LLM 可读的文本。

    在 tool loop 第二轮，LLM 通过此段落看到搜索/工具执行的真实结果。
    """
    if not tool_messages:
        return "（无）"

    lines = []
    for msg in tool_messages:
        name = msg.get("name", "unknown")
        status = msg.get("status", "ok")
        result = msg.get("result", {}) or {}
        if isinstance(result, dict) and result.get("songs"):
            songs = result["songs"]
            lines.append(f"🔍 play_music 搜索 \"{result.get('query', '')}\" 返回了 {len(songs)} 首歌曲：")
            for i, s in enumerate(songs, 1):
                sid = s.get("id", s.get("song_id", "?"))
                sname = s.get("name", "?")
                sartist = ", ".join(a.get("name", "") for a in (s.get("artists", []) or [])) or s.get("artist", "?")
                lines.append(f"   {i}. song_id={sid} —— {sname} —— {sartist}")
        elif isinstance(result, dict) and result.get("play_url"):
            lines.append(f"▶ play_music 获取播放链接成功：song_id={result.get('song_id', '?')}")
        else:
            lines.append(f"  {name}: {status}")

    return "\n".join(lines) if lines else "（无）"


def _ensure_tool_calls(decision: dict) -> dict:
    """确保 LLM decision 包含 play_music 工具调用。

    安全网：如果 LLM 直接输出了歌曲但没有请求搜索，为其注入
    一个 play_music 工具调用，让 tool loop 先去搜索真实歌曲。
    """
    playlist = decision.get("playlist_decision", {}) or {}
    songs = playlist.get("songs", []) or []
    tool_calls = decision.get("tool_calls", []) or []

    # 歌曲非空 且 无 play_music 工具调用 → 注入搜索
    has_play_music = any(tc.get("name") == "play_music" for tc in tool_calls)
    if songs and not has_play_music:
        first = songs[0]
        query = first.get("name", "") or first.get("query", "")
        if query:
            logger.info("_ensure_tool_calls: injecting play_music query=%s", query)
            tool_calls.append({"name": "play_music", "args": {"query": query}})
            decision["tool_calls"] = tool_calls
    return decision


def _package_decision(decision: dict, state: dict) -> dict:
    """将 LLM decision 打包为 Node 返回值。

    从 decision.tool_calls 提取 pending_tool_calls，按 Tool Loop 规则设 next_node。
    ★ 路由决策仅依赖 Tool Loop 机械规则（pending_tool_calls + count < max），
      不涉及业务逻辑。路由由 conditional edge 消费。
    """
    tool_calls = decision.get("tool_calls", [])
    pending = [{"name": tc["name"], "args": tc.get("args", {})} for tc in tool_calls]

    count = state.get("tool_loop_count", 0)
    max_count = state.get("tool_loop_max", 1)
    next_node = "tool_dispatcher" if (pending and count < max_count) else "action_planner"

    return {
        "llm_decision": decision,
        "init_plan": None,
        "pending_tool_calls": pending,
        "next_node": next_node,
    }


# ═══════════════════════════════════════════════════════════════
# MVP Mock — 严格模拟未来 LLM JSON 输出
# ═══════════════════════════════════════════════════════════════


# 真实网易云歌曲 ID（mock 模式也能播放）
_REAL_SONGS = [
    {"song_id": "108914", "name": "江南", "artist": "林俊杰", "scene_match": "default"},
    {"song_id": "25642214", "name": "爱错(Live)", "artist": "王力宏", "scene_match": "default"},
    {"song_id": "26548584", "name": "Happy", "artist": "Pharrell Williams", "scene_match": "default"},
    {"song_id": "28403111", "name": "特别的人", "artist": "方大同", "scene_match": "default"},
    {"song_id": "3339230677", "name": "晴天", "artist": "周杰伦", "scene_match": "default"},
    {"song_id": "4336330", "name": "Here Comes The Sun", "artist": "The Beatles", "scene_match": "default"},
    {"song_id": "1977929099", "name": "午后阳光 (海浪声+钢琴)", "artist": "睡前音乐盒", "scene_match": "default"},
    {"song_id": "1855567912", "name": "学习专注力", "artist": "纯音乐", "scene_match": "default"},
    {"song_id": "2195553", "name": "Sunny", "artist": "Boney M.", "scene_match": "default"},
    {"song_id": "1394167216", "name": "知我", "artist": "国风堂, 哦漏", "scene_match": "default"},
]


def _mock_init_plan(init_mode) -> dict:
    """MVP Mock：生成假 init_plan。

    init_plan 是 INIT_PROMPT 专用输出结构（program_state + initial_playlist + welcome），
    与 conversation/timer/replan 的 4 块输出结构不同。
    """
    import datetime
    today = datetime.date.today().isoformat()

    program_state = {
        "program_date": today,
        "today_theme": "今日陪伴",
        "current_segment": "intro",
        "program_mood": "neutral",
        "program_goal": "陪伴用户",
        "voice_style": "warm",
        "speech_rate": 0.8,
        "speak_frequency": "low",
        "program_status": "running",
    }

    initial_playlist = list(_REAL_SONGS)

    return {
        "program_state": program_state,
        "initial_playlist": initial_playlist,
        "first_song_id": "108914",
        "welcome_text": f"你好，欢迎来到 SoulChord！今天是{today}，让我陪你度过美好的一天。先来一首林俊杰的《江南》吧。",
    }


def _mock_conversation_decision(context: dict) -> dict:
    """Mock LLM 对 CONVERSATION 事件的 4 块输出。"""
    # 返回前 3 首真实歌曲作为默认播放列表
    mock_songs = [{"id": s["song_id"], "name": s["name"], "artist": s["artist"]} for s in _REAL_SONGS[:3]]
    return {
        "program_decision": {
            "today_theme": None,
            "current_segment": None,
            "program_mood": None,
            "program_goal": None,
            "voice_style": None,
            "speech_rate": None,
            "speak_frequency": None,
        },
        "playlist_decision": {
            "action": "replace",
            "songs": mock_songs,
            "reason": "默认播放列表",
        },
        "dialogue_decision": {
            "should_speak": True,
            "text": "嗯，我听到了。让我想想怎么调整。",
            "style": "warm",
        },
        "tool_calls": [],
    }


def _mock_timer_decision(context: dict) -> dict:
    """Mock LLM 对 TIMER 事件的 4 块输出。"""
    timer_type = context.get("timer_type", "heartbeat")
    if timer_type == "playlist_health":
        reason = "播放列表健康检查，无需调整"
    else:
        reason = f"定时检查（{timer_type}），无需调整"

    return {
        "program_decision": {
            "today_theme": None,
            "current_segment": None,
            "program_mood": None,
            "program_goal": None,
            "voice_style": None,
            "speech_rate": None,
            "speak_frequency": None,
        },
        "playlist_decision": {
            "action": "keep",
            "songs": [],
            "reason": reason,
        },
        "dialogue_decision": {
            "should_speak": False,
            "text": "",
            "style": "warm",
        },
        "tool_calls": [],
    }


def _mock_replan_decision(context: dict) -> dict:
    """Mock LLM 对 REPLAN 事件的 4 块输出 — queue 空时重建 playlist。"""
    prog = context.get("program", {}) or {}
    return {
        "program_decision": {
            "today_theme": prog.get("today_theme", "今日陪伴"),
            "current_segment": "music",
            "program_mood": prog.get("program_mood", "neutral"),
            "program_goal": "继续陪伴用户",
            "voice_style": None,
            "speech_rate": None,
            "speak_frequency": None,
        },
        "playlist_decision": {
            "action": "replace",
            "songs": [
                {"song_id": s["song_id"], "name": s["name"], "artist": s["artist"], "scene_match": "default"}
                for s in _REAL_SONGS
            ],
            "reason": "播放列表已空，重新生成 10 首推荐",
        },
        "dialogue_decision": {
            "should_speak": False,
            "text": "",
            "style": "warm",
        },
        "tool_calls": [],
    }
