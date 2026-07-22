"""Agent Runtime lifespan — FastAPI app + 9 步启动 + decide_init_mode。

★ v0.6 A 项：lifespan 9 步
  ① init adapter  ② compile graph  ③ warmup memory
  ④ load RuntimeDJState  ⑤ create EventQueue
  ⑥ start Dispatcher  ⑦ start Scheduler
  ⑧ Runtime ready  ⑨ decide_init_mode + 推 AGENT_INIT
★ v0.6 J 项 + ★ v0.1.2 启动重建 3 情况
★ H19：Runtime 负责生命周期 / Graph 负责单次推理
"""

import asyncio
import logging
import time

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from agent.config import settings
from agent.graph import build_graph
from agent.runtime.event_queue import EventQueue, EventType, Event
from agent.runtime.dispatcher import EventDispatcher
from agent.runtime.ws_sender import ws_sender_loop, ws_heartbeat_loop
from agent.runtime.ws_handler import handle_ws_connection
from agent.state.runtime_dj_state import build_runtime_dj_state_from_disk
from agent.state.state_manager import state_manager
from agent.state.program_state import load_program_state, program_date_matches_today
from agent.shared.enums import InitMode
from agent.services.event_service import event_service
from agent.services.llm_service import LLMService
from agent.runtime.scheduler import Scheduler
from agent.state.data_initializer import init_data_files
from agent.state.player_state import clear_playback_cache
from agent.routes.http_routes import register_http_routes

logger = logging.getLogger(__name__)

# ── 全局单例 ──
event_queue = EventQueue()
dispatcher: EventDispatcher | None = None
scheduler: Scheduler | None = None
_runtime_dj_state: dict = {}
_runtime_ready_event = asyncio.Event()
_graph = None
_llm_service = LLMService()
_ws_sender_task: asyncio.Task | None = None
_ws_heartbeat_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dispatcher, scheduler, _runtime_dj_state, _graph, _ws_sender_task, _ws_heartbeat_task

    # ─────────────────────────────────────────────────
    # 第 1 步：初始化 adapter（注入到 @tool 函数）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 1/9] Init adapter")
    # P1：adapter 注入到 langchain_tools

    # ─────────────────────────────────────────────────
    # 第 2 步：compile LangGraph（7 节点）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 2/9] Compile graph")
    _graph = build_graph()

    # ─────────────────────────────────────────────────
    # 第 2.5 步：init_data_files（确保 6 data JSON 首次启动时存在）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 2.5/9] Init data files")
    init_data_files()

    # 清除 player_mirror 中的旧播放状态（避免上一轮测试脏数据被缓存恢复）
    clear_playback_cache()

    # ─────────────────────────────────────────────────
    # ❖ 第 2.7 步：configure LLMService（DeepSeek）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 2.7/9] Configure LLMService (model=%s, key_len=%d)", settings.LLM_MODEL, len(settings.DEEPSEEK_API_KEY))
    _llm_service.configure(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.LLM_MODEL,
        timeout_s=settings.LLM_TIMEOUT_S,
    )

    # ─────────────────────────────────────────────────
    # ❖ 第 2.8 步：initialize DJHostService
    # ─────────────────────────────────────────────────
    from agent.services.dj_host_service import DJHostService
    _dj_host_service = DJHostService(
        llm_service=_llm_service,
        enabled=settings.dj_host.enabled,
        cache_ttl_s=settings.dj_host.cache_ttl_s,
        llm_timeout_s=settings.dj_host.llm_timeout_s,
        persona_name=settings.dj_host.persona_name,
        persona_style=settings.dj_host.persona_style,
    )
    logger.info("[lifespan 2.8/9] DJHostService initialized (enabled=%s)", settings.dj_host.enabled)

    # ─────────────────────────────────────────────────
    # 第 3 步：warmup Memory（4 category + music_profile）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 3/9] Warmup memory")
    state_manager.memory.warmup()

    # ─────────────────────────────────────────────────
    # 第 4 步：load RuntimeDJState（长寿 in-memory）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 4/9] Load RuntimeDJState")
    _runtime_dj_state = build_runtime_dj_state_from_disk()
    state_manager.runtime_dj_state = _runtime_dj_state

    # ─────────────────────────────────────────────────
    # 第 5 步：create EventQueue（已构造）+ 绑定 EventService
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 5/9] EventQueue ready + bind EventService")
    event_service.bind(event_queue)

    # ─────────────────────────────────────────────────
    # 第 6 步：start EventDispatcher（Runtime while True）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 6/9] Start EventDispatcher")
    dispatcher = EventDispatcher(event_queue, _runtime_dj_state, llm_service=_llm_service, dj_host_service=_dj_host_service)
    dispatcher.set_graph(_graph)
    asyncio.create_task(dispatcher.run())

    # ─────────────────────────────────────────────────
    # ❖ 第 6.5 步：start WS sender loop（在 Dispatcher 之后、Scheduler 之前）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 6.5/9] Start WS sender loop")
    _ws_sender_task = asyncio.create_task(ws_sender_loop())
    _ws_heartbeat_task = asyncio.create_task(ws_heartbeat_loop())

    # ─────────────────────────────────────────────────
    # 第 7 步：start Scheduler（4 Timer Loop）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 7/9] Start Scheduler")
    scheduler = Scheduler(event_queue, settings.scheduler_config, runtime_dj_state=_runtime_dj_state)
    scheduler.start()

    # ─────────────────────────────────────────────────
    # 第 8 步：Runtime ready 信号
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 8/9] Runtime ready signal")
    _runtime_ready_event.set()

    # ─────────────────────────────────────────────────
    # 第 9 步：decide_init_mode() + 推 AGENT_INIT（仅 first/new_day）
    # ─────────────────────────────────────────────────
    logger.info("[lifespan 9/9] decide_init_mode")
    await _push_agent_init_when_ready()

    yield  # ← 应用开始服务

    # ── 关闭 ──
    logger.info("Shutting down...")
    if scheduler:
        await scheduler.stop()
    if dispatcher:
        dispatcher.stop()
    if _ws_sender_task:
        _ws_sender_task.cancel()
    if _ws_heartbeat_task:
        _ws_heartbeat_task.cancel()
    state_manager.memory.flush()


def decide_init_mode() -> InitMode:
    """★ v0.6 J 项：启动重建 3 情况判断。"""
    ps = load_program_state()
    if ps is None:
        return InitMode.FIRST_INIT
    if not program_date_matches_today(ps):
        return InitMode.NEW_DAY_INIT
    return InitMode.RESUME


async def _push_agent_init_when_ready():
    """★ v0.6 A 项：等 Runtime ready 后立即推 AGENT_INIT（不去 sleep 2s）。

    3 种模式：
      - first_init / new_day_init → AGENT_INIT（完整 INIT 流程）
      - resume → REPLAN_REQUEST（只生成歌单，不重置节目状态）
    """
    await _runtime_ready_event.wait()
    init_mode = decide_init_mode()
    if init_mode in (InitMode.FIRST_INIT, InitMode.NEW_DAY_INIT):
        logger.info("Pushing AGENT_INIT event (mode=%s)", init_mode.value)
        await event_queue.put(Event.from_system(
            EventType.AGENT_INIT,
            {"reason": init_mode.value, "init_mode": init_mode.value, "ts": int(time.time() * 1000)}
        ))
    else:
        logger.info("Pushing REPLAN_REQUEST on resume (queue may be empty)")
        await event_queue.put(Event.from_system(
            EventType.REPLAN_REQUEST,
            {"reason": "resume_startup", "init_mode": "resume", "ts": int(time.time() * 1000)}
        ))


# ── FastAPI App ──
app = FastAPI(lifespan=lifespan, title="SoulChord Agent Runtime", version="0.6.1")

# CORS：允许 Vite dev server（5173）和 Electron 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ★ 注册 HTTP 路由（8 群组：health / init / settings / playlist / user / feedback / history / netease）
register_http_routes(app)


@app.websocket("/ws/client")
async def ws_endpoint(ws: WebSocket):
    """WebSocket 端点 — 前端实时通信。"""
    await handle_ws_connection(ws, event_queue, _runtime_dj_state)
