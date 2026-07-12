from fastapi import APIRouter
from backend.db import (
    settings_store,
    netease_store,
    user_profile_store,
    playlist_store,
    player_store,
)

router = APIRouter()


@router.get("/api/init")
async def init():
    settings = settings_store.read()
    netease_status = netease_store.read()
    user_profile = user_profile_store.read()
    playlists = playlist_store.list()
    player_state = player_store.read()

    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "settings": settings,
            "netease_status": netease_status,
            "user_profile": user_profile,
            "playlists": playlists,
            "player_state": player_state,
        },
    }