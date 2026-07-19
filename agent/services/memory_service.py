"""MemoryService — 封装 state_manager.memory 操作。"""

import logging

from agent.state.state_manager import state_manager

logger = logging.getLogger(__name__)


class MemoryService:
    """Memory 读写服务。"""

    def load_all(self, min_confidence: float = 0.7) -> dict:
        return state_manager.memory.load_all(min_confidence)

    def load_category(self, category: str) -> dict:
        return state_manager.memory.load_category(category)

    def write(self, category: str, key: str, value, ttl_s=None) -> bool:
        return state_manager.memory.write(category, key, value, ttl_s)

    def flush(self):
        state_manager.memory.flush()
