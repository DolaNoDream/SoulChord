"""ToolAdapter — 6 DJ_TOOLS dispatch + 14 INTERNAL_TOOLS。

★ v0.6.1 F 项：get_environment_context（原 query_user_context）
★ 8 Service 已注入（Memory / Program / Player / Environment / Music / Event / Feishu / ASR）
★ v9.14：启用 MUSIC_PROVIDERS 时 play_music 走 MusicSearchService
"""

import logging

from agent.services.memory_service import MemoryService
from agent.services.program_service import ProgramService
from agent.services.player_service import PlayerService
from agent.services.environment_service import EnvironmentService
from agent.services.music_service import MusicService
from agent.services.event_service import EventService, event_service as _global_event_service
from agent.services.feishu_service import feishu_service as _global_feishu_service
from agent.services.asr_service import asr_service as _global_asr_service

logger = logging.getLogger(__name__)


class ToolAdapter:
    """ToolAdapter：dispatch() + 6 个 Service 属性。"""

    def __init__(self):
        self.memory = MemoryService()
        self.program = ProgramService()
        self.player = PlayerService()
        self.environment = EnvironmentService()
        self.music = MusicService()
        self.event = _global_event_service
        self.feishu = _global_feishu_service
        self.asr = _global_asr_service

        # v9.14: 多 Provider 搜索（惰性初始化）
        self._search_service = None

    def _get_search_service(self):
        """获取 MusicSearchService 实例（惰性初始化）。"""
        if self._search_service is not None:
            return self._search_service

        from agent.config import settings
        if not settings.music_providers.enabled:
            self._search_service = False  # sentinel
            return None

        try:
            from agent.services.providers.registry import create_providers
            from agent.services.search_service import MusicSearchService
            registry = create_providers()
            self._search_service = MusicSearchService(registry)
            logger.info("MusicSearchService initialized with providers: %s", registry.list_names())

            # 异步健康检查（不阻塞初始化）
            import asyncio
            asyncio.ensure_future(
                registry.health_check_all(timeout=settings.music_providers.health_timeout_s)
            )
            return self._search_service
        except Exception as e:
            logger.warning("Failed to initialize MusicSearchService: %s (falling back to single source)", e)
            self._search_service = False
            return None

    async def _search_play_music(self, query: str, limit: int = 5) -> list[dict]:
        """搜索音乐 — 有多 Provider 就走融合路径，否则走旧单源路径。"""
        svc = self._get_search_service()
        if svc is None:
            # 降级：走旧 MusicService 单源路径
            return await self.music.search_songs(query, limit)

        try:
            from agent.services.song_resolver import resolve
            provider_results = await svc.search(query, limit)
            songs = resolve(provider_results)
            logger.info("MusicSearchService: %d providers, %d merged results for %r",
                        len(provider_results), len(songs), query)
            return songs
        except Exception as e:
            logger.error("MusicSearchService search error, falling back: %s", e)
            return await self.music.search_songs(query, limit)

    async def _recommend_music(self, songs: list[dict], limit: int = 5) -> list[dict]:
        """推荐音乐解析：对每首 (name, artist) 执行搜索 + pick_best_song。

        ★ P6：将 LLM 推荐的歌曲列表解析为唯一版本。每首歌独立搜索，
        用 pick_best_song 选最佳版本。解析失败的歌静默跳过。

        Args:
            songs: LLM 推荐列表 [{name, artist, reason}, ...]
            limit: 每首歌的搜索候选数

        Returns:
            已解析歌曲列表（每首含真实 song_id/id, name, artists, sources, _recommend_reason）
        """
        from agent.services.song_resolver import pick_best_song

        resolved = []
        for song in songs:
            name = song.get("name", "")
            artist = song.get("artist", "")
            reason = song.get("reason", "")
            query = f"{name} {artist}".strip()
            if not query:
                logger.warning("recommend_music: empty name/artist pair, skip")
                continue

            search_results = await self._search_play_music(query, limit)
            best = None
            if search_results:
                best = pick_best_song(name, artist, search_results)

            if best:
                best["_recommend_reason"] = reason
                resolved.append(best)
            else:
                logger.warning("recommend_music: no resolution for %r %r, skip", name, artist)

        return resolved

    async def dispatch(self, tool_name: str, args: dict) -> dict:
        """分派 tool 调用到对应 Service。

        6 DJ_TOOLS 路由：
          - play_music → self.music（向下兼容）
          - recommend_music → 推荐解析（P6）
          - get_environment_context → self.environment
          - query_user_preference / update_memory → self.memory
          - manage_playlist → 占位（P1 实现）
          - query_calendar → self.feishu（scope=current/today）
        """
        logger.info("Tool dispatch: %s args=%s", tool_name, args)

        # ── Music ──
        if tool_name == "recommend_music":
            songs = args.get("songs", [])
            limit = args.get("limit", 5)
            resolved = await self._recommend_music(songs, limit)
            return {
                "songs": resolved,
                "count": len(resolved),
                "requested": len(songs),
                "success": True,
            }

        if tool_name == "play_music":
            query = args.get("query", "")
            song_id = args.get("song_id", "")
            if query:
                limit = args.get("limit", 5)
                songs = await self._search_play_music(query, limit)
                return {"songs": songs, "query": query, "count": len(songs), "success": True}
            if song_id:
                url = await self.music.get_play_url(song_id)
                if not url:
                    return {"status": "error", "code": "PLAY_URL_NOT_FOUND", "error": f"No playable URL for song_id={song_id}"}
                return {"song_id": song_id, "play_url": url, "success": True}
            logger.warning("ToolAdapter: play_music called without query or song_id")
            return {"status": "error", "code": "MISSING_QUERY", "error": "play_music requires query (song/artist name) or song_id"}

        # ── Environment ──
        elif tool_name == "get_environment_context":
            weather, time_info, loc, activity = await _gather_env(self.environment)
            return {
                "weather": weather,
                "time": time_info,
                "location": loc,
                "activity": activity,
            }

        # ── Memory（preference / memory） ──
        elif tool_name == "query_user_preference":
            category = args.get("category", "preference")
            data = self.memory.load_category(category)
            return {category: data, "source": "memory"}

        elif tool_name == "update_memory":
            category = args.get("category", "")
            key = args.get("key", "")
            value = args.get("value", "")
            ttl = args.get("ttl_s")
            ok = self.memory.write(category, key, value, ttl)
            return {"success": ok, "category": category, "key": key}

        # ── 占位工具（P1 / P2 实现） ──
        elif tool_name == "manage_playlist":
            logger.info("Tool manage_playlist: not implemented")
            return {"success": False, "error": "manage_playlist not yet implemented"}

        elif tool_name == "query_calendar":
            scope = args.get("scope", "today")
            if scope == "current":
                return await self.feishu.get_calendar_current()
            return await self.feishu.get_calendar_today()

        else:
            raise NotImplementedError(f"Unknown tool: {tool_name}")


async def _gather_env(env: EnvironmentService):
    """并行调用 EnvironmentService 的 4 个方法。"""
    import asyncio
    return await asyncio.gather(
        env.get_current_weather(),
        env.get_current_time(),
        env.get_current_location(),
        env.get_current_activity(),
    )


adapter = ToolAdapter()
