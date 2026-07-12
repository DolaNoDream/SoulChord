import time
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.db import user_profile_store, playlist_store

router = APIRouter()


class UpdateUserBaseInfoRequest(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


@router.post("/api/user/analyze")
async def analyze_user():
    playlists = playlist_store.list()
    current_time = int(time.time() * 1000)

    genres = []
    artists = []
    for playlist in playlists:
        songs = playlist.get("songs", [])
        for song in songs:
            for artist in song.get("artists", []):
                artists.append(artist.get("name", ""))
            album = song.get("album", {})
            genres.append(album.get("name", ""))

    favorite_genres = list(set(genres))[:5]
    favorite_artists = list(set(artists))[:5]

    updates = {
        "favorite_genres": favorite_genres,
        "favorite_artists": favorite_artists,
        "music_preference_desc": "根据您的歌单分析生成的音乐偏好描述",
        "AI_conclustion": "您是一位热爱音乐的用户",
        "update_at": current_time
    }
    user_profile_store.update(updates)

    return {"code": 0, "msg": "ok", "data": {"update_at": current_time}}


@router.get("/api/user/profile")
async def get_user_profile():
    profile = user_profile_store.read()
    return {"code": 0, "msg": "ok", "data": profile}


@router.put("/api/user/baseinfo")
async def update_user_baseinfo(request: UpdateUserBaseInfoRequest):
    updates = {}
    if request.nickname is not None:
        updates["nickname"] = request.nickname
    if request.avatar_url is not None:
        updates["avatar_url"] = request.avatar_url
    if not updates:
        return {"code": 1001, "msg": "参数错误", "data": None}
    user_profile_store.update(updates)
    profile = user_profile_store.read()
    return {"code": 0, "msg": "ok", "data": profile}