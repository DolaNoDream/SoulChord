"""player_mirror.json 读写封装。

player_mirror.json 由 Electron → Agent 单向同步；Agent 只读，ws/handler.py 写入。
Mirror 不是 source of truth（v0.6 F 项）。
"""

import json
import os
from typing import Optional

from agent.config import settings

DEFAULT_PLAYER_MIRROR: dict = {
    "current_song": None,
    "current_position_ms": 0,
    "is_playing": False,
    "playlist_queue": [],
    "queue_strategy": {},
    "updated_at_ms": 0,
}


def load_player_mirror() -> Optional[dict]:
    """加载 player_mirror.json；不存在或损坏时返回默认值。"""
    path = settings.PLAYER_MIRROR_FILE
    if not os.path.exists(path):
        return dict(DEFAULT_PLAYER_MIRROR)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_PLAYER_MIRROR)


def update_player_event(event: dict) -> bool:
    """处理前端 player_event 并写入 player_mirror.json。

    只能由 ws/handler.py 调用；Node 不直接调用。
    """
    mirror = load_player_mirror() or dict(DEFAULT_PLAYER_MIRROR)
    subtype = event.get("subtype", "")

    if subtype == "song_started":
        mirror["current_song"] = event.get("song")
        mirror["current_position_ms"] = 0
        mirror["is_playing"] = True
    elif subtype == "song_progress":
        mirror["current_position_ms"] = event.get("position_ms", 0)
    elif subtype in ("song_finished", "user_skip"):
        mirror["current_song"] = None
        mirror["current_position_ms"] = 0
        mirror["is_playing"] = False
        if subtype == "user_skip":
            _remove_first_from_queue(mirror)
    elif subtype in ("user_like", "user_dislike", "play_end"):
        pass  # 不改变播放状态
    elif subtype == "playlist_changed":
        mirror["playlist_queue"] = event.get("playlist", [])
        mirror["queue_strategy"] = event.get("strategy", {})

    mirror["updated_at_ms"] = _now_ms()
    return _write_mirror(mirror)


def _remove_first_from_queue(mirror: dict):
    queue = mirror.get("playlist_queue", [])
    if queue:
        mirror["playlist_queue"] = queue[1:]


def _write_mirror(mirror: dict) -> bool:
    path = settings.PLAYER_MIRROR_FILE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mirror, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def clear_playback_cache() -> bool:
    """启动时清除 player_mirror 中的播放状态缓存。

    避免上一轮测试/会话遗留的脏数据（如 测试歌曲 / example.com URL）
    在 INIT 流程播放前被 _send_cached_music_play 读到并发送给前端。
    保留 playlist_queue（Resume 模式需要队列状态）。
    """
    mirror = load_player_mirror() or dict(DEFAULT_PLAYER_MIRROR)
    mirror["current_song"] = None
    mirror.pop("play_url", None)
    mirror["is_playing"] = False
    mirror["current_position_ms"] = 0
    mirror["updated_at_ms"] = _now_ms()
    return _write_mirror(mirror)


# 已知的测试/模拟歌曲名称，不写入播放记录
_TEST_SONG_NAMES = frozenset({"Song 1", "Song1", "Next", "测试歌曲", "测试", "Test Song", "test"})


def _is_test_song(entry: dict) -> bool:
    """判断播放记录是否为测试/模拟数据，应被过滤。"""
    name = entry.get("song_name")
    if not name:  # 无 song_name 的记录不自动过滤（可能是测试用的最小数据）
        return False
    name = name.strip()
    if name in _TEST_SONG_NAMES:
        return True
    # 英文"Song"/"Next"/"Test" 且无 artist 的记录也视为测试数据
    if not entry.get("artist") and name.lower() in ("song", "next", "test", "song1"):
        return True
    return False


def load_history(limit: int = 20, offset: int = 0) -> dict:
    """加载 player_history.json，支持分页。

    自动过滤测试/模拟歌曲记录。
    返回 {"items": [...], "total": ..., "limit": ..., "offset": ...}
    """
    path = settings.PLAYER_HISTORY_FILE
    items = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
        except (json.JSONDecodeError, OSError):
            items = []
    if not isinstance(items, list):
        items = []
    # 过滤测试记录
    items = [e for e in items if not _is_test_song(e)]
    total = len(items)
    sliced = items[offset:offset + limit]
    return {"items": sliced, "total": total, "limit": limit, "offset": offset}


def append_history_entry(entry: dict) -> bool:
    """向 player_history.json 追加一条播放记录（新记录插在最前）。

    entry 格式：
      {song_id, song_name, artist, cover_url, played_at, feedback, duration_played_ms}

    去重：60 秒内同一 song_id 的重复记录会自动跳过。
    """
    path = settings.PLAYER_HISTORY_FILE
    items = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
        except (json.JSONDecodeError, OSError):
            items = []
    if not isinstance(items, list):
        items = []

    # 过滤测试/模拟歌曲（不写入）
    if _is_test_song(entry):
        return True

    # 去重：60 秒内同一 song_id 的重复记录
    song_id = entry.get("song_id", "")
    played_at = entry.get("played_at", 0)
    for existing in items:
        if existing.get("song_id") == song_id:
            age = abs(played_at - existing.get("played_at", 0))
            if age < 60_000:  # 60 秒内
                return True  # 视为已存在，静默跳过

    items.insert(0, entry)
    # 最多保留 500 条
    items = items[:500]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)
