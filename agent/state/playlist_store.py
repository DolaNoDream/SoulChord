"""playlists.json 读写封装。

playlists.json 存放本地导入的歌单列表及歌曲详情。
"""

import copy
import json
import os
import time
import uuid
from typing import Optional

from agent.config import settings as config_settings

DEFAULT_PLAYLISTS: dict = {
    "playlists": [],
    "songs": {},
}


def _default() -> dict:
    """返回深拷贝的默认结构——避免浅拷贝共享 list 引用导致跨请求数据泄漏。"""
    return {"playlists": [], "songs": {}}


def list_all() -> list:
    """返回全部歌单列表。"""
    data = _load_all()
    return data.get("playlists", [])


def get(playlist_id: str) -> Optional[dict]:
    """查询单个歌单。"""
    for pl in list_all():
        if pl.get("playlist_id") == playlist_id:
            return pl
    return None


def add(playlist: dict) -> dict:
    """新增歌单，自动生成 playlist_id 和 created_at。"""
    data = _load_all()
    pl = {
        "playlist_id": str(uuid.uuid4()),
        "name": playlist.get("name", "未命名歌单"),
        "source_url": playlist.get("source_url", ""),
        "song_count": len(playlist.get("songs", [])),
        "created_at": int(time.time() * 1000),
        "remark": playlist.get("remark", ""),
    }
    data["playlists"].append(pl)
    if playlist.get("songs"):
        data["songs"][pl["playlist_id"]] = playlist["songs"]
    _save_all(data)
    return pl


def update(playlist_id: str, updates: dict) -> Optional[dict]:
    """增量更新歌单信息（名称、备注）。"""
    data = _load_all()
    for pl in data["playlists"]:
        if pl.get("playlist_id") == playlist_id:
            if "name" in updates:
                pl["name"] = updates["name"]
            if "remark" in updates:
                pl["remark"] = updates["remark"]
            _save_all(data)
            return pl
    return None


def delete(playlist_id: str) -> bool:
    """删除指定歌单及关联歌曲缓存。"""
    data = _load_all()
    original_len = len(data["playlists"])
    data["playlists"] = [pl for pl in data["playlists"] if pl.get("playlist_id") != playlist_id]
    data["songs"].pop(playlist_id, None)
    if len(data["playlists"]) < original_len:
        _save_all(data)
        return True
    return False


def import_from_url(url: str) -> Optional[dict]:
    """通过网易云歌单分享链接导入。

    MVP：mock 实现，返回占位歌单。
    P2：调 music_agent_api 解析链接。
    """
    pl = {
        "name": f"导入歌单 ({time.strftime('%Y-%m-%d')})",
        "source_url": url,
        "songs": [],
        "remark": "来自网易云导入",
    }
    return add(pl)


def _load_all() -> dict:
    """加载完整 playlists.json。"""
    path = config_settings.PLAYLISTS_FILE
    if not os.path.exists(path):
        return _default()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default()


def _save_all(data: dict) -> bool:
    path = config_settings.PLAYLISTS_FILE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False
