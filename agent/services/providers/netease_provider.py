"""NeteaseProvider — 封装 music_agent_api:8081 HTTP 调用。"""

import logging

import httpx

from agent.services.providers.base import MusicProvider, ProviderSearchResult, SongSource
from agent.services.accounts.models import ProviderAccount

logger = logging.getLogger(__name__)


class NeteaseProvider(MusicProvider):
    """网易云音乐 Provider。

    通过 HTTP 调用队友的 music_agent_api（8081），与 MusicService 走同一后端。
    """

    def __init__(self, base_url: str, timeout: float = 15.0):
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    @property
    def name(self) -> str:
        return "netease"

    @property
    def support_account(self) -> bool:
        return True

    async def get_account_status(self) -> ProviderAccount:
        """查询网易云登录状态。"""
        try:
            resp = await self._client.get("/login/status")
            body = resp.json()
            if body.get("code") == 0:
                data = body.get("data", {})
                return ProviderAccount(
                    provider="netease",
                    login_status=data.get("logged_in", False),
                    nickname=data.get("nickname", ""),
                )
        except Exception as e:
            logger.debug("NeteaseProvider get_account_status failed: %s", e)
        return ProviderAccount(provider="netease", login_status=False)

    async def search(self, query: str, limit: int = 10) -> list[ProviderSearchResult]:
        try:
            resp = await self._client.get("/songs/search", params={"q": query, "limit": limit})
            body = resp.json()
            if body.get("code") != 0:
                logger.warning("NeteaseProvider search failed: %s", body.get("msg"))
                return []
            songs = body.get("data", {}).get("songs", [])
            return [self._to_result(s) for s in songs]
        except Exception as e:
            logger.error("NeteaseProvider search error: %s", e)
            return []

    async def get_playlist_tracks(self, playlist_id: str) -> list[ProviderSearchResult]:
        """获取网易云歌单歌曲列表。

        调 :8081/api/v1/playlist/detail 获取歌单详情及歌曲。
        """
        try:
            resp = await self._client.get("/api/v1/playlist/detail", params={"id": playlist_id})
            body = resp.json()
            if body.get("code") != 0:
                logger.warning("NeteaseProvider get_playlist_tracks failed: %s", body.get("msg"))
                return []
            songs = body.get("data", {}).get("songs", [])
            return [self._to_result(s) for s in songs]
        except Exception as e:
            logger.error("NeteaseProvider get_playlist_tracks error: %s", e)
            return []

    async def get_play_url(self, source: SongSource) -> str | None:
        """调 :8081/api/v1/songs/{platform_id}/playurl 获取播放 URL。"""
        try:
            resp = await self._client.get(f"/songs/{source.platform_id}/playurl")
            body = resp.json()
            url = body.get("data", {}).get("url") if isinstance(body.get("data"), dict) else None
            if url:
                return url
            logger.warning("NeteaseProvider: no play_url for %s", source.platform_id)
            return None
        except Exception as e:
            logger.error("NeteaseProvider get_play_url error: %s", e)
            return None

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()

    def _to_result(self, raw: dict) -> ProviderSearchResult:
        """将 music_agent_api 的 Song 格式转为 ProviderSearchResult。"""
        artists = raw.get("artists", []) or raw.get("ar", [])
        artist_list = [
            {"id": str(a.get("id", "")), "name": a.get("name", "")}
            for a in artists
        ]
        album_raw = raw.get("album", {}) or raw.get("al", {})
        album_obj = {
            "id": str(album_raw.get("id", "")),
            "name": album_raw.get("name", ""),
        }
        return ProviderSearchResult(
            provider="netease",
            platform_id=str(raw.get("id", "")),
            platform_mid=None,
            name=raw.get("name", "未知歌曲"),
            artists=artist_list,
            album=album_obj,
            cover_url=album_raw.get("cover_url", "") or raw.get("cover_url", ""),
            duration_ms=raw.get("duration_ms", 0),
            fee=raw.get("fee", 0),
        )
