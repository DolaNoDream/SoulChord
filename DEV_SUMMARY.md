# SoulChord · 项目开发总结

> **2026-07-19 更新 v8.4** | 59 Python 源文件，**260 测试通过** | 前端体验修复：刷新空白 (localStorage) + 进度条拖动 (dragPreview) + 搜索空结果 3 级兜底

---

## 一、项目定位

**SoulChord** = Windows 桌面"AI DJ Agent"。AI 通过**对话 + 音乐 + 飞书日程感知**主动提供**情绪陪伴**（不是音乐推荐工具）。

**三模块架构**：
```
Electron+Vue3 窗口（5 tab）  ←WS+HTTP→  Python Agent Runtime（8000）  ←HTTP→  music_agent_api（8081, Docker）
   前端同学                                 本仓库                                 队友
```

---

## 二、技术栈

| 维度 | 选型 | 备注 |
|---|---|---|
| Agent 框架 | **LangGraph StateGraph** | 8 节点，禁 while True: graph.invoke() |
| LLM | **DeepSeek**（API 兼容 OpenAI） | 经 LLMService.call_json(prompt) |
| TTS / ASR | **讯飞** | MVP mock，P2 接真实 |
| 音乐源 | **网易云** | 经队友 music_agent_api |
| 日程源 | **飞书** | MVP mock，P2 OAuth |
| 持久化 | **JSON 文件** | 不用 SQLite/向量库 |
| UI | **Electron + Vue3** | 普通窗口，砍桌宠/Live2D，5 tab |

---

## 三、架构总览

### 运行时序

```
lifespan 10 步
  Step 1:   Init adapter
  Step 2:   Compile graph（8 节点 StateGraph）
  Step 2.5: Init data files（6 JSON 首次启动自动生成）
  Step 2.7: Configure LLMService（DeepSeek）
  Step 3:   Warmup memory
  Step 4:   Load RuntimeDJState（长寿 in-memory）
  Step 5:   EventQueue ready + bind EventService
  Step 6:   Start EventDispatcher（while True 消费 EventQueue）
  Step 6.5: Start WS sender + heartbeat loops
  Step 7:   Start Scheduler（4 Timer Loop）
  Step 8:   Runtime ready signal
  Step 9:   decide_init_mode → 推 AGENT_INIT（first/new_day）/ REPLAN_REQUEST（resume）

EventDispatcher loop:
  while True:
      event = await queue.get()           # Runtime 负责生命周期
      state = build_initial_state(...)
      result = await graph.ainvoke(state)  # Graph 单次 invoke

Scheduler 4 Timer Loop:
  feishu(5min) / heartbeat(30s) / playlist_health(10min) / program_tick(30min)
```

### 8 节点 StateGraph

```
router（条件边 6 路分流）
  ├→ player_event → feedback_extractor / action_planner / emit
  ├→ system_init → context_builder → dj_planner(INIT) → action_planner → action_executor → tool_dispatcher → emit
  ├→ conversation → context_builder → dj_planner(CONV) → action_planner → action_executor → tool_dispatcher → emit
  ├→ timer_event → context_builder → dj_planner(TIMER) → action_planner → action_executor → emit
  ├→ replan_event → context_builder → dj_planner(REPLAN) → action_planner → action_executor → emit
  └→ user_control / system → action_planner → action_executor → emit

Tool Loop（最多 1 次）:
  dj_planner → tool_dispatcher（pending_tool_calls 非空）→ dj_planner（tool_messages 给 LLM）→ action_planner
```

### 10 Service + ToolAdapter

```
DJ Planner LLM 看到的 6 DJ_TOOLS：
  play_music / get_environment_context / query_user_preference /
  update_memory / manage_playlist / query_calendar
        ↓
  ToolAdapter.dispatch(tool_name, args) — compose 多 Service 方法
        ↓
  10 Service 层（每个方法 = 1 次外部调用）：
  MemoryService / ProgramService / PlayerService / EnvironmentService /
  MusicService / EventService / TTSService / LLMService / FeishuService / ASRService
```

### WS 实时通信（5 type）

```
chat / music / status / error / heartbeat
  → ws_manager（ConnectionManager）
  → ws_sender（ws_out_queue + sender loop + WSMessageBuilder）
  → ws_handler（端点 + 消息分发）
  → heartbeat: server 30s ping / 60s timeout
```

### HTTP 9 群组路由

```
init / settings / playlist / user / feedback / history / health / netease / feishu
  → 均经 Store 层（settings_store / playlist_store / memory_store / player_state / program_state）
  → route 不直接 open json
  → 统一响应格式 {"ok": bool, "data": ..., "error": ...}
```

---

## 四、关键设计决策（不可动摇）

| # | 决策 | 约束 |
|---|---|---|
| ① | Runtime 负责生命周期 / Graph 单次 invoke | 禁 `while True: graph.invoke()`（3 理由：消耗 token / Agent 幻想 / 无法抢占优先级） |
| ② | Memory vs DJState 隔离 | Memory（用户记忆，JSON 持久化）vs RuntimeDJState（AI 运行态，in-memory only） |
| ③ | Node 不直接 IO | 经 `agent/state/` 4 模块（memory_store / program_state / player_state / runtime_dj_state）+ state_manager |
| ④ | Mirror ≠ Source of Truth | Player Mirror 单向 Electron→Agent，播放状态以前端 player_event 为准 |
| ⑤ | plan_owner ≠ action_owner | DJ Planner 决定"为什么做"（不写 actions）；Action Planner 决定"如何执行" |
| ⑥ | 长寿 vs per-invoke | RuntimeDJState 长寿 in RuntimeContext；Node 经 `state["runtime_snapshot"]` 读快照 |
| ⑦ | 4 组同名陷阱 | ① today_theme ≠ current_scene ② preference ≠ feedback ③ context ≠ program_state ④ Memory context vs RuntimeDJState |
| ⑧ | Node return dict|str | 不调 `state.update()` |
| ⑨ | tool_loop_count 普通字段 | 无 reducer，Node 在 partial update 中 +1 |
| ⑩ | context_builder 不读 RDS | snapshot 由 Runtime invoke 前注入 AgentState.runtime_snapshot |

---

## 五、Agent 包结构

```
agent/
├── __main__.py              # python -m agent（uvicorn）
├── config.py                # Settings + SchedulerConfig（环境变量）
├── graph.py                 # ★ StateGraph 8 节点 + 3 conditional + 5 direct edges
├── shared/enums.py          # 8 枚举（TriggerType / EventPriority / EventType / InitMode / ...）
├── state/                   # IO 抽象层（Node 不直接 open json）
│   ├── agent_state.py       # AgentState TypedDict
│   ├── program_state.py     # program_state.json 读写（v0.6 11 字段）
│   ├── player_state.py      # player_mirror.json + load_history() 分页
│   ├── memory_store.py      # Memory 4 category + TTL + CRUD
│   ├── settings_store.py    # settings.json CRUD
│   ├── playlist_store.py    # playlists.json CRUD
│   ├── runtime_dj_state.py  # RuntimeDJState 重建 + snapshot deepcopy
│   ├── data_initializer.py  # 首次启动 6 JSON 自动生成
│   └── state_manager.py     # 统一封装代理
├── routes/
│   └── http_routes.py       # HTTP 8 群组（register_http_routes 统一注册）
├── runtime/
│   ├── event_queue.py       # asyncio.PriorityQueue（P0/P1/P3）
│   ├── dispatcher.py        # while True 消费 EventQueue → graph.ainvoke
│   ├── dispatcher_helpers.py
│   ├── scheduler.py         # 4 Timer Loop
│   ├── ws_manager.py        # ConnectionManager
│   ├── ws_sender.py         # ws_out_queue + sender loop
│   ├── ws_handler.py        # WS 端点 + 消息分发
│   └── lifespan.py          # FastAPI app + 10 步启动
├── prompts/
│   ├── __init__.py          # 导出 3 format 函数
│   ├── init_prompt.py       # INIT_PROMPT
│   ├── conversation_prompt.py  # CONVERSATION_PROMPT（REPLAN 复用）
│   └── timer_prompt.py      # TIMER_PROMPT（4 timer_type 分支）
├── nodes/                   # 8 Graph Node（均 return dict|str）
│   ├── router.py            # 条件边 6 路分流
│   ├── context_builder.py   # 5 域并行加载
│   ├── dj_planner.py        # 4 prompt 模式（INIT/CONV/TIMER/REPLAN）
│   ├── action_planner.py    # song_finished + transition speech + song_id 校验
│   ├── action_executor.py   # 消费 actions[] → Service（含 play_url=None 处理）
│   ├── emit_response.py     # WS 消息入 ws_out_queue
│   ├── feedback_extractor.py  # user_like/dislike/skip/play_end
│   └── tool_dispatcher.py   # 执行 pending_tool_calls
└── services/
    ├── adapter.py           # ToolAdapter 6 DJ_TOOLS dispatch（结构化错误返回）
    ├── memory_service.py
    ├── program_service.py
    ├── player_service.py
    ├── environment_service.py  # 4 mock（weather/time/location/activity）
    ├── music_service.py        # 真实 HTTP 调用 music_agent_api:8081，无 mock URL
    ├── tts_service.py          # TTS mock（xunfei_mock）
    ├── event_service.py        # EventQueue 封装 + push_replan
    ├── llm_service.py          # DeepSeek API（retry + 结构化 error）
    ├── feishu_service.py       # 飞书骨架（get_calendar_current/today mock）
    └── asr_service.py          # ASR 骨架（recognize mock）
```

---

## 六、测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|---|---|---|
| `test_init_planner.py` | 57 | Init Planner + 路由 + P0-2 + song_finished + transition speech + StateGraph |
| `test_scheduler.py` | 13 | Scheduler 生命周期 + 4 Timer EventType |
| `test_dj_planner_prompts.py` | 27 | 4 prompt schema + Tool Loop + LLM + **_is_fake_song_id 校验** |
| `test_action_executor.py` | 14 | TTSService + ActionExecutor + 异常降级 + **play_url=None 处理** |
| `test_llm_service.py` | 16 | LLMService 成功/重试/API 异常/配置/JSON 边界 |
| `test_ws_phase2.py` | 9 | emit WS 输出 + ConnectionManager heartbeat/broadcast |
| `test_http_routes.py` | 51 | HTTP 11 群组全覆盖（含 feishu + feedback POST + memory）+ 统一响应格式 + Store 隔离 + netease 代理测试 |
| `test_data_initializer.py` | 10 | 6 JSON 创建/内容/不覆盖/类型/序列化 |
| `test_skeleton_services.py` | 11 | Feishu/ASR schema + adapter dispatch + **play_music 空 query/真实 query 测试** |
| `tests/e2e/ (4 files)` | 44 | 启动/WS chat 全链路/player_event/Tool Loop |
| **合计** | **260** | **~5.7s 运行** |

---

## 七、数据文件

| 文件 | 路径 | 用途 |
|---|---|---|
| memory.json | data/memory.json | Memory 4 category（profile/preference/context/feedback）|
| program_state.json | data/program_state.json | 节目状态 v0.6 11 字段 |
| settings.json | data/settings.json | 用户设置（APIKey 等）|
| playlists.json | data/playlists.json | 歌单列表 |
| player_history.json | data/player_history.json | 播放历史 |
| player_mirror.json | data/player_mirror.json | Electron→Agent 播放状态同步 |

所有数据文件由 `init_data_files()` 在 lifespan Step 2.5 首次启动自动生成。

---

## 八、启动方式

```bash
cd dev
export DEEPSEEK_API_KEY="sk-xxx"    # 设置启用真实 LLM
python -m agent                      # 启动 Agent Runtime（8000）
```

WS 端点：`ws://localhost:8000/ws/client`
HTTP 端点：`http://localhost:8000/api/health`

**完整 3 终端启动：**
```bash
# 终端 1: Node.js 网易云底层
npx NeteaseCloudMusicApi

# 终端 2: 队友的 FastAPI 代理
cd api/music_agent_api && uvicorn main:app --port 8081

# 终端 3: Agent Runtime (8000)
cd dev && python -m agent
```

---

## 九、已验证的全链路

```
WS 聊天 → EventQueue → EventDispatcher → graph.ainvoke(8节点)
  → router → context_builder → dj_planner(真实DeepSeek, 2次调用)
  → tool_dispatcher(play_music 搜索 → music_agent_api:8081 → 网易云)
  → dj_planner(合成搜索结果) → action_planner(music_play)
  → action_executor(get_play_url) → emit_response → WS chat.reply + music.play
```

---

## 十、2026-07-18 网易云登录全链路实现（v5）

### 改动文件

| 文件 | 改动 |
|------|------|
| `api/music_agent_api/auth_manager.py` | 新增 `login_phone/qr_key/qr_create/qr_check/login_status/logout/is_logged_in` 6 方法 + `_save_token` |
| `api/music_agent_api/main.py` | 新增 6 个登录端点：`POST /login/phone`、`GET /login/qr-key`、`GET /login/qr-create`、`POST /login/qr-check`、`GET /login/status`、`POST /login/logout` |
| `api/music_agent_api/schemas.py` | 新增 `PhoneLoginRequest`、`QrCheckRequest` |
| `agent/routes/http_routes.py` | 删除全部 netease mock，改为代理到 music_agent_api；`/api/init` 同步改用真实状态 |
| `frontend/src/api/agent.ts` | 新增 `postNeteasePhoneLogin` / `getNeteaseQrKey` / `getNeteaseQrCreate` / `postNeteaseQrCheck` |
| `frontend/src/components/SettingsDrawer.vue` | 登录弹窗重构：tabs（手机号登录 + 扫码登录），QR 码显示 + 2s 轮询 |
| `frontend/src/stores/player.ts` | 修复 autoplay 策略：play() 失败时回退 isPlaying=false，让用户手势触发 |
| `frontend/src/stores/chat.ts` | 新增 `isSending` 状态 |
| `frontend/src/composables/useChat.ts` | 改用 store.isSending，修复输入框卡死 |
| `frontend/src/composables/useWebSocket.ts` | 收到 chat.reply 时重置 isSending=false |
| `tests/test_http_routes.py` | TestNetease 更新测试新代理行为 |

### 已知剩余问题

| # | 问题 | 原因 | 状态 |
|---|------|------|------|
| ① | `/api/proxy/audio` 网易云 CDN 返回 `text/html` | 某些歌曲 `outer/url` 端点返回 HTML 页面而非音频 | 需队友修复 |
| ② | WS 响应耗时 15-20s | 2 次 LLM × ~7s + 工具调度 | 可接受，非 bug |
| ③ | 飞书 HTTP 接口（status/connect/disconnect/today/refresh）| 未实现 | P1 |
| ④ | Memory HTTP 接口（query/update/delete）| 未实现 | P1 |
| ⑤ | 真实 TTS/ASR/Feishu | mock→真实 | P2 |

| # | 问题 | 原因 | 状态 |
|---|------|------|------|
| ① | play_url 只有 20 秒试听 | 网易云对非免费歌只返回试听片段；`auth_manager.py` 只用了匿名登录，无 VIP cookie | **需队友加登录接口** |
| ② | WS 响应耗时 15-20s | 2 次 LLM × ~7s + 工具调度 | 可接受，非 bug |
| ③ | 前端联调（剩余 WS `id` / HTTP 端点补齐） | 契约可选字段；Memory+飞书 HTTP 未实现 | P1 |
| ④ | 飞书 OAuth / HTTP 补齐 | status/connect/disconnect/today/refresh | P1 |
| ⑤ | Memory HTTP 补齐 | query/update/delete | P1 |
| ⑥ | 真实 TTS/ASR | mock→真实 | P2 |

---

## 十一、2026-07-19 飞书 OAuth + 日程 HTTP 全链路实现（v8）

### 改动文件

| 文件 | 改动 |
|------|------|
| `api/music_agent_api/main.py` | 合并飞书代码：新增飞书配置/`get_direct_session()`/`get_feishu_tenant_access_token()`/3 个飞书端点 + 自动加载 `.env` + 更新 `device/info` |
| `api/music_agent_api/docker-compose.yml` | 加 `FEISHU_APP_ID`/`FEISHU_APP_SECRET`/`NO_PROXY` |
| `agent/routes/http_routes.py` | 新增 Section 10 feishu：5 个端点（status/auth-url/calendar-today/calendar-current/refresh）+ 更新 `/api/init` calendar 字段 |
| `tests/test_http_routes.py` | 新增 `TestFeishu` 5 测试 + `TestResponseFormat` 加飞书端点 |
| `.env` | 加飞书配置节（`FEISHU_APP_ID`/`FEISHU_APP_SECRET`/`FEISHU_BASE_URL`/`FEISHU_REDIRECT_URI`） |

### Agent 飞书代理路由

| 端点 | 行为 |
|------|------|
| `GET /api/feishu/status` | 代理到 music_agent_api → 返回 `connected` 状态 |
| `GET /api/feishu/auth/url` | 代理到 music_agent_api → 返回飞书 OAuth 授权 URL |
| `GET /api/feishu/calendar/today` | 先尝试真实数据 → 失败回退 mock |
| `GET /api/feishu/calendar/current` | 先尝试真实数据 → 失败回退 mock |
| `POST /api/feishu/refresh` | no-op |

### 数据流

```
前端 → agent:8000/api/feishu/... → proxy → music_agent_api:8081/api/v1/feishu/... → 飞书 Open API
```

OAuth 流程：
1. 前端调 `GET /api/feishu/auth/url` 获取飞书扫码 URL
2. 用户浏览器打开 → 飞书二维码 → 手机飞书扫码
3. 浏览器回调到 `music_agent_api:8081/api/v1/feishu/auth/callback?code=xxx`
4. 换取 `user_access_token` 并缓存（内存）
5. 后续日程查询使用该 token 调飞书日历 API

### 已知剩余问题

| # | 问题 | 原因 | 状态 |
|---|------|------|------|
| ① | 前端自动播放策略：WS重连后第二首歌需用户点击 | 浏览器限制 `audio.play()` | 已加click恢复，待验证 |
| ② | 真实 TTS/ASR | mock→真实 | P2 |
| ③ | feedback_writer 拆分 / resume handler | 架构细化 | P2 |

---

## 十二、2026-07-19 v8.3 自动连播全链路实现

### 本轮目标

**播放队列自动连播**：启动后自动生成歌单 → 歌曲播完自动切下一首 → LLM 输出直接入队 → 歌曲失败自动跳过。

### 改动文件（11 文件）

| 文件 | 改动 |
|------|------|
| `agent/nodes/router.py` | `skip` 加入 player_event subtype 列表，修复 next() 发 WS `skip` 未被路由 |
| `agent/nodes/feedback_extractor.py` | 新增 `"skip"` 反馈写入分支 |
| `agent/nodes/action_planner.py` | **核心改动**：INIT playlist_queue 入队 / `_handle_song_finished` 消费队列 / LLM decision 的 `songs[1:]` 入队 / 支持 `action=add|replace` |
| `agent/nodes/action_executor.py` | 新增 `_pop_failed_from_queue()` — play_url 失败时自动移除失效歌曲 + REPLAN |
| `agent/nodes/dj_planner.py` | 新增 `_REAL_SONGS`（10 首真实网易云 ID）/ `_ensure_tool_calls()` 安全网 / mock 全部使用真实 ID |
| `agent/runtime/lifespan.py` | Resume 模式推 `REPLAN_REQUEST`（之前跳过不推，启动后无歌可播） |
| `agent/prompts/conversation_prompt.py` | REPLAN 额外说明改为"先用 play_music 搜索真实歌曲，不要编造 song_id" |
| `agent/state/player_state.py` | 新增 `_is_test_song()` 过滤测试记录（Song 1/Next/测试歌曲）不写入播放历史 |
| `SoulChord-deskpet-skin/SoulChord-front/src/stores/player.ts` | `prev()` 修复：设 audioElement.src + play()（之前只更新状态不调播放） |
| `tests/test_init_planner.py` | Resume 测试断言改为 `qsize() == initial_size + 1` |
| `tests/test_dj_planner_prompts.py` | 3 个 REPLAN 测试断言 `next_node` 改为 `"tool_dispatcher"` |

### 启动数据流

```
lifespan Step 9 decide_init_mode:
  first_init  → AGENT_INIT → dj_planner(INIT) → init_plan 含 initial_playlist → action_planner
    → 取 first_song 播放，其余 songs[1:] 写入 RuntimeDJState.playlist_queue + player_mirror.json
  new_day     → AGENT_INIT → 同上（日期不匹配时重建）
  resume      → REPLAN_REQUEST → dj_planner(REPLAN) → _ensure_tool_calls 注入 play_music → tool loop 搜索 →
    → 搜索结果入 playlist_decision → action_planner 取 songs[0] 播放，songs[1:] 入队

song_finished / user_skip / play_end:
  → action_planner._handle_song_finished
    → 读 playlist_queue[0] → 出队 → 播放下一首
    → 队列空 → 设 needs_replan=True → dispatcher 推 REPLAN_REQUEST

play_url 失败（text/html / 404）:
  → action_executor._pop_failed_from_queue
    → 检查队列第一首是否匹配 → 匹配则弹出 + 更新 player_mirror → needs_replan=True

LLM decision 含 songs[ ] 但无 tool_calls:
  → _ensure_tool_calls 安全网：注入 play_music 工具调用
  → LLM 下一轮收到搜索结果再输出真实 song_id
```

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| ① | RuntimeDJState.playlist_queue 作唯一真相源 | 长寿 in-memory，不受 graph invoke 生命周期限制 |
| ② | player_mirror.json 存 playlist_queue 副本 | Electron Mirror 同步用；Node 写入口统一经 `update_player_event(playlist_changed)` |
| ③ | Queue 消费 = 前端驱动 | action_planner 只决定"播什么"，前端收到 `music.play` 后播完发 `play_end` 触发下一首 |
| ④ | _ensure_tool_calls 是代码安全网，非 prompt 替代 | prompt 先从根源教 LLM 用工具，安全网兜底 LLM 不听话的情况 |
| ⑤ | 失败歌曲不阻塞队列 | `_pop_failed_from_queue` 移除失效项 + REPLAN，不会死循环重试同一首 |

### 已知剩余问题

| # | 问题 | 原因 | 状态 |
|---|------|------|------|
| ① | 前端自动播放策略：WS 重连后第二首歌需用户点击 | 浏览器限制 `audio.play()` | 已加 click 恢复，待验证 |
| ② | 真实 TTS/ASR | mock→真实 | P2 |
| ③ | feedback_writer 拆分 / resume handler | 架构细化 | P2 |
