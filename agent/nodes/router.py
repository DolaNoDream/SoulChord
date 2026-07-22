"""Router 节点 — 规则路由，6 路分流 + player_event subtype 细化。

★ v0.6 D 项：song_finished → action_planner（不进 feedback_extractor）
★ v0.1.2 P1-6：trigger_type 7 枚举
★ v0.1.2 修正：作为 Graph Node，return dict（含 next_node），不调 state.update()
"""

import logging

logger = logging.getLogger(__name__)


async def router_node(state: dict) -> dict:
    """规则路由（Graph Node，输出 next_node 供 conditional edge 读）。

    Input: state.trigger_type, state.trigger_event
    Output: dict 含 next_node
    """
    trigger_type = state.get("trigger_type", "")
    trigger_event = state.get("trigger_event", {}) or {}
    subtype = trigger_event.get("subtype", "")

    if trigger_type == "system_init":
        next_node = "context_builder"
    elif trigger_type == "conversation":
        next_node = "context_builder"
    elif trigger_type == "replan_event":
        next_node = "context_builder"
    elif trigger_type == "timer_event":
        next_node = "context_builder"
    elif trigger_type == "dj_monologue":
        next_node = "context_builder"
    elif trigger_type == "user_control":
        next_node = "action_planner"
    elif trigger_type == "system":
        next_node = "emit_response"
    elif trigger_type == "player_event":
        if subtype in ("song_started", "song_progress", "pause", "resume", "play_start"):
            next_node = "emit_response"
        elif subtype == "song_finished":
            next_node = "action_planner"
        elif subtype in ("user_like", "user_dislike", "user_skip", "skip", "play_end"):
            next_node = "feedback_extractor"
        else:
            logger.warning("Unknown player_event subtype: %s", subtype)
            next_node = "emit_response"
    else:
        logger.warning("Unknown trigger_type: %s", trigger_type)
        next_node = "emit_response"

    return {"next_node": next_node}
