"""CONVERSATION_PROMPT — 标准 4 块输出。

★ v0.6 H3/H4：DJ Planner 单次 LLM 调用，输出 4 块
★ v0.6 N 项：REPLAN 模式复用本 prompt（+ extra system message）
★ 输出 schema 统一：program_decision / playlist_decision / dialogue_decision / tool_calls
★ formatter 接收 context dict，不与 LangGraph AgentState 耦合
"""

CONVERSATION_PROMPT = """你是 SoulChord AI DJ，一个通过对话和音乐陪伴用户的 AI 电台。
当前为 {mode} 事件，请根据以下上下文输出节目规划。

【用户刚刚说】
{user_text}

【工具执行结果】
{tool_results}

【用户信息】
{user_info}

【环境信息】
{environment_info}

【节目状态】
{program_info}

【播放状态】
{playback_info}

【可用 DJ 工具】
1. play_music — 播放指定歌曲。必须提供 query（歌曲名/歌手名）。song_id 由工具搜索返回，不要自己编造。参数：{{"query": "搜索关键词"}}
2. manage_playlist — 管理播放列表
3. get_environment_context — 获取环境信息（天气/时间/位置/活动）
4. query_user_preference — 查询用户偏好和记忆
5. update_memory — 更新用户记忆
6. query_calendar — 查询飞书日程
{replan_extra}

【playlist_decision.action 选择规则】
- insert_now：用户明确要求播放某首歌（"放一首XX"、"播放XX"、"我想听XX"）。只输出那首歌，不加其他歌曲。
- append：你想推荐几首歌给用户，或者在现有节目基础上补充歌曲。
- replace：用户要求换节目（"换点别的"、"今天想听XX风格"），或者当前节目需要整体更换。
- keep：只是聊天，不需要改变播放列表。

【重要：song_id 不要出现在你的输出中！】
你输出的歌曲只有 name 和 artist，song_id 由 play_music 工具搜索返回。如果你在 tool_calls 中请求了 play_music 搜索，系统会自动匹配搜索结果中的真实 song_id。

请严格按以下 JSON 格式输出，不要添加多余文本，不在 JSON 外包 markdown 代码块：

{{
  "program_decision": {{
    "today_theme": "string 或 null（整日主题，不需要更新时填 null）",
    "current_segment": "string 或 null（intro/music/transition/talk）",
    "program_mood": "string 或 null（energetic/warm/reflective/neutral）",
    "program_goal": "string 或 null",
    "voice_style": "string 或 null（warm/cool/gentle/lively）",
    "speech_rate": "float 或 null",
    "speak_frequency": "string 或 null（low/medium/high）"
  }},
  "playlist_decision": {{
    "action": "string（keep/replace/append/insert_now）",
    "songs": [
      {{"name": "string", "artist": "string", "scene_match": "string"}}
    ],
    "reason": "string"
  }},
  "dialogue_decision": {{
    "should_speak": true,
    "text": "string（要对用户说的话）",
    "style": "string（warm/cool/gentle/lively）"
  }},
  "tool_calls": [
    {{"name": "tool_name", "args": {{"key": "value"}}}}
  ]
}}
"""


# ── 内部辅助：从 context dict 构建 prompt 各段落 ──


def _build_user_info(context: dict) -> str:
    """用户信息段落。"""
    user = context.get("user", {}) or {}
    env = context.get("environment", {}) or {}
    parts = []
    nickname = user.get("nickname")
    if nickname:
        parts.append(f"用户昵称：{nickname}")
    parts.append(f"音乐偏好：{user.get('music_profile', '暂无画像')}")
    mood = env.get("user_mood")
    if mood:
        parts.append(f"用户心情：{mood}")
    return "\n".join(parts) or "暂无用户信息"


def _build_environment_info(context: dict) -> str:
    """环境信息段落。"""
    env = context.get("environment", {}) or {}
    parts = []
    parts.append(f"时间段：{env.get('day_period', '未知')}")
    weather = env.get("weather")
    if weather:
        parts.append(f"天气：{weather}")
    activity = env.get("current_activity")
    if activity:
        parts.append(f"活动：{activity}")
    return "\n".join(parts)


def _build_program_info(context: dict) -> str:
    """节目状态段落。"""
    prog = context.get("program", {}) or {}
    snap = context.get("runtime_snapshot", {}) or {}
    parts = []
    parts.append(f"今日主题：{prog.get('today_theme', '未设置')}")
    parts.append(f"节目风格：{snap.get('program_mood', prog.get('program_mood', 'neutral'))}")
    parts.append(f"当前段：{snap.get('current_segment', prog.get('current_segment', 'intro'))}")
    parts.append(f"当前场景：{snap.get('current_scene', 'default')}")
    parts.append(f"交互强度：{snap.get('interaction_level', 'low')}")
    goal = prog.get("program_goal")
    if goal:
        parts.append(f"今日目标：{goal}")
    return "\n".join(parts)


def _build_playback_info(context: dict) -> str:
    """播放状态段落。"""
    mirror = context.get("player_mirror", {}) or {}
    snap = context.get("runtime_snapshot", {}) or {}
    parts = []
    current_name = (
        mirror.get("current_song_name")
        or (snap.get("current_song") or {}).get("name")
    )
    if current_name:
        parts.append(f"当前播放：{current_name}")
    queue = mirror.get("playlist_queue", []) or snap.get("playlist_queue", [])
    parts.append(f"队列余量：{len(queue)} 首")
    is_playing = mirror.get("is_playing", snap.get("is_playing", False))
    has_current = bool(current_name)
    if not has_current:
        parts.append("播放状态：未播放")
    elif is_playing:
        parts.append("播放状态：播放中")
    else:
        parts.append("播放状态：已暂停")
    return "\n".join(parts)


# ── 公开 API ──


def format_conversation_prompt(context: dict, replan_reason: str = "") -> str:
    """构建 CONVERSATION_PROMPT（用于 conversation / replan 模式）。

    Args:
        context: 上下文 dict（由 dj_planner_node 从 AgentState 提取），
                 不含 AgentState 直接引用，不与 LangGraph 耦合。
                 必需键：trigger_type, user, environment, program,
                        playlist, player_mirror, runtime_snapshot
        replan_reason: 非空时表示 REPLAN 模式，追加 extra system message

    Returns:
        完整 prompt 字符串
    """
    mode = "REPLAN" if replan_reason else "CONVERSATION"

    replan_extra = ""
    if replan_reason:
        replan_extra = (
            "\n【额外说明】\n"
            f"当前为 REPLAN 事件：{replan_reason}。\n"
            "请先使用 play_music 工具搜索真实歌曲（输出 tool_calls）。\n"
            "步骤：先输出 tool_calls → 执行搜索 → 在下一轮根据搜索结果输出 playlist_decision（只含 name+artist，song_id 由系统自动匹配）。"
        )

    return CONVERSATION_PROMPT.format(
        mode=mode,
        user_text=context.get("user_text", ""),
        tool_results=context.get("tool_results", "（无）"),
        user_info=_build_user_info(context),
        environment_info=_build_environment_info(context),
        program_info=_build_program_info(context),
        playback_info=_build_playback_info(context),
        replan_extra=replan_extra,
    )
