"""TIMER_PROMPT — 简化 4 块输出。

★ v0.6 H20 加强：DJ Planner 统一负责所有节目策划事件（含定时事件）
★ 4 种 timer_type：feishu / heartbeat / playlist_health / program_tick
★ 输出 schema 与 CONVERSATION_PROMPT 一致
★ formatter 接收 context dict，不与 LangGraph AgentState 耦合
"""

TIMER_PROMPT = """你是 SoulChord AI DJ，接到来定时事件（{timer_type}）。
请检查当前状态并输出节目调整。

【当前节目】
{program_info}

【播放状态】
{playback_info}

【工具执行结果】
{tool_results}

【可用 DJ 工具】
1. play_music — 播放指定歌曲。必须提供 query（歌曲名/歌手名）。song_id 由工具搜索返回，不要自己编造。参数：{{"query": "搜索关键词"}}
2. manage_playlist — 管理播放列表
3. get_environment_context — 获取环境信息
4. query_user_preference — 查询用户偏好
5. query_calendar — 查询飞书日程

{type_specific}

【重要：song_id 不要出现在你的输出中！】
你输出的歌曲只有 name 和 artist，song_id 由 play_music 工具搜索返回。

请严格按以下 JSON 格式输出，不要添加多余文本：

{{
  "program_decision": {{
    "today_theme": "string 或 null",
    "current_segment": "string 或 null（intro/music/transition/talk）",
    "program_mood": "string 或 null（energetic/warm/reflective/neutral）",
    "program_goal": "string 或 null",
    "voice_style": "string 或 null",
    "speech_rate": "float 或 null",
    "speak_frequency": "string 或 null"
  }},
  "playlist_decision": {{
    "action": "string（keep/replace/append/insert_now）",
    "songs": [
      {{"name": "string", "artist": "string", "scene_match": "string"}}
    ],
    "reason": "string"
  }},
  "dialogue_decision": {{
    "should_speak": false,
    "text": "string",
    "style": "string"
  }},
  "tool_calls": []
}}
"""


# ── 内部辅助 ──


def _build_type_specific(context: dict) -> str:
    """根据 timer_type 构建任务说明。"""
    timer_type = context.get("timer_type", "")
    hints = {
        "feishu": "【任务】检查飞书日历，看用户是否有即将开始的日程。无需调整则保持现状。",
        "heartbeat": "【任务】心跳常规检查。无需调整。",
        "playlist_health": (
            "【任务】播放列表健康检查。如果队列快空了（<3 首），"
            "用 manage_playlist 或 play_music 补充歌曲。"
        ),
        "program_tick": (
            "【任务】节目段定时检查。考虑是否需要切换节目段"
            "（current_segment）或调整 program_mood。"
        ),
    }
    return hints.get(timer_type, "")


# ── 公开 API ──


def format_timer_prompt(context: dict) -> str:
    """构建 TIMER_PROMPT。

    Args:
        context: 上下文 dict（必需键：timer_type, program,
                 player_mirror, runtime_snapshot 等），
                 不与 LangGraph AgentState 耦合。

    Returns:
        完整 prompt 字符串
    """
    from agent.prompts.conversation_prompt import _build_program_info, _build_playback_info

    timer_type = context.get("timer_type", "heartbeat")

    return TIMER_PROMPT.format(
        timer_type=timer_type,
        tool_results=context.get("tool_results", "（无）"),
        program_info=_build_program_info(context),
        playback_info=_build_playback_info(context),
        type_specific=_build_type_specific(context),
    )
