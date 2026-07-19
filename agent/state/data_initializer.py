"""首次启动时初始化 6 个数据 JSON 文件。

Store DEFAULT
      ↓
data_initializer.init_data_files()
      ↓
首次生成 JSON（不存在时才写入，不覆盖已有文件）

关系：Store 内 DEFAULT 是唯一来源，data/*.json 不是 source of truth。
策略：不提交 data/*.json 到 git，仅提交 data/.gitkeep。
"""

import json
import logging
import os
from typing import Any

from agent.config import settings
from agent.state.memory_store import DEFAULT_MEMORY
from agent.state.settings_store import DEFAULT_SETTINGS
from agent.state.playlist_store import DEFAULT_PLAYLISTS
from agent.state.program_state import DEFAULT_PROGRAM_STATE
from agent.state.player_state import DEFAULT_PLAYER_MIRROR

logger = logging.getLogger(__name__)

# ── 初始化清单： (settings 属性, 默认值) ──
# 按依赖顺序排列
_INIT_TASKS: list[tuple[str, Any]] = [
    ("MEMORY_FILE", DEFAULT_MEMORY),
    ("SETTINGS_FILE", DEFAULT_SETTINGS),
    ("PLAYLISTS_FILE", DEFAULT_PLAYLISTS),
    ("PROGRAM_STATE_FILE", DEFAULT_PROGRAM_STATE),
    ("PLAYER_MIRROR_FILE", DEFAULT_PLAYER_MIRROR),
    # player_history.json 是列表（非 dict），初始为空
    ("PLAYER_HISTORY_FILE", []),
]


def init_data_files():
    """确保 6 个 JSON 数据文件首次启动时存在。

    对每个文件：若磁盘上已存在 → 跳过；不存在 → 用 DEFAULT 值创建。
    在 lifespan Step 2（compile graph）之后、Step 3（warmup memory / init StateManager）之前调用。
    """
    for attr_name, default_value in _INIT_TASKS:
        path: str = getattr(settings, attr_name)
        if os.path.exists(path):
            continue
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default_value, f, ensure_ascii=False, indent=2)
            logger.info("Created initial data file: %s", path)
        except OSError as e:
            logger.warning("Failed to create %s: %s", path, e)
