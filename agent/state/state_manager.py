"""state_manager — state IO 统一封装。

Node 不直接 open json，统一经此模块读写。
★ v0.6 H 项 + ★ v0.6.1 D 项
"""

from agent.state import memory_store
from agent.state import program_state as ps
from agent.state import player_state as pms
from agent.state import runtime_dj_state as rds


class StateManager:
    """state IO 统一入口。

    3 个子模块：
      - memory: Memory JSON 读写（profile / preference / context / feedback）
      - program: program_state.json 读写（今日节目规划）
      - player: player_mirror.json 读写（播放状态镜像）
    """

    def __init__(self):
        self.memory = _MemoryProxy()
        self.program = _ProgramProxy()
        self.player = _PlayerProxy()

    @property
    def runtime_dj_state(self) -> dict:
        """当前长寿 RuntimeDJState 引用。

        注：state_manager 本身不持有 RuntimeDJState——它由 RuntimeContext.runtime_dj_state 持有。
        此属性仅用于状态同步，返回的是运行时全局 dict 的引用。
        由 Runtime 在 lifespan 中注入。
        """
        # 实际场景：Runtime 在启动时将全局 RuntimeDJState dict 绑定到这里
        return self._rds_ref

    @runtime_dj_state.setter
    def runtime_dj_state(self, value: dict):
        self._rds_ref = value


class _MemoryProxy:
    """Memory 操作代理。"""

    def warmup(self):
        """预热 Memory（加载 + 缓存）。"""
        memory_store.load_all()

    def load_all(self, min_confidence: float = 0.7) -> dict:
        return memory_store.load_all(min_confidence)

    def load_category(self, category: str) -> dict:
        return memory_store.load_category(category)

    def write(self, category: str, key: str, value, ttl_s=None) -> bool:
        return memory_store.write(category, key, value, ttl_s)

    def flush(self):
        memory_store.flush()


class _ProgramProxy:
    """ProgramState 操作代理。"""

    def load_program_state(self) -> dict | None:
        return ps.load_program_state()

    def save_program_state(self, state: dict) -> bool:
        return ps.save_program_state(state)

    def reset_program_state(self) -> dict:
        return ps.reset_program_state()

    def program_date_matches_today(self, state: dict) -> bool:
        return ps.program_date_matches_today(state)

    def today_str(self) -> str:
        return ps.today_str()


class _PlayerProxy:
    """PlayerMirror 操作代理。"""

    def load_player_mirror(self) -> dict | None:
        return pms.load_player_mirror()

    def update_player_event(self, event: dict) -> bool:
        return pms.update_player_event(event)


# 全局单例
state_manager = StateManager()
