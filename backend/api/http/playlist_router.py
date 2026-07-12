import uuid
import time
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.db import playlist_store, user_profile_store

router = APIRouter()


class ImportPlaylistRequest(BaseModel):
    playlist_url: str


class UpdatePlaylistRequest(BaseModel):
    name: Optional[str] = None
    remark: Optional[str] = None


@router.post("/api/playlist/import")
async def import_playlist(request: ImportPlaylistRequest):
    playlist_id = str(uuid.uuid4())
    new_playlist = {
        "playlist_id": playlist_id,
        "name": "未命名歌单",
        "source_url": request.playlist_url,
        "song_count": 0,
        "created_at": int(time.time() * 1000),
        "songs": []
    }
    playlist_store.add(new_playlist)
    return {"code": 0, "msg": "ok", "data": new_playlist}


@router.get("/api/playlist/list")
async def get_playlist_list():
    playlists = playlist_store.list()
    return {"code": 0, "msg": "ok", "data": playlists}


@router.get("/api/playlist/{playlist_id}")
async def get_playlist(playlist_id: str):
    playlist = playlist_store.get_by_id(playlist_id, id_field="playlist_id")
    if not playlist:
        return {"code": 1003, "msg": "歌单不存在", "data": None}
    return {"code": 0, "msg": "ok", "data": playlist}


@router.put("/api/playlist/{playlist_id}")
async def update_playlist(playlist_id: str, request: UpdatePlaylistRequest):
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.remark is not None:
        updates["remark"] = request.remark
    if not updates:
        return {"code": 1001, "msg": "参数错误", "data": None}
    updated = playlist_store.update(playlist_id, updates, id_field="playlist_id")
    if not updated:
        return {"code": 1003, "msg": "歌单不存在", "data": None}
    return {"code": 0, "msg": "ok", "data": updated}


@router.delete("/api/playlist/{playlist_id}")
async def delete_playlist(playlist_id: str):
    success = playlist_store.delete(playlist_id, id_field="playlist_id")
    if not success:
        return {"code": 1003, "msg": "歌单不存在", "data": None}
    return {"code": 0, "msg": "ok", "data": None}