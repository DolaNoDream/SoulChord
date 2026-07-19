"""Runtime 长期运行组件 — EventQueue + Scheduler + Dispatcher + Lifespan + WS。

导出 app（FastAPI 实例）、decide_init_mode 等供外部导入。
"""

from agent.runtime.lifespan import app, decide_init_mode, event_queue, _push_agent_init_when_ready, _runtime_ready_event
from agent.runtime.ws_manager import connection_manager
from agent.runtime.ws_sender import ws_out_queue, ws_sender_loop, enqueue_or_drop
from agent.runtime.ws_handler import handle_ws_connection

__all__ = [
    "app", "decide_init_mode", "event_queue", "_push_agent_init_when_ready", "_runtime_ready_event",
    "connection_manager", "ws_out_queue", "ws_sender_loop", "enqueue_or_drop", "handle_ws_connection",
]
