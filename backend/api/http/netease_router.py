from fastapi import APIRouter
from pydantic import BaseModel
from backend.db import netease_store

router = APIRouter()


class NeteaseLoginRequest(BaseModel):
    credential: str


@router.post("/api/netease/login")
async def netease_login(request: NeteaseLoginRequest):
    netease_store.update({
        "login_status": True,
        "nickname": "网易云用户"
    })
    status = netease_store.read()
    return {"code": 0, "msg": "ok", "data": status}


@router.get("/api/netease/status")
async def get_netease_status():
    status = netease_store.read()
    return {"code": 0, "msg": "ok", "data": status}