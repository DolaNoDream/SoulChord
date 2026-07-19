"""PlayerService — 封装 state_manager.player 操作。"""

import logging

from agent.state.state_manager import state_manager

logger = logging.getLogger(__name__)


class PlayerService:
    """PlayerMirror 读写服务。"""

    def load_mirror(self) -> dict | None:
        return state_manager.player.load_player_mirror()

    def update_event(self, event: dict) -> bool:
        return state_manager.player.update_player_event(event)
