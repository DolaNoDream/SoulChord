"""program_state.json 读写封装。

v0.6 schema 11 字段：
  version / updated_at / program_date / today_theme / current_segment /
  program_mood / program_goal / voice_style / speech_rate / speak_frequency / program_status
"""

import json
import os
from typing import Optional

from agent.config import settings

DEFAULT_PROGRAM_STATE: dict = {
    "version": "1.0",
    "updated_at": 0,
    "program_date": "",
    "today_theme": "",
    "current_segment": "intro",
    "program_mood": "neutral",
    "program_goal": "",
    "voice_style": "warm",
    "speech_rate": 0.8,
    "speak_frequency": "low",
    "program_status": "idle",
}


def load_program_state() -> Optional[dict]:
    """加载 program_state.json；不存在或损坏时返回 None。"""
    path = settings.PROGRAM_STATE_FILE
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_program_state(state: dict) -> bool:
    """写入 program_state.json；失败返回 False。"""
    path = settings.PROGRAM_STATE_FILE
    try:
        state["updated_at"] = _now_ms()
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def reset_program_state() -> dict:
    """重置为默认值。"""
    return dict(DEFAULT_PROGRAM_STATE)


def program_date_matches_today(state: dict) -> bool:
    """检查 program_date 是否等于今天。

    decide_init_mode() 依赖此判断。
    """
    import datetime
    today = datetime.date.today().isoformat()
    return state.get("program_date") == today


def today_str() -> str:
    """返回今日日期字符串 YYYY-MM-DD。"""
    import datetime
    return datetime.date.today().isoformat()


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)
