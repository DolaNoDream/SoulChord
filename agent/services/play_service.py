"""PlayService — 统一播放服务。

所有播放入口（AI DJ / HTTP 点击 / 后续 Search）统一走此服务。

职责：
  1. 解析播放源（SourceSelector + Provider 多源重试)
  2. 构建代理 URL（解决前端 CORS）
  3. 更新播放历史 + player_mirror
  4. 更新 RDS current_song

用法（AI DJ Graph 内）：
    play_service = PlayService()
    result = await play_service.play(song)
    if result:
        pending_payload["music_play"] = {
            "song": result["song"],
            "play_url": result["play_url"],
        }

用法（HTTP 入口）：
    result = await play_service.play(song)
    if result:
        enqueue_or_drop(build_music_play(result["song"], result["play_url"]))
        return ok({"play_url": result["play_url"], "song": result["song"]})
"""

import json
import logging
import os
import urllib.parse

from agent.services.music_service import MusicService

logger = logging.getLogger(__name__)

# ★ P2: 播放源选择基础设施（惰性初始化）
_SOURCE_SELECTOR = None
_PROVIDER_REGISTRY = None


def _get_provider_infra():
    """惰性初始化 SourceSelector + ProviderRegistry。"""
    global _SOURCE_SELECTOR, _PROVIDER_REGISTRY
    if _SOURCE_SELECTOR is None:
        from agent.services.source_selector import SourceSelector
        from agent.services.providers.registry import create_providers
        from agent.config import settings as _settings
        _PROVIDER_REGISTRY = create_providers()
        _SOURCE_SELECTOR = SourceSelector(_PROVIDER_REGISTRY, _settings.PROVIDER_PRIORITY)
    return _SOURCE_SELECTOR, _PROVIDER_REGISTRY


class PlayService:
    """统一播放服务——所有播放入口走此服务。"""

    def __init__(self):
        self._music = MusicService()  # 旧路径（无 sources 的老数据）

    # ── 主入口 ──

    async def play(self, song: dict) -> dict | None:
        """解析播放 URL，更新相关状态。

        Args:
            song: 歌曲数据，含 id, name, artists, sources[] 等。

        Returns:
            {play_url, song, provider_name} | None（全部源失败时）
        """
        song_id = song.get("id", "")
        if not song_id:
            logger.warning("PlayService: play called with empty song_id")
            return None

        sources = song.get("sources", [])
        provider_name = "netease"

        if sources:
            play_url, provider_name = await self._resolve_with_sources(song_id, song)
        else:
            play_url = await self._resolve_legacy(song_id)

        if not play_url:
            logger.error("PlayService: no playable URL for song=%s", song_id)
            return None

        proxy_url = self._build_proxy_url(play_url, provider_name)

        # 写入播放历史
        self._record_history(song_id, song)

        # 写入 player_mirror
        self._save_playback_state_to_mirror(song_id, song, proxy_url)

        logger.info("PlayService: resolved provider=%s song=%s",
                     provider_name, song.get("name", "?"))

        return {
            "play_url": proxy_url,
            "song": song,
            "provider_name": provider_name,
        }

    # ── 源解析 ──

    async def _resolve_with_sources(self, song_id: str, song: dict) -> tuple[str | None, str | None]:
        """通过 SourceSelector + Provider.get_play_url 获取播放 URL。

        按 priority 依次尝试各源，一个失败换下一个。
        全部失败返回 (None, None)。

        Returns:
            (url, provider_name) 元组。全部失败返回 (None, None)。
        """
        selector, registry = _get_provider_infra()

        from agent.services.provider_account_service import get_account_service
        account_svc = get_account_service()
        accounts = account_svc.get_all() if account_svc else None
        from agent.services.source_selector import ProviderSelectionContext
        context = ProviderSelectionContext(accounts=accounts) if accounts else None

        ranked = selector.rank(song, context=context)
        if not ranked:
            logger.warning("PlayService: no playable sources for song=%s", song_id)
            return None, None

        for source in ranked:
            provider = registry.get(source.provider)
            if not provider:
                logger.debug("PlayService: provider %s not registered, skip", source.provider)
                continue

            try:
                url = await provider.get_play_url(source)
                if url:
                    logger.info("PlayService: got play_url from %s for song=%s",
                                source.provider, song_id)
                    return url, source.provider
            except Exception as e:
                logger.warning("Source %s play failed for song=%s: %s",
                               source.provider, song_id, e)
                continue

        logger.error("PlayService: all %d sources failed for song=%s", len(ranked), song_id)
        return None, None

    async def _resolve_legacy(self, song_id: str) -> str | None:
        """老数据无 sources → 旧 Netease-only 路径（向后兼容）。"""
        try:
            return await self._music.get_play_url(song_id)
        except Exception as e:
            logger.error("PlayService: legacy resolve failed for song=%s: %s", song_id, e)
            return None

    # ── 代理 URL ──

    @staticmethod
    def _build_proxy_url(play_url: str, provider_name: str) -> str:
        """将原始 CDN URL 转为代理 URL，解决前端 CORS / 跨域问题。"""
        from agent.config import settings as _settings
        encoded = urllib.parse.quote(play_url, safe="")
        return f"http://localhost:{_settings.AGENT_PORT}/api/proxy/audio?url={encoded}&provider={provider_name}"

    # ── 播放历史 ──

    @staticmethod
    def _record_history(song_id: str, song: dict):
        """将播放记录写入 player_history.json。"""
        artist_name = ""
        artists = song.get("artists") or []
        if isinstance(artists, list) and len(artists) > 0:
            a0 = artists[0]
            artist_name = a0.get("name", "") if isinstance(a0, dict) else str(a0)
        elif song.get("artist"):
            artist_name = song["artist"] if isinstance(song["artist"], str) else ""

        entry = {
            "song_id": song_id,
            "song_name": song.get("name", "未知歌曲"),
            "artist": artist_name,
            "cover_url": song.get("cover_url", ""),
            "played_at": int(__import__("time").time() * 1000),
            "feedback": "",
            "duration_played_ms": 0,
        }
        from agent.state.player_state import append_history_entry
        append_history_entry(entry)

    # ── player_mirror ──

    @staticmethod
    def _save_playback_state_to_mirror(song_id: str, song: dict, play_url: str):
        """将当前播放状态写入 player_mirror.json。"""
        song_name = (song.get("name") or "").strip()
        if song_name in ("测试歌曲", "测试", "Song 1", "Song1", "Next", "Test Song", "test"):
            logger.info("skip caching test song=%r to player_mirror", song_name)
            return

        from agent.state.player_state import load_player_mirror, DEFAULT_PLAYER_MIRROR
        from agent.config import settings as _settings
        mirror = load_player_mirror() or dict(DEFAULT_PLAYER_MIRROR)
        mirror["current_song"] = song
        mirror["play_url"] = play_url
        mirror["is_playing"] = True
        mirror["current_position_ms"] = 0
        mirror["updated_at_ms"] = int(__import__("time").time() * 1000)
        try:
            os.makedirs(os.path.dirname(_settings.PLAYER_MIRROR_FILE), exist_ok=True)
            with open(_settings.PLAYER_MIRROR_FILE, "w", encoding="utf-8") as f:
                json.dump(mirror, f, ensure_ascii=False, indent=2)
        except OSError:
            logger.warning("Failed to write playback state to player_mirror")


# ── 模块级单例 ──
play_service = PlayService()
