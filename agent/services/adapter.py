"""ToolAdapter — 6 DJ_TOOLS dispatch + 14 INTERNAL_TOOLS。

★ v0.6.1 F 项：get_environment_context（原 query_user_context）
★ 8 Service 已注入（Memory / Program / Player / Environment / Music / Event / Feishu / ASR）
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

    async def dispatch(self, tool_name: str, args: dict) -> dict:
        """分派 tool 调用到对应 Service。

        6 DJ_TOOLS 路由：
          - play_music → self.music
          - get_environment_context → self.environment
          - query_user_preference / update_memory → self.memory
          - manage_playlist → 占位（P1 实现）
          - query_calendar → self.feishu（scope=current/today）
        """
        logger.info("Tool dispatch: %s args=%s", tool_name, args)

        # ── Music ──
        if tool_name == "play_music":
            query = args.get("query", "")
            song_id = args.get("song_id", "")
            if query:
                limit = args.get("limit", 5)
                songs = await self.music.search_songs(query, limit)
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
