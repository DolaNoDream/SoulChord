"""DJ_SPEECH_PROMPT — LLM DJ speech generation prompt。

生成自然、多样的 AI 电台 DJ 过渡语。
Output schema: {"text": str, "style": str, "should_speak": bool}
"""

DJ_SPEECH_PROMPT = """你是 {persona_name}，一个温暖的 AI 电台 DJ。你的风格是 {persona_style}。

当前是 {day_period}，节目主题是「{today_theme}」。

【用户】
{user_info}

【当前正在播放的歌曲】
{current_song_info}

请用自然、温暖、不重复的语言说一段话，重点是当前正在播放的歌曲。

要求：
- 长度控制在 20-100 字，鼓励多说一些，可以加入一些关于这首音乐的介绍（可以包括风格、歌手、感受等等）
- 语气自然，像真人 DJ
- 不要用套路化的模板，每一次都不一样
- 不要提前介绍下一首歌
- {queue_status_text}

请严格按 JSON 格式输出：
{{
  "text": "你的 DJ 串词",
  "style": "{persona_style}",
  "should_speak": true
}}
"""


def format_dj_speech_prompt(context: dict) -> str:
    """Build DJ speech prompt from context dict。

    期望的 context key：
        persona_name, persona_style, day_period, today_theme,
        user_nickname, user_mood,
        current_song (dict with name, artist),
        queue_empty (bool)
    """
    persona_name = context.get("persona_name", "Soul")
    persona_style = context.get("persona_style", "warm")
    day_period = context.get("day_period", "unknown")
    today_theme = context.get("today_theme", "今晚")

    # 用户信息
    nickname = context.get("user_nickname") or ""
    user_mood = context.get("user_mood") or ""
    user_parts = []
    if nickname:
        user_parts.append(f"用户昵称：{nickname}")
    if user_mood:
        user_parts.append(f"用户心情：{user_mood}")
    user_info = "、".join(user_parts) or "暂无用户信息"

    # 当前歌曲
    current = context.get("current_song") or {}
    current_song_info = (
        f"正在播放：{current.get('name', '未知歌曲')}"
        f" — {current.get('artist', '未知歌手')}"
    )

    # 队列状态（不透露下一首具体信息）
    queue_empty = context.get("queue_empty", True)
    if not queue_empty:
        queue_status_text = "后面还有好歌在等着。"
    else:
        queue_status_text = "队列快空了，告诉用户你正在准备更多好音乐。"

    return DJ_SPEECH_PROMPT.format(
        persona_name=persona_name,
        persona_style=persona_style,
        day_period=day_period,
        today_theme=today_theme,
        user_info=user_info,
        current_song_info=current_song_info,
        queue_status_text=queue_status_text,
    )
