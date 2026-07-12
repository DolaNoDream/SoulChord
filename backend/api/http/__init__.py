from .init_router import router as init_router
from .setting_router import router as setting_router
from .netease_router import router as netease_router
from .playlist_router import router as playlist_router
from .user_router import router as user_router

__all__ = [
    "init_router",
    "setting_router",
    "netease_router",
    "playlist_router",
    "user_router",
]