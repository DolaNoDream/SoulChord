"""QQProvider — 通过独立 HTTP 服务（8082）接入 qqmusic-api-python。"""

import logging

import httpx

from agent.services.providers.base import MusicProvider, ProviderSearchResult, SongSource
from agent.services.accounts.models import ProviderAccount

logger = logging.getLogger(__name__)

_QQ_COVER_URL_TPL = "https://y.gtimg.cn/music/photo_new/T002R300x300M000{mid}.jpg"


class QQProvider(MusicProvider):
    """QQ 音乐 Provider。

    通过 HTTP 调用 qqmusic-api-web（8082），对称于 NeteaseProvider。
    P1 最小集：仅 search + health_check。
    """

    def __init__(self, base_url: str, timeout: float = 15.0):
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    @property
    def name(self) -> str:
        return "qqmusic"

    @property
    def support_account(self) -> bool:
        return True

    async def get_account_status(self) -> ProviderAccount:
        """查询 QQ 音乐登录状态。"""
        try:
            resp = await self._client.get("/login/status")
            body = resp.json()
            if body.get("code") == 0:
                data = body.get("data", {})
                return ProviderAccount(
                    provider="qqmusic",
                    login_status=data.get("logged_in", False),
                    nickname=data.get("nickname", ""),
                    avatar_url=data.get("avatar_url"),
                )
        except Exception as e:
            logger.debug("QQProvider get_account_status failed: %s", e)
        return ProviderAccount(provider="qqmusic", login_status=False)

    async def search(self, query: str, limit: int = 10) -> list[ProviderSearchResult]:
        try:
            resp = await self._client.get(
                "/search/search_by_type",
                params={"keyword": query, "page": 1, "num": limit, "search_type": 0},
            )
            body = resp.json()
            if body.get("code") != 0:
                logger.warning("QQProvider search failed: %s", body.get("msg"))
                return []

            data = body.get("data") or {}
            songs = data.get("song") or []
            return [self._to_result(s) for s in songs]

        except Exception as e:
            logger.error("QQProvider search error: %s", e)
            return []

    async def get_playlist_tracks(self, playlist_id: str) -> list[ProviderSearchResult]:
        """获取 QQ 音乐歌单歌曲列表。

        调 :8082/songlist/{playlist_id}/detail 获取歌单详情及歌曲。
        """
        try:
            resp = await self._client.get(
                f"/songlist/{playlist_id}/detail",
                params={"num": 100, "page": 1, "onlysong": True},
            )
            body = resp.json()
            if body.get("code") != 0:
                logger.warning("QQProvider get_playlist_tracks failed: %s", body.get("msg"))
                return []
            songs = body.get("songs", [])
            return [self._playlist_to_result(s) for s in songs]
        except Exception as e:
            logger.error("QQProvider get_playlist_tracks error: %s", e)
            return []

    async def get_play_url(self, source: SongSource) -> str | None:
        """调 :8082/song/{mid}/url 获取播放 URL。

        QQMusicApi 返回 GetSongUrlsResponse 格式：
          {code, data: {expiration, data: [{purl, vkey, ...}]}}
        需要从 items 中提取 purl 并与 CDN base 拼接。
        """
        mid = source.platform_mid or source.platform_id
        try:
            resp = await self._client.get(f"/song/{mid}/url")
            # ★ 健康检查：HTTP 状态码
            if resp.status_code != 200:
                logger.warning("QQProvider: HTTP %d for mid=%s", resp.status_code, mid)
                return None
            body = resp.json()
            if body.get("code") == 0:
                items = body.get("data", {}).get("data") or []
                if items and len(items) > 0:
                    purl = items[0].get("purl", "")
                    if purl:
                        url = f"http://ws.stream.qqmusic.qq.com/{purl}"
                        # ★ 健康检查：URL 格式
                        if not url.startswith("http"):
                            logger.warning("QQProvider: invalid CDN URL for mid=%s", mid)
                            return None
                        logger.info("QQProvider: got play_url (mid=%s, purl_len=%d)", mid, len(purl))
                        return url
                    logger.warning("QQProvider: purl empty for mid=%s", mid)
                else:
                    logger.warning("QQProvider: no items in response for mid=%s", mid)
            else:
                logger.warning("QQProvider: API error code=%s for mid=%s", body.get("code"), mid)
            return None
        except Exception as e:
            logger.error("QQProvider get_play_url error: %s", e)
            return None

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/", timeout=5.0)
            body = resp.json()
            return body.get("code") == 0
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()

    def _playlist_to_result(self, raw: dict) -> ProviderSearchResult:
        """将歌单 API 的 Song 模型 dict 转为 ProviderSearchResult。

        与 _to_result 不同：songlist 返回的 Song 含有 mid、singer[].mid、album.mid，
        interval 为秒、pay 为嵌套 dict。
        """
        platform_id = str(raw.get("id", ""))
        platform_mid = raw.get("mid") or None

        singer_raw = raw.get("singer") or []
        artist_list = [
            {"id": str(s.get("id", "")), "name": s.get("name", "")}
            for s in singer_raw
        ]

        album_raw = raw.get("album") or {}
        album_mid = album_raw.get("mid") or ""
        album_obj = {
            "id": str(album_raw.get("id", "")),
            "name": album_raw.get("name", ""),
        }

        cover_url = _QQ_COVER_URL_TPL.format(mid=album_mid) if album_mid else ""
        interval_s = raw.get("interval", 0) or 0
        duration_ms = int(interval_s) * 1000

        pay_raw = raw.get("pay") or {}
        fee = pay_raw.get("pay_play", 0) if isinstance(pay_raw, dict) else 0

        return ProviderSearchResult(
            provider="qqmusic",
            platform_id=platform_id,
            platform_mid=platform_mid,
            name=raw.get("name", "未知歌曲"),
            artists=artist_list,
            album=album_obj,
            cover_url=cover_url,
            duration_ms=duration_ms,
            fee=fee,
        )

    def _to_result(self, raw: dict) -> ProviderSearchResult:
        """将 qqmusic-api-web 的 Song 格式转为 ProviderSearchResult。"""
        platform_id = str(raw.get("id", ""))
        platform_mid = raw.get("mid") or None

        # 歌手
        singer_raw = raw.get("singer") or []
        artist_list = [
            {"id": str(s.get("id", "")), "name": s.get("name", "")}
            for s in singer_raw
        ]

        # 专辑
        album_raw = raw.get("album") or {}
        album_mid = album_raw.get("mid") or ""
        album_obj = {
            "id": str(album_raw.get("id", "")),
            "name": album_raw.get("name", ""),
        }

        # 封面 URL（QQ 音乐封面格式）
        cover_url = _QQ_COVER_URL_TPL.format(mid=album_mid) if album_mid else ""

        # 时长（interval 是秒，转毫秒）
        interval_s = raw.get("interval", 0) or 0
        duration_ms = int(interval_s) * 1000

        return ProviderSearchResult(
            provider="qqmusic",
            platform_id=platform_id,
            platform_mid=platform_mid,
            name=raw.get("name", "未知歌曲"),
            artists=artist_list,
            album=album_obj,
            cover_url=cover_url,
            duration_ms=duration_ms,
            fee=raw.get("pay", {}).get("pay_play", 0) if isinstance(raw.get("pay"), dict) else 0,
        )
