import os
from .json_store import JSONStore, CollectionStore
from .models import (
    UserProfits,
    Playlist,
    Song,
    Artist,
    Album,
    Settings,
    NeteaseLoginStatus,
    PlayerState,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

settings_store = JSONStore(os.path.join(DATA_DIR, "settings.json"), {"llm_apikey": "", "netease_apikey": ""})

netease_store = JSONStore(os.path.join(DATA_DIR, "netease.json"), {"login_status": False, "nickname": ""})

user_profile_store = JSONStore(os.path.join(DATA_DIR, "user_profile.json"), {
    "nickname": "用户",
    "avatar_url": None,
    "favorite_genres": [],
    "disliked_genres": [],
    "favorite_artists": [],
    "music_preference_desc": "",
    "AI_conclustion": "",
    "update_at": 0
})

playlist_store = CollectionStore(os.path.join(DATA_DIR, "playlists.json"))

player_store = JSONStore(os.path.join(DATA_DIR, "player.json"), {
    "current_song": None,
    "play_url": None,
    "is_playing": False,
    "playlist": [],
    "current_index": 0
})

__all__ = [
    "JSONStore",
    "CollectionStore",
    "UserProfits",
    "Playlist",
    "Song",
    "Artist",
    "Album",
    "Settings",
    "NeteaseLoginStatus",
    "PlayerState",
    "settings_store",
    "netease_store",
    "user_profile_store",
    "playlist_store",
    "player_store",
]