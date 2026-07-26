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

# ★ v9.13: INIT 目标队列长度 — LLM 规划足够歌曲供逐首解析
INIT_TARGET_QUEUE_SIZE = 12


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

    支持 Tool Loop（v9.1）：
    - Round 1：调 LLM 生成 init_plan，注入 play_music 工具调用
    - Round 2：tool_messages 已有搜索结果，透传 init_plan 到 action_planner

    优先调 LLM（含重试 + 降级），无 LLMService 时回退 mock。
    """
    # Round 2：tool 搜索结果已就绪，直接透传 init_plan
    tool_messages = state.get("tool_messages", []) or []
    if tool_messages:
        init_plan = state.get("init_plan") or {}
        logger.info("Init round 2: tool_messages=%d, passing init_plan to action_planner",
                    len(tool_messages))
        return {
            "llm_decision": None,
            "init_plan": init_plan,
            "pending_tool_calls": [],
            "next_node": "action_planner",
        }

    # Round 1：调 LLM 或 mock
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

    # ★ P6: Inject recommend_music tool call for initial_playlist
    pending_calls = _inject_recommend_music_tools(init_plan)

    return {
        "llm_decision": None,
        "init_plan": init_plan,
        "pending_tool_calls": pending_calls,
        "next_node": "tool_dispatcher" if pending_calls else "action_planner",
    }


def _inject_recommend_music_tools(init_plan: dict) -> list:
    """为 init_plan 注入推荐音乐工具调用（单次 recommend_music 调用）。

    ★ P6：将所有 LLM 规划歌曲打包为一个 recommend_music(songs=[...]) 调用，
    tool_dispatcher 批量搜索解析，返回已解析歌曲（含真实 song_id）。

    之前：N 次 play_music(query) 调用，tool_messages 有 N 组原始搜索结果。
    现在：1 次 recommend_music(songs) 调用，tool_messages 有 1 组已解析结果。
    """
    initial_playlist = init_plan.get("initial_playlist", [])
    if not initial_playlist:
        return []

    songs = []
    for song in initial_playlist[:INIT_TARGET_QUEUE_SIZE]:
        name = song.get("name", "")
        artist = song.get("artist", "")
        if name and artist:
            songs.append({
                "name": name,
                "artist": artist,
                "reason": "initial_playlist",
            })

    if songs:
        logger.info("Injected recommend_music tool call for %d songs (init_plan)", len(songs))
        return [{"name": "recommend_music", "args": {"songs": songs}}]
    return []


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
    context["timer_type"] = trigger_event.get("scheduler_loop", trigger_event.get("timer_type", "heartbeat"))
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

    支持 Tool Loop Round 2（v9.2 修复）：
    - Round 1：调 LLM 搜索歌曲（输出 tool_calls）
    - Round 2：搜索结果已就绪，直接基于搜索结果构建播放列表决策

    优先调 LLM，无 LLMService 时回退 mock。
    """
    tool_messages = state.get("tool_messages", []) or []

    # ★ Round 2：搜索结果已就绪，直接基于搜索结果构建播放列表（跳过 LLM）
    if tool_messages:
        return _build_replan_from_search(tool_messages, state, snapshot)

    # Round 1：调 LLM 搜索
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
            if name == "recommend_music":
                lines.append(f"🎵 recommend_music 推荐了 {len(songs)}/{result.get('requested', '?')} 首歌曲：")
                for i, s in enumerate(songs, 1):
                    sid = s.get("id", s.get("song_id", "?"))
                    sname = s.get("name", "?")
                    sartist = ", ".join(a.get("name", "") for a in (s.get("artists", []) or [])) or s.get("artist", "?")
                    reason = s.get("_recommend_reason", "")
                    reason_part = f" —— {reason}" if reason else ""
                    lines.append(f"   {i}. song_id={sid} —— {sname} —— {sartist}{reason_part}")
            else:
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
    """确保 LLM decision 包含 recommend_music 工具调用。

    ★ P6：LLM 推荐 N 首歌曲 → 打包为一个 recommend_music(songs=[...]) 调用。
    tool_dispatcher 批量解析所有歌曲，返回含真实 song_id 的列表。

    之前：N 次 play_music(query) 调用 → N 组原始搜索结果 → Round 2 启发式 dedup
    现在：1 次 recommend_music(songs) 调用 → 1 组已解析结果 → Round 2 直接使用
    """
    playlist = decision.get("playlist_decision", {}) or {}
    songs = playlist.get("songs", []) or []
    tool_calls = decision.get("tool_calls", []) or []

    # 检查是否已有 recommend_music 调用
    has_recommend = any(
        tc.get("name") == "recommend_music" for tc in tool_calls
    )
    if has_recommend:
        logger.debug("_ensure_tool_calls: recommend_music already present")
        return decision

    # 收集所有未处理的歌曲
    song_list = []
    for song in songs:
        name = song.get("name", "")
        artist = song.get("artist", "")
        reason = song.get("reason", song.get("scene_match", ""))
        if name and artist:
            song_list.append({"name": name, "artist": artist, "reason": reason})

    if song_list:
        tool_calls.append({"name": "recommend_music", "args": {"songs": song_list}})
        logger.info("_ensure_tool_calls: injected recommend_music for %d songs", len(song_list))
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
# Tool Loop Round 2 辅助 — 从搜索结果直接构建播放列表
# ═══════════════════════════════════════════════════════════════


def _build_replan_from_search(tool_messages: list, state: dict, snapshot: dict) -> dict:
    """Tool Loop Round 2：从搜索结果直接构建播放列表决策，跳过 LLM。

    与 _handle_init Round 2 透传策略不同（init_plan 已包含完整节目规划），
    REPLAN Round 2 需要实时基于搜索结果构建播放列表，
    因为 Round 1 的 LLM decision 只包含 tool_calls（搜索请求），不包含 playlist_decision。

    v9.2 修复：搜索结果已就绪时不再调 LLM，避免 REPLAN prompt 中
    "先输出 tool_calls" 的指令让 LLM 在 Round 2 继续输出搜索请求而非 playlist_decision。

    ★ P5.x：搜索结果先按歌曲实体聚类+版本过滤，再入 playlist。
      避免同一首歌的 Live/Remix/翻唱版本污染队列。

    ★ P6：优先从 recommend_music 结果提取（已解析歌曲，无需 dedup），
      向后兼容 play_music 搜索结果。
    """
    # ★ P6：优先从 recommend_music 结果提取
    resolved_songs = _extract_recommended_songs(tool_messages)

    # 向后兼容：从 play_music 搜索结果提取 + dedup
    if not resolved_songs:
        raw_songs = _extract_songs_from_tool_messages(tool_messages)
        resolved_songs = _dedupe_search_results_to_unique_songs(raw_songs, max_songs=5)

    reason = (state.get("trigger_event") or {}).get("reason", "播放列表补充")

    if resolved_songs:
        prog = snapshot.get("program", state.get("program", {})) or {}
        decision = {
            "program_decision": {
                "today_theme": prog.get("today_theme", None),
                "current_segment": "music",
                "program_mood": prog.get("program_mood", snapshot.get("program_mood", "neutral")),
                "program_goal": "继续陪伴用户",
                "voice_style": None,
                "speech_rate": None,
                "speak_frequency": None,
            },
            "playlist_decision": {
                "action": "add",
                "songs": [
                    {"name": s.get("name", ""), "artist": _extract_artist_str(s), "scene_match": "default"}
                    for s in resolved_songs
                ],
                "reason": f"REPLAN搜索结果自动续杯（{reason}）",
            },
            "dialogue_decision": {
                "should_speak": False,
                "text": "",
                "style": "warm",
            },
            "tool_calls": [],
        }
        logger.info("Replan round 2: built playlist from %d unique songs, reason=%r",
                    len(resolved_songs), reason)
        return _package_decision(decision, state)

    # 搜索结果为空 → 回退 mock（极端兜底，不应发生）
    logger.warning("Replan round 2: no songs extracted from %d tool_messages, using mock fallback",
                   len(tool_messages))
    context = _build_prompt_context(state, snapshot, trigger_type="replan_event")
    decision = _mock_replan_decision(context)
    return _package_decision(_ensure_tool_calls(decision), state)


def _extract_songs_from_tool_messages(tool_messages: list) -> list[dict]:
    """从 tool_messages 中提取 play_music 搜索结果中的歌曲（去重，保留搜索顺序）。"""
    seen = set()
    result = []
    for msg in reversed(tool_messages):
        if msg.get("name") != "play_music":
            continue
        res = msg.get("result", {})
        if not isinstance(res, dict):
            continue
        songs = res.get("songs", [])
        for s in songs:
            sid = s.get("id", "") or s.get("song_id", "")
            if sid and sid not in seen:
                seen.add(sid)
                result.append(s)
    return result


def _extract_recommended_songs(tool_messages: list) -> list[dict]:
    """从 recommend_music 工具结果中提取已解析歌曲。

    recommend_music 返回的 result.songs 已包含真实 song_id
    和 sources[]，不需要进一步解析或去重。
    """
    seen = set()
    result = []
    for msg in tool_messages:
        if msg.get("name") != "recommend_music":
            continue
        res = msg.get("result", {})
        if not isinstance(res, dict):
            continue
        songs = res.get("songs", [])
        for s in songs:
            sid = s.get("id", "") or s.get("song_id", "")
            if sid and sid not in seen:
                seen.add(sid)
                result.append(s)
    return result


def _dedupe_search_results_to_unique_songs(songs: list[dict], max_songs: int = 5) -> list[dict]:
    """搜索结果按歌曲实体聚类，每个实体只保留最佳版本。

    问题背景：
      搜索 "午后" 返回 "午后"、"午后(Live)"、"午后 Remix" 等多个版本，
      这些是同一首歌的不同候选版本，不应作为多首推荐歌曲入队。

    做法：
      1. 用 build_song_dedup_key 归一化 (标题, 歌手) 作为实体 key
      2. 同一 key 的多条结果中，选版本分数最低的（原版 < Live < Cover）
      3. 保留搜索结果的原始顺序，取前 max_songs 首

    Args:
        songs: 搜索结果列表（来自 _extract_songs_from_tool_messages）
        max_songs: 最大返回歌曲数

    Returns:
        去重+选优后的列表，每个实体最多一首
    """
    from agent.services.song_resolver import build_song_dedup_key, _version_score

    # 第一遍：按实体 key 分组，每组保留最佳版本
    groups: dict[tuple[str, str], dict] = {}
    for s in songs:
        key = build_song_dedup_key(s)
        if not key[0]:
            continue
        if key not in groups:
            groups[key] = dict(s)
        else:
            existing = _version_score(groups[key].get("name", ""))
            current = _version_score(s.get("name", ""))
            if current < existing:  # 分数越低越优先（原版=0 < Live=10 < Cover=20）
                groups[key] = dict(s)

    # 第二遍：按原始顺序输出，同一实体只输出最佳版本
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for s in songs:
        key = build_song_dedup_key(s)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        result.append(groups[key])
        if len(result) >= max_songs:
            break

    return result


def _extract_artist_str(song: dict) -> str:
    """从搜索结果 song dict 中提取歌手名字符串（兼容 artists 数组和 artist 字符串）。"""
    artists = song.get("artists", []) or song.get("ar", [])
    if artists and isinstance(artists, list):
        return ", ".join(a.get("name", "") for a in artists if a.get("name"))
    return song.get("artist", "")


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
        "welcome_text": f"你好，欢迎来到 SoulChord！今天是{today}，让我陪你度过美好的一天。先来一首林俊杰的《江南》吧。",
    }


def _mock_conversation_decision(context: dict) -> dict:
    """Mock LLM 对 CONVERSATION 事件的 4 块输出。"""
    # 返回前 3 首真实歌曲作为默认播放列表（只含 name+artist，song_id 由代码匹配）
    mock_songs = [{"name": s["name"], "artist": s["artist"]} for s in _REAL_SONGS[:3]]
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
                {"name": s["name"], "artist": s["artist"], "scene_match": "default"}
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
