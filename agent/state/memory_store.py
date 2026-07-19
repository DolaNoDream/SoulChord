"""memory.json 读写封装。

Memory 4 类 category：profile / preference / context / feedback。
设计原则 #8（v0.6 G 项）：context 短期（TTL）/ preference 长期（TTL=null）。
"""

import json
import os
import time
from typing import Optional

from agent.config import settings

# 默认 Memory 结构
DEFAULT_MEMORY: dict = {
    "profile": {},        # 用户画像（nickname, favorite_genres, music_profile 等）
    "preference": {},     # 长期偏好（TTL=null）
    "context": {},        # 短期语境（TTL=1 天）
    "feedback": {},       # 歌曲反馈（song_<id>）
}


def load_all(min_confidence: float = 0.7) -> dict:
    """加载完整 Memory；损坏时返回默认空结构。"""
    path = settings.MEMORY_FILE
    if not os.path.exists(path):
        return dict(DEFAULT_MEMORY)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _apply_ttl(data)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_MEMORY)


def load_category(category: str) -> dict:
    """加载单个 category。"""
    data = load_all()
    return data.get(category, {})


def write(category: str, key: str, value, ttl_s: Optional[int] = None) -> bool:
    """写入 Memory 的指定 category.key。

    Args:
        category: profile / preference / context / feedback
        key: 子键（如 song_<id>）
        value: 值
        ttl_s: TTL 秒数（None = 长期不过期）
    """
    path = settings.MEMORY_FILE
    data = load_all()
    if category not in data:
        data[category] = {}

    entry = {"value": value, "ts": int(time.time() * 1000)}
    if ttl_s is not None:
        entry["ttl_s"] = ttl_s
    data[category][key] = entry

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def delete(category: str, key: str) -> bool:
    """删除 Memory 的指定 category.key。"""
    path = settings.MEMORY_FILE
    data = load_all()
    if category not in data or key not in data[category]:
        return False
    del data[category][key]
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def flush():
    """占位：确保内存数据落盘（当前同步写入已保证）。"""
    pass


def _apply_ttl(data: dict) -> dict:
    """删除过期的 TTL 条目。"""
    now_ms = int(time.time() * 1000)
    for cat_name in ("context",):
        cat = data.get(cat_name, {})
        expired_keys = []
        for key, entry in cat.items():
            ttl_s = entry.get("ttl_s")
            if ttl_s is not None:
                ts = entry.get("ts", 0)
                if (now_ms - ts) > ttl_s * 1000:
                    expired_keys.append(key)
        for k in expired_keys:
            del cat[k]
    return data
