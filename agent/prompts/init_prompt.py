"""INIT_PROMPT — first_init / new_day_init 专用 prompt。

输出 init_plan（program_state + initial_playlist + first_song_id + welcome_text）。
★ v0.6 I 项：program_state schema 11 字段。
"""

INIT_PROMPT = """你是 SoulChord AI DJ。用户首次打开 App 或新的一天开始（{init_mode}），
请根据以下上下文生成今日节目 + 初始播放列表 + 欢迎语。

【Runtime Context】
- 今日日期：{date}
- 天气：{weather}
- 当前时间段：{day_period}
- 场景：{scene}

【用户音乐画像】
{music_profile}

【初始播放列表要求】
- 基于用户画像选择 10 首匹配场景的歌
- **多样性要求：不同歌手至少 6 位以上，同一艺术家的歌曲最多 2 首**
- 风格多样化（如已选一首安静的歌，下一首选不同节奏的）
- 第 1 首作为初始歌曲立即播放
- 每首歌包含 name、artist、scene_match（不要生成 song_id，song_id 由系统通过 play_music 工具搜索自动解析）

【输出格式】JSON（严格遵循此 schema）：
{{
  "program_state": {{
    "program_date": "{today}",
    "today_theme": "（主题名）",
    "current_segment": "intro",
    "program_mood": "（energetic / warm / reflective / neutral）",
    "program_goal": "（今日目标）",
    "voice_style": "（warm / cool / gentle / lively）",
    "speech_rate": 0.8,
    "speak_frequency": "（low / medium / high）"
  }},
  "initial_playlist": [
    {{"name": "...", "artist": "...", "scene_match": "..."}}
  ],
  "welcome_text": "（个性化欢迎语，含今日天气/场景/节目主题）"
}}
"""


def format_init_prompt(
    init_mode: str,
    date: str,
    today: str,
    weather: str = "未知",
    day_period: str = "未知",
    scene: str = "default",
    music_profile: str = "（新用户，暂无画像）",
) -> str:
    """使用实际值填充 INIT_PROMPT 模板占位符。"""
    return INIT_PROMPT.format(
        init_mode=init_mode,
        date=date,
        today=today,
        weather=weather,
        day_period=day_period,
        scene=scene,
        music_profile=music_profile,
    )
