"""MusicService — 音乐服务（搜索/播放/推荐）。

经 httpx 调用 music_agent_api（port 8081），对接真实网易云数据。
"""

import logging

import httpx

from agent.config import settings

logger = logging.getLogger(__name__)

_API_BASE = settings.MUSIC_API_BASE_URL  # http://localhost:8081/api/v1


class MusicService:
    """音乐操作服务（真实 HTTP 调用）。"""

    def __init__(self):
        self._client = httpx.AsyncClient(base_url=_API_BASE, timeout=15.0)

    async def search_songs(self, query: str, limit: int = 10) -> list[dict]:
        """搜索歌曲 → 返回 Song 列表（与音乐 API 契约对齐）。"""
        try:
            resp = await self._client.get("/songs/search", params={"q": query, "limit": limit})
            body = resp.json()
            if body.get("code") != 0:
                logger.warning("MusicAPI search failed: %s", body.get("msg"))
                return self._mock_songs(query, limit)
            songs = body.get("data", {}).get("songs", [])
            return [_normalize_song(s) for s in songs]
        except Exception as e:
            logger.error("MusicAPI search error: %s", e)
            return self._mock_songs(query, limit)

    async def get_play_url(self, song_id: str) -> str | None:
        """获取播放 URL → 返回可播放的 MP3 地址，失败返回 None。"""
        try:
            resp = await self._client.get(f"/songs/{song_id}/playurl")
            body = resp.json()
            if body.get("code") != 0:
                logger.warning("MusicAPI playurl failed: %s", body.get("msg"))
                return None
            return body.get("data", {}).get("url")
        except Exception as e:
            logger.error("MusicAPI playurl error: %s", e)
            return None

    async def recommend_for_scene(self, scene: str, limit: int = 10) -> list[dict]:
        """按场景推荐歌曲。"""
        try:
            resp = await self._client.get("/recommend/scene", params={"scene": scene, "limit": limit})
            body = resp.json()
            if body.get("code") != 0:
                logger.warning("MusicAPI recommend scene failed: %s", body.get("msg"))
                return self._mock_songs(scene, limit)
            songs = body.get("data", {}).get("songs", [])
            return [_normalize_song(s) for s in songs]
        except Exception as e:
            logger.error("MusicAPI recommend scene error: %s", e)
            return self._mock_songs(scene, limit)

    async def report_playback(self, song_id: str, action: str, **kwargs) -> bool:
        """上报播放状态。"""
        try:
            payload = {"song_id": song_id, "event": action, "duration_ms": kwargs.get("duration_ms", 0), "ts": kwargs.get("ts", 0), "source": "ai_dj"}
            resp = await self._client.post("/playback/report", json=payload)
            body = resp.json()
            ok = body.get("code") == 0
            if not ok:
                logger.warning("MusicAPI report failed: %s", body.get("msg"))
            return ok
        except Exception as e:
            logger.error("MusicAPI report error: %s", e)
            return False

    async def close(self):
        await self._client.aclose()

    # ── 降级 mock（搜索降级，playurl 不降级——假 URL 会制造播放成功假象） ──

    @staticmethod
    def _mock_songs(label: str, limit: int) -> list[dict]:
        return [
            {
                "id": f"mock_{i}",
                "name": f"{label} #{i}",
                "artists": [{"id": "mock_artist", "name": "SoulChord"}],
                "album": {"id": "mock_album", "name": "Mock Album"},
                "cover_url": "",
                "duration_ms": 180000,
                "fee": 0,
            }
            for i in range(1, min(limit, 3) + 1)
        ]


def _normalize_song(raw: dict) -> dict:
    """将音乐 API 的 Song 格式统一为 WS 前端格式（Song type）。"""
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
    return {
        "id": str(raw.get("id", "")),
        "name": raw.get("name", "未知歌曲"),
        "artists": artist_list,
        "album": album_obj,
        "cover_url": album_raw.get("cover_url", "") or raw.get("cover_url", ""),
        "duration_ms": raw.get("duration_ms", 0),
        "fee": raw.get("fee", 0),
    }
