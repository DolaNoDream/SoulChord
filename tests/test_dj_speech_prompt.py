"""DJ speech prompt 格式化测试。

覆盖（4 测试）：
1. 完整 context → prompt 含所有节
2. queue_empty → 正确提示文本
3. 有 next_song → 正确下一首信息
4. 用户昵称 → 含用户信息

使用方法：
    cd dev
    python -m pytest tests/test_dj_speech_prompt.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestDJSpeechPrompt:
    """format_dj_speech_prompt 测试。"""

    def test_full_context_formats_correctly(self):
        """TC-01: 完整 context → prompt 含 persona/歌曲/时段。"""
        from agent.prompts.dj_speech_prompt import format_dj_speech_prompt

        context = {
            "persona_name": "Soul",
            "persona_style": "warm",
            "day_period": "evening",
            "today_theme": "轻松夜晚",
            "user_nickname": "小明",
            "user_mood": "放松",
            "current_song": {"name": "晴天", "artist": "周杰伦"},
            "next_song": {"name": "简单爱", "artist": "周杰伦"},
            "queue_empty": False,
        }
        prompt = format_dj_speech_prompt(context)

        assert "Soul" in prompt, f"应含 persona 名，实际: {prompt[:50]}"
        assert "晴天" in prompt, "应含当前歌曲"
        assert "简单爱" not in prompt, "不应含下一首歌名"
        assert "小明" in prompt, "应含用户昵称"
        assert "轻松夜晚" in prompt, "应含节目主题"
        assert "evening" in prompt, "应含时段"

    def test_queue_empty_variant(self):
        """TC-02: queue_empty=True → 队列快空提示。"""
        from agent.prompts.dj_speech_prompt import format_dj_speech_prompt

        context = {
            "persona_name": "Soul",
            "persona_style": "warm",
            "day_period": "night",
            "today_theme": "深夜",
            "user_nickname": "",
            "user_mood": "",
            "current_song": {"name": "安静", "artist": "周杰伦"},
            "next_song": None,
            "queue_empty": True,
        }
        prompt = format_dj_speech_prompt(context)

        assert "队列" in prompt, "空队列时应含提示"

    def test_with_next_song(self):
        """TC-03: 有 next_song → prompt 不应含下一首预告节。"""
        from agent.prompts.dj_speech_prompt import format_dj_speech_prompt

        context = {
            "persona_name": "Soul",
            "persona_style": "warm",
            "day_period": "afternoon",
            "today_theme": "午后",
            "user_nickname": "",
            "user_mood": "",
            "current_song": {"name": "A", "artist": "B"},
            "next_song": {"name": "C", "artist": "D"},
            "queue_empty": False,
        }
        prompt = format_dj_speech_prompt(context)

        assert "【下一首预告】" not in prompt, "不应含下一首预告节"
        assert "好歌" in prompt, "应含积极提示而非具体歌名"

    def test_no_user_info(self):
        """TC-04: 无用户信息 → 不报错，含默认文本。"""
        from agent.prompts.dj_speech_prompt import format_dj_speech_prompt

        context = {
            "persona_name": "Soul",
            "persona_style": "warm",
            "day_period": "morning",
            "today_theme": "早上",
            "user_nickname": "",
            "user_mood": "",
            "current_song": {"name": "A", "artist": "B"},
            "next_song": None,
            "queue_empty": True,
        }
        prompt = format_dj_speech_prompt(context)

        assert "暂无用户信息" in prompt, "无昵称时应显示默认"
        assert "Soul" in prompt
