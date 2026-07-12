from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.db import settings_store

router = APIRouter()


class SettingsUpdateRequest(BaseModel):
    llm_apikey: Optional[str] = None
    netease_apikey: Optional[str] = None


@router.get("/api/settings")
async def get_settings():
    settings = settings_store.read()
    return {"code": 0, "msg": "ok", "data": settings}


@router.put("/api/settings")
async def update_settings(request: SettingsUpdateRequest):
    updates = {}
    if request.llm_apikey is not None:
        updates["llm_apikey"] = request.llm_apikey
    if request.netease_apikey is not None:
        updates["netease_apikey"] = request.netease_apikey
    if updates:
        settings_store.update(updates)
    settings = settings_store.read()
    return {"code": 0, "msg": "ok", "data": settings}