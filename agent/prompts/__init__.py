"""DJ Planner prompt 模板。

★ v0.6 4 prompt 模式：INIT / CONVERSATION / TIMER / REPLAN
★ 输出 schema 统一：program_decision / playlist_decision / dialogue_decision / tool_calls
"""

from agent.prompts.init_prompt import format_init_prompt
from agent.prompts.conversation_prompt import format_conversation_prompt
from agent.prompts.timer_prompt import format_timer_prompt
from agent.prompts.dj_speech_prompt import format_dj_speech_prompt

__all__ = [
    "format_init_prompt",
    "format_conversation_prompt",
    "format_timer_prompt",
    "format_dj_speech_prompt",
]
