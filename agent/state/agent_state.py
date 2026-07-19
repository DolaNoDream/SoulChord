"""AgentState — LangGraph State TypedDict（单次 invoke 内有效）。

★ v0.1.3：Tool Loop 普通字段 / runtime_snapshot 只读 / actions replace
设计来源：state_schema.md v0.1.3 §3
"""

from typing import Annotated, Any, Optional, TypedDict


def _append_messages(existing: list, new: list) -> list:
    """简单 append reducer（不依赖 LangChain BaseMessage）。"""
    return (existing or []) + (new or [])


class AgentState(TypedDict, total=False):
    """单次 graph.ainvoke 内的 LangGraph State。
    所有字段均为可选（total=False），允许 Node 返回部分更新。
    """

    # ──────── LangGraph 保留的非 schema 字段 ────────
    # 注意：AgentState 之外的自定义字段（如 test harness 的 __refs__）
    # 不会被 LangGraph 保留。如需传递额外信息，请在此显式声明。
    __refs__: dict                                            # event_service + llm_service 引用

    # ──────── LangGraph messages（append reducer） ────────
    messages: Annotated[list, _append_messages]              # 对话消息
    tool_messages: Annotated[list[dict], _append_messages]   # tool 返回结果

    # ──────── Runtime 注入（不通过 reducer） ────────
    trigger_type: str                                        # 7 TriggerType
    trigger_event: Optional[dict]                            # 原始 Event payload
    event_priority: str                                      # P0 / P1 / P3
    init_mode: str                                           # first_init / new_day_init / resume
    dependencies: dict                                       # event_queue + state_manager + runtime_dj_state

    # ──────── 5 域 Context（context_builder 写入） ────────
    user: dict
    environment: dict
    program: dict
    playlist: dict
    player_mirror: dict

    # ──────── RuntimeDJState 冷快照（Runtime invoke 前注入） ────────
    runtime_snapshot: Optional[dict]

    # ──────── 路由决策（Node 写入 → conditional edge 读取） ────────
    next_node: str                                           # router / dj_planner / tool_dispatcher 写

    # ──────── 反馈处理（feedback_extractor 写入） ────────
    feedback_record: Optional[dict]

    # ──────── LLM 中间产物（dj_planner 写入） ────────
    llm_decision: Optional[dict]
    init_plan: Optional[dict]

    # ──────── Tool 调用状态（dj_planner → tool_dispatcher） ────────
    pending_tool_calls: list[dict]
    tool_loop_count: int                                     # 普通字段（无 reducer）
    tool_loop_max: int

    # ──────── 动作规划（action_planner 整数组写入） ────────
    actions: list[dict]                                      # 默认 replace

    # ──────── 最终输出（emit_response 读取） ────────
    pending_payload: Optional[dict]                          # {chat_reply, music_play, status_update, transition_speech}
    should_speak: bool
    should_play_music: bool

    # ──────── 元数据 ────────
    last_error: Optional[dict]
    turn_count: int
    last_active_at_ms: int
