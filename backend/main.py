from fastapi import FastAPI
from backend.api.http import (
    init_router,
    setting_router,
    netease_router,
    playlist_router,
    user_router,
)

app = FastAPI(title="SoulChord Backend API", version="1.0")

app.include_router(init_router)
app.include_router(setting_router)
app.include_router(netease_router)
app.include_router(playlist_router)
app.include_router(user_router)


@app.get("/")
async def root():
    return {"code": 0, "msg": "SoulChord Backend API is running", "data": {}}