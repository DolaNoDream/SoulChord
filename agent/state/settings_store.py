"""settings.json 读写封装。

settings.json 存放用户配置（APIKey 等），前端 GET/PUT /api/settings 操作。
"""

import json
import os
from typing import Optional

from agent.config import settings as config_settings

DEFAULT_SETTINGS: dict = {
    "llm_apikey": "",
}


def load() -> dict:
    """加载 settings.json；不存在或损坏时返回默认值。"""
    path = config_settings.SETTINGS_FILE
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)


def save(data: dict) -> bool:
    """全量写入 settings.json。"""
    path = config_settings.SETTINGS_FILE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def update(**kwargs) -> dict:
    """增量更新 settings.json，返回合并后的完整 settings。"""
    current = load()
    current.update(kwargs)
    save(current)
    return current
