"""ProgramService — 封装 state_manager.program 操作。"""

import logging

from agent.state.state_manager import state_manager

logger = logging.getLogger(__name__)


class ProgramService:
    """ProgramState 读写服务。"""

    def load(self) -> dict | None:
        return state_manager.program.load_program_state()

    def save(self, state: dict) -> bool:
        return state_manager.program.save_program_state(state)

    def reset(self) -> dict:
        return state_manager.program.reset_program_state()

    def today_str(self) -> str:
        return state_manager.program.today_str()

    def date_matches_today(self, state: dict) -> bool:
        return state_manager.program.program_date_matches_today(state)
