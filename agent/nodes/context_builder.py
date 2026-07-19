"""context_builder 节点 — 加载 5 域 context（不读 RuntimeDJState）。

★ v0.6.1 C 项：原 context_loader 改名（不是简单加载 — 是 warmup + format + put-into-state）
★ v0.1.2 P1-4：**不读** RuntimeDJState；snapshot 由 Runtime 在 invoke 前注入
★ v0.1.2 P0-1：return dict（partial update）
"""

import logging

from agent.state.state_manager import state_manager

logger = logging.getLogger(__name__)


async def context_builder_node(state: dict) -> dict:
    """并行加载 5 域 context。

    域：user / environment / program / playlist / player_mirror
    **不**写 runtime_snapshot（Runtime 注入）
    """
    import asyncio

    async def load_user():
        try:
            memory = state_manager.memory.load_all(min_confidence=0.7)
            return {
                "nickname": memory.get("profile", {}).get("nickname", {}).get("value"),
                "favorite_genres": memory.get("preference", {}).get("favorite_genres", {}).get("value"),
                "music_profile": memory.get("profile", {}).get("music_profile", {}).get("value"),
            }
        except Exception as e:
            logger.warning("load_user failed: %s", e)
            return {}

    async def load_environment():
        try:
            ctx = state_manager.memory.load_category("context")
            return {
                "user_mood": ctx.get("mood", {}).get("value"),
                "current_activity": ctx.get("current_activity", {}).get("value"),
                "day_period": _compute_day_period(),
            }
        except Exception as e:
            logger.warning("load_environment failed: %s", e)
            return {}

    async def load_program():
        try:
            ps = state_manager.program.load_program_state()
            return ps or {}
        except Exception as e:
            logger.warning("load_program failed: %s", e)
            return {}

    async def load_playlist():
        try:
            mirror = state_manager.player.load_player_mirror()
            return {"playlist_queue": mirror.get("playlist_queue", [])}
        except Exception as e:
            logger.warning("load_playlist failed: %s", e)
            return {"playlist_queue": []}

    async def load_player_mirror():
        try:
            return state_manager.player.load_player_mirror() or {}
        except Exception as e:
            logger.warning("load_player_mirror failed: %s", e)
            return {}

    user, env, prog, pl, mirror = await asyncio.gather(
        load_user(), load_environment(), load_program(),
        load_playlist(), load_player_mirror(),
    )

    return {
        "user": user,
        "environment": env,
        "program": prog,
        "playlist": pl,
        "player_mirror": mirror,
    }


def _compute_day_period() -> str:
    """计算当前时间段。"""
    import datetime
    hour = datetime.datetime.now().hour
    if 5 <= hour < 9:
        return "morning"
    elif 9 <= hour < 12:
        return "before_noon"
    elif 12 <= hour < 14:
        return "noon"
    elif 14 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"
