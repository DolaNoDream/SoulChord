			## 三十三、2026-07-23 LLM API Key 真实流动修复（已完成）

	**"前端设置了 API key，后端却一直用 .env 里的写死 key" → 前端 key 真正生效**

	| # | 改动 | 详情 | 文件 |
	|---|------|------|------|
	| ① | **LLMService.reconfigure()** | 新增热更新方法，重置 `self._client = None` 迫使下次调用用新 key 重建 AsyncOpenAI | **改** agent/services/llm_service.py |
	| ② | **lifespan 启动优先读用户 key** | 第 2.7 步先加载 `settings.json`，若用户已保存 key 则用它配置 LLMService，不再只用 .env | **改** agent/runtime/lifespan.py |
	| ③ | **PUT /api/settings 热更新** | 收到新 `llm_apikey` 后调用 `_llm_service.reconfigure()`，用户改 key 立即生效无需重启 | **改** agent/routes/http_routes.py |
	| ④ | **register_http_routes 注入 llm_service** | 新增可选参数，lifespan 传入 `_llm_service` 单例，避免循环依赖 | **改** agent/routes/http_routes.py |

	**根因**：前端 key 经 `PUT /api/settings` 存到 `settings.json`，但 LLMService 启动后永不刷新。`_resolve_llm_key()` 只影响 HTTP 读取端点，不影响 LLM 运行时。两处断裂。

	**42 相关测试通过，0 回归**

---

			## 三十二、2026-07-23 桌面打包 — SoulChord NSIS 安装包（已完成）

	**从"5 终端手动启动" → "用户一键安装，双击运行"**

	| # | 改动 | 详情 | 文件 |
	|---|------|------|------|
	| ① | **PyInstaller 3 后端** | agent(25MB) + music_api(25MB) + qqmusic_api(22MB) — onedir 模式，排除 transformers 省 65MB/个 | **新建** build/agent.spec, music_api.spec, qqmusic_api.spec, run_*.py |
	| ② | **NeteaseCloudMusicApi 打包** | pkg 编译首选，兜底 portable Node.js(67MB) | **新建** build/netease-wrapper/ |
	| ③ | **BackendManager** | Electron spawn 4 子进程 + 顺序启动 + 健康检查 + taskkill 清理 | **新建** electron/backend-manager.ts |
	| ④ | **Loading 窗口** | frameless 透明窗口，IPC 实时显示 4 后端启动进度 | **新建** public/loading.html, 改 electron/main.ts + preload.ts |
	| ⑤ | **electron-builder 配置** | extraResources 包含 4 后端 → NSIS oneClick:false | **改** electron-builder.yml |
	| ⑥ | **build-all.ps1** | 7 步全自动流水线：检查环境 → pip install → PyInstaller × 3 → Netease → npm build → electron-builder → 验证 | **新建** build-all.ps1 |
	| ⑦ | **经验** | .pth 中文路径 GBK 解码 → $env:PYTHONUTF8=1；QQMusicApi version pin 冲突 → 改 >=；GitHub 下载失败 → npmmirror 镜像 | — |

	**产物**：`SoulChord-0.1.0-Setup.exe`（218MB）

---

	**从"只有网易云登录" → "双 Provider 登录 + Agent 状态感知 + SourceSelector 动态优先级"**

	| # | 改动 | 详情 | 文件 |
	|---|------|------|------|
	| ① | **QQMusicApi 登录端点** | `/login/status` 查询 + `/login/logout` 标记无效；QR 成功后自动 `credential_store.update()` | **改** modules/login.py + routes/login.py |
	| ② | **Agent QQ 代理路由** | `_call_qq_api()` 调 8082；新增 `/api/qq/status` / qrcode / qrcode/status 3 端点；`/api/init` 含 qq 状态 | **改** http_routes.py |
	| ③ | **ProviderAccount 模型** | `provider / login_status / nickname / avatar_url` dataclass | **新增** accounts/models.py |
	| ④ | **ProviderAccountService** | asyncio background loop（300s），仅查 `support_account=True` 的 Provider；模块级 singleton 供 lifespan/dispatcher/executor 共享 | **新增** provider_account_service.py |
	| ⑤ | **support_account 属性** | `MusicProvider` 默认 False；NeteaseProvider + QQProvider 覆写为 True；`get_account_status()` 可选不加入 ABC | **改** base.py + netease_provider.py + qq_provider.py |
	| ⑥ | **SourceSelector 无状态** | `ProviderSelectionContext` dataclass；`rank(song, context)`；`_resolve_priority(accounts)` 每次返回新列表；QQ 登录后 qqmusic 优先 | **改** source_selector.py |
	| ⑦ | **ActionExecutor 注入 accounts** | `_exec_play_with_sources` 从 ProviderAccountService 取 accounts，传 context 给 rank() | **改** action_executor.py |
	| ⑧ | **Lifespan 集成** | 第 2.9 步初始化 ProviderAccountService + create_providers；shutdown 时 stop() | **改** lifespan.py |
	| ⑨ | **前端 QQ 扫码 UI** | SettingsDrawer QQ 账号区 + 扫码弹窗；settings.ts qqLoginStatus/qqNickname；agent.ts getQqStatus/getQqQrcode/getQqQrcodeStatus | **改** SettingsDrawer.vue + settings.ts + agent.ts |

	**改动规模**：4 新增 + 9 修改 = 13 文件 / 361 测试通过（零回归）

	---

			## 三十、2026-07-22 v9.14 P2 — SourceSelector 播放源选择（已完成）

	**从单源 play_url → 多源 try/except 重试**

	| # | 改动 | 详情 | 文件 |
	|---|------|------|------|
	| ① | **SongSource 数据类** | provider / platform_id / platform_mid / play_available；`from_dict()` 类方法 | **改** providers/base.py |
	| ② | **Provider.get_play_url ABC** | 参数统一为 SongSource | **改** providers/base.py |
	| ③ | **NeteaseProvider.get_play_url** | `:8081/songs/{platform_id}/playurl` | **改** netease_provider.py |
	| ④ | **QQProvider.get_play_url** | `:8082/song/{mid}/url` | **改** qq_provider.py |
	| ⑤ | **SourceSelector** | `rank(song)` 按 PROVIDER_PRIORITY + play_available 排序，纯同步无状态 | **新增** source_selector.py |
	| ⑥ | **ActionExecutor 多源重试** | `_exec_play` 有 sources 时 for+try/except 依次尝试各 Provider；全部失败报 PLAY_URL_NOT_FOUND（不 fallback 旧路径）；无 sources 走旧路径 | **改** action_executor.py |
	| ⑦ | **_build_song_payload 透传 sources** | 改名 `_to_frontend_song` → `_build_song_payload`；输出新增 sources 字段 | **改** action_planner.py |
	| ⑧ | **PROVIDER_PRIORITY 配置** | 默认 ["netease", "qqmusic"] | **改** config.py |
	| ⑨ | **20 个 P2 测试** | SongSource / SourceSelector rank / _build_song_payload / _exec_play with sources | **改** test_providers.py |

	**改动规模**：1 新增 + 5 修改 = 6 文件，20 新测试

	**验证**：361/364 通过（3 预存外部依赖失败），0 回归。

	---

	## 二十九、2026-07-22 P3 计划定稿 — QQ 扫码登录 + Provider 登录状态感知

	**从"只有网易云登录" → "双 Provider 登录 + Agent 状态感知"**

	| # | 阶段 | 详情 | 文件 |
	|---|------|------|------|
	| ① | **P3.1 QQ login API** | QQMusicApi(8082) 新增 `/login/status` + `/login/logout`；qrcode 成功后自动存 credential；Agent 新增代理路由 `/api/qq/*`；`/api/init` 含 qq 状态 | backend: login.py/modules + agent: http_routes.py |
	| ② | **P3.2 状态服务** | `ProviderAccount` 模型在 `accounts/models.py`；`ProviderAccountService` asyncio background loop 定时刷新；`SourceSelector.rank(song, context: ProviderSelectionContext)` 无状态动态优先级 | accounts/ + provider_account_service.py + source_selector.py + action_executor.py |
	| ③ | **P3.3 前端 UI** | SettingsDrawer QQ 扫码登录区域 + settingsStore qq 状态 + agent.ts API | SettingsDrawer.vue + settings.ts + agent.ts |

	**关键设计决策**：
	- ProviderAccountService 用 `asyncio.create_task` 自管理生命周期，不新增 Scheduler event
	- SourceSelector 无状态：`_resolve_priority()` 每次返回新列表，不改成员变量
	- `/api/init` 只供前端展示；Agent 运行时状态由 ProviderAccountService 独立维护
	- 实施顺序：P3.1 → P3.2 → P3.3（最后做前端）

	**详细方案**：`.claude/plans/delightful-finding-otter.md`

	---

			## 二十八、2026-07-22 v9.14 P1 — QQ Music 双数据源

**从单网易云源 → 网易云 + QQ 双数据源搜索融合**

| # | 改动 | 详情 | 文件 |
|---|------|------|------|
| ① | **MusicProvider 抽象层** | MusicProvider ABC：search() / health_check() / get_play_url()（预留）。ProviderSearchResult 统一中间模型 | **NEW** providers/base.py |
| ② | **NeteaseProvider** | 封装 music_service.py 现有 HTTP 调用，输出 ProviderSearchResult | **NEW** providers/netease_provider.py |
| ③ | **QQProvider** | HTTP 调 qqmusic-api-web:8082，仅 search + health_check 最小集 | **NEW** providers/qq_provider.py |
| ④ | **ProviderRegistry** | 注册 + 获取 + 健康检查（timeout=2s，失败不阻塞） | **NEW** providers/registry.py |
| ⑤ | **MusicSearchService** | 并行调两个 Provider，asyncio.gather(return_exceptions=True)，故障隔离 | **NEW** search_service.py |
| ⑥ | **SongResolver 增强** | 新增 resolve() 入口：normalize → merge（按 normalized title+artist 聚类）→ rank（离散评分）；不选 primary_source | **修改** song_resolver.py |
| ⑦ | **Song dict 新增字段** | provider / platform_id / platform_mid / sources[]，不碰 id | **修改** song_resolver.py, adapter.py |
| ⑧ | **adapter 开关保护** | MUSIC_PROVIDERS.enabled 关闭时走旧 MusicService | **修改** adapter.py |
| ⑨ | **配置项** | MUSIC_PROVIDERS + DEFAULT_PROVIDER + PROVIDER_HEALTH_TIMEOUT | **修改** config.py |

**改动规模**：6 新增 + 3 修改 = 9 文件

**设计原则**：
- Provider 对称：都走独立 HTTP 服务，不做 SDK subprocess
- 故障隔离：一个 Provider 挂，另一个照常
- 历史兼容：id 字段不变，仅新增字段
- P1 不做：UnifiedSong / primary_source / 登录 / 歌单导入

**详细方案**：见 memory/session-2026-07-22-qqmusic-dual-source.md

---

		## 二十七、2026-07-22 v9.11 — Fish Audio API 端点修复 + 音频闪避 + CORS

**从错误 Fish Audio API 端点 → 正确 v1 API + 前端音频体验修复**

| # | 改动 | 详情 | 文件 |
|---|------|------|------|
| ① | **TTS API 端点修复** | `https://fishaudio.org/api/open/v1/speech/tts` → `https://api.fish.audio/v1/tts`；参数 `voiceId` → `reference_id`；模型从 body `modelId` 改为 header `model: s2.1-pro-free`；语速 `speed` → `prosody.speed` | `tts_service.py` |
| ② | **ASR API 端点修复** | `https://fishaudio.org/api/open/v1/speech/transcriptions` (JSON) → `https://api.fish.audio/v1/asr` (multipart/form-data)；参数从 `audio_url` 改为 `audio_data` (bytes) | `asr_service.py` |
| ③ | **Base URL 默认值更新** | `https://fishaudio.org/api/open/v1` → `https://api.fish.audio` | `config.py` |
| ④ | **代理音频 CORS 修复** | StreamingResponse + FileResponse 加 `Access-Control-Allow-Origin: *` | `http_routes.py` |
| ⑤ | **TTS 日志增强** | action_executor 区分 audio=yes/NO；emit_response dj.speech 日志含 audio_url | `action_executor.py`, `emit_response.py` |
| ⑥ | **前端持久 TTS 元素** | 模块级 `_ttsAudio` 单例替代局部 `new Audio()`，避免 GC 回收导致播放中断 | `useWebSocket.ts` |
| ⑦ | **音频闪避** | TTS 说话时音乐音量降至 15%，结束后恢复原始音量；`_duckMusic()` / `_unduckMusic()` 含防重复闪避保护 | `useWebSocket.ts` |
| ⑧ | **DigitalOrb 音频静默 Bug** | `createMediaElementSource` 未连 `ctx.destination` → 若执行会切断所有音频输出 | `DigitalOrb.vue` |
| ⑨ | **WsMessageType 补充** | 加 `'tts'` 类型枚举 | `chat.ts` |
| ⑩ | **ASR 测试更新** | 适配新 bytes 接口 | `test_skeleton_services.py` |

**改动规模**：10 文件（7 后端 + 3 前端 + 1 测试）

**验证**：33/34 通过（1 预存 e2e 失败），0 新失败。

---

## 二十六、2026-07-21 v9.10 — Fish Audio 真实 TTS + ASR

**从 mock 语音 → 真实 Fish Audio API**

| # | 改动 | 详情 | 文件 |
|---|------|------|------|
| ① | **TTSService 重构** | 替换 `xunfei_mock` 为真实 Fish Audio 同步 HTTP API，音频缓存到 `data/tts/`，API Key 缺失时静默降级 | `tts_service.py` |
| ② | **ASRService 重构** | 替换 `xunfei_mock` 为真实 Fish Audio 转写 API | `asr_service.py` |
| ③ | **TTS 音频服务端点** | 新增 `GET /api/tts/audio/{filename}` 提供缓存音频文件 | `http_routes.py` |
| ④ | **WS 消息带真实 audio_url** | emit_response 传递 audio_url → WS 消息不再硬编码空字符串 | `emit_response.py`, `ws_sender.py` |
| ⑤ | **前端播放 TTS 音频** | useWebSocket.ts 新增 `case 'tts'` + DJ 话术播放 audio_url | `useWebSocket.ts` |
| ⑥ | **前端类型补充** | 新增 `TtsSynthesizePayload` 接口 | `chat.ts` |
| ⑦ | **配置 + Key** | config.py + .env 新增 Fish Audio 配置项 | `.env`, `config.py` |

**改动规模**：10 文件（6 后端 + 2 前端 + 1 测试 + 1 配置）

**验证**：317/321 通过（4 预存失败），0 新失败。

---

- 全量回归：317/321 通过（4 预存 music_agent_api 不可用 / e2e）

---

## 二十五、2026-07-21 v9.9 — AI 电台 UI 重设计

**从"音乐播放器" → "AI 电台控制室"**

| # | 改动 | 详情 | 文件 |
|---|------|------|------|
| ① | **Center Stage 布局** | 时钟→柱状图→2×2 网格播放区→广播稿聊天→输入区 | `DashboardView.vue` |
| ② | **主题色重构** | 深黑蓝 #05070D、电台绿 #19E6A2、AI 蓝紫 #6675FF、暖橙 #FFB86C | `variables.scss` |
| ③ | **点阵交互背景** | Canvas 绘制，鼠标产生球体隆起（位移+变亮），白天灰/黑夜白 | **NEW** `DotGrid.vue` |
| ④ | **像素柱状图可视化** | 20 根方块柱，Web Audio API 真实频率，激昂高/轻柔低 | **NEW** `DigitalOrb.vue` |
| ⑤ | **数字时钟** | Silkscreen 72px → Orbitron 96px + text-shadow glow | `ClockDisplay.vue` |
| ⑥ | **标题栏重做** | ● Claude + ● ON AIR（呼吸灯）+ ☾ 主题切换 + ⚙ 齿轮 | `App.vue` |
| ⑦ | **播放区 2×2 网格** | 左列歌名+PLAYING / 右列控制按钮跨行居中；emoji→薄线符号 | `MusicPlayer.vue` |
| ⑧ | **广播稿聊天** | 无头像气泡，role 标签+玻璃卡片+IBM Plex Mono | `ChatBubble.vue` |
| ⑨ | **日夜主题** | CSS 变量覆盖深色/浅色两套色值，localStorage 持久化 | `variables.scss`/多组件 |
| ⑩ | **封面图隐藏** | 删除 UI `<img>`，后端 `cover_url` 接口保留 | `MusicPlayer.vue` |

**改动规模**：11 文件 + 2 新建（DotGrid.vue、DigitalOrb.vue）

**验证**：构建通过，dev server 正常。

---

## 二十四、2026-07-21 v9.7 — 歌单管理 + 添加到歌单 + DJ 话术重复修复

### 歌单管理功能

**新增功能（4 项）**：
| # | 功能 | 实现 |
|---|------|------|
| ① | **新建歌单** | PlaylistPanel 顶部"✚ 新建"按钮 → 弹窗输入名称 → `POST /api/playlist/create` |
| ② | **保护网易云导入的歌单** | 后端 `DELETE` 检查 `netease_id`，有值返回 1002 拒绝删除；前端删除按钮自动禁用 + hover 提示 |
| ③ | **添加到歌单** | MusicPlayer ❤️ 按钮改为下拉菜单，显示所有用户创建的歌单，点击即添加；底部"✚ 新建歌单并添加" |
| ④ | **后端 add_song API** | `POST /api/playlist/{id}/songs` + `playlist_store.add_song()`（含 song_id 去重） |

**改动文件（7 文件）**：
| 文件 | 改动 |
|------|------|
| `agent/routes/http_routes.py` | +`POST /api/playlist/create` / `POST /api/playlist/{id}/songs`；DELETE 保护网易云 |
| `agent/state/playlist_store.py` | +`add_song(playlist_id, song)` |
| `frontend/src/types/music.ts` | Playlist 接口 +`netease_id`/`remark` |
| `frontend/src/api/agent.ts` | +`createPlaylist()` / `addSongToPlaylist()` |
| `frontend/src/stores/playlist.ts` | +`createPlaylist()` / `addSong()` / `isNeteaseImported()` / `userPlaylists` |
| `frontend/src/components/PlaylistPanel.vue` | 新建按钮 + 弹窗 + 网易云删除保护 |
| `frontend/src/components/MusicPlayer.vue` | ❤️ → 添加到歌单下拉菜单 |

### DJ 话术重复修复

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| ④ | 同一首歌 DJ 说两次（相近话术） | ws_handler play_start 推 DJ_MONOLOGUE 后，scheduler heartbeat 30s backstop 在 `last_dj_speech_song_id` 未更新前也推了一条 → 两条几乎同时入队 | RDS 加 `last_play_start_dj_ts`；scheduler backstop 检查该标记 < 30s 则跳过 |

**改动文件（2 文件）**：
| 文件 | 改动 |
|------|------|
| `agent/runtime/ws_handler.py` | 推 DJ_MONOLOGUE 后记录 `runtime_dj_state["last_play_start_dj_ts"]` |
| `agent/runtime/scheduler.py` | `_check_dj_monologue_backstop` 检查 `last_play_start_dj_ts` < 30s → 跳过 |

### DJ 话术架构（v9.7 最终版）

```
触发链路：
  play_start（主）
    → ws_handler: RDS current_song 同步 + 推 DJ_MONOLOGUE + 记录 last_play_start_dj_ts
    → Graph: ... → emit_response(dj.speech)
  
  heartbeat 30s 兜底（safety net）
    → _check_dj_monologue_backstop
    → 检查 last_play_start_dj_ts < 30s → 跳过（抑制与 play_start 的竞态）
    → 否则条件满足时推 DJ_MONOLOGUE

去重机制（4 层）：
  1. ws_handler: song_id 未变化 → 不推 DJ_MONOLOGUE（相同 song_id 防重）
  2. ws_handler: last_play_start_dj_ts → scheduler backstop 30s 内跳过（防 scheduler 竞态）
  3. dj_host: 60s dedup（节点级，防 Graph 内重复）
  4. dj_host: L1 cache 5min TTL（LLM 调用级消除冗余）
```

## 二十三、2026-07-21 v9.6 — 聚焦当前歌 + RESUME 自动播放 + play_start 去重

### 问题清单

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| ① | DJ 话术总在介绍下一首歌 | prompt 有 `【下一首预告】` 节显式告诉 LLM 下首歌名；模板 L3 也引入下一首 | 删除整个节 + 模板聚焦当前歌；format 不再接受 next_song |
| ② | 重启后不放歌、AIDJ 不说话 | RESUME 模式推 REPLAN_REQUEST，LLM 见队列有歌 + `已暂停` → `action=keep` + 空 songs → action_planner 无 play_song | `未播放` 修正误导 + RESUME 安全网自动播第一首 |
| ③ | 同一首歌 DJ 说两次 | `next()` + `playSong()` 都发 play_start → 两个 DJ_MONOLOGUE → 并发生成双话术 | ws_handler 去重：相同 song_id 只推一次 DJ_MONOLOGUE |

### 改动文件（5 文件）

| 文件 | 改动 |
|------|------|
| `agent/prompts/dj_speech_prompt.py` | 删除 `【下一首预告】` + `{next_song_section}`，format 不再接受/使用 next_song |
| `agent/services/dj_host_service.py` | 模板层 L3 `_generate_template` 聚焦当前歌曲，废弃 next_song 变体 |
| `agent/runtime/ws_handler.py` | play_start 推 DJ_MONOLOGUE 移到 RDS 更新守卫内（song_id 变化才推） |
| `agent/nodes/action_planner.py` | `_handle_llm_decision` 末尾加 RESUME 安全网检查：队列有歌 + 无 current_song → 自动播第一首 |
| `agent/prompts/conversation_prompt.py` | `播放状态：已暂停` → `未播放`（当前无歌时） |

### DJ 话术架构（v9.6 最终版）

```
prompt 结构：
  【用户】{user_info}
  【当前正在播放的歌曲】{current_song_info}
  → 无【下一首预告】节，LLM 不知下一首歌名

模板 L3（fallback）：
  聚焦当前歌曲名，4 mood 各自围绕当前歌展开
  （energetic/warm/reflective/neutral 各有模板）

触发去重：
  ws_handler: song_id 未变化 → 不推 DJ_MONOLOGUE
  dj_host: 60s dedup + L1 cache 5min TTL
```

---

## 二十二、2026-07-20 DJ Host Agent 修复 Round 2 — 同步 + 触发 + 前端显示

### 问题清单

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| ① | `dj_monologue` 事件无输出 | `action_planner_node` 的 catch-all 返回 `pending_payload: None`，覆盖了 `dj_host` 设置的 `dj_speech` | +`_handle_dj_monologue()` 透传 `dj_speech` + `tts_speak` action |
| ② | 前端不显示 DJ 话术 | `useWebSocket.ts` `handleMessage` 无 `case 'dj'`，`dj.speech` 静默丢弃 | +`case 'dj'` handler，显示 🎙️ 气泡；`chat.ts` +`'dj'` 类型 + `DjSpeechPayload` |
| ③ | DJ 说的歌不对（RDS 不同步） | 前端 `onSongEnded` 先 `next(true)` 本地推进再发 `play_end`；`next()` 本地切歌后不发 `play_start` | 交换 `onSongEnded` 顺序（先发 `play_end`）；`next()`/`_playFromQueue` 本地推进后发 `play_start`（含 song_name/artist） |
| ④ | 后端 RDS 不跟随前端切歌 | `ws_handler` 收到 `play_start` 只写 player_mirror，不更新 RDS `current_song` | `play_start` handler 同步更新 RDS + 推 `DJ_MONOLOGUE`（新触发方式） |
| ⑤ | QueuePanel 看不到后续歌曲 | `emit_response` 只发 `music.play`，不发 `music.update_playlist` | 发 `music.play` 后同步从 snapshot 取 `playlist_queue` 发 `update_playlist` |
| ⑥ | DJ 话术介绍的是下一首歌 | prompt 写"介绍即将播放的下一首歌" | 改为"以当前正在播放的歌曲为主，下一首作为延伸话题" |

### 改动文件（9 文件）

| 文件 | 改动 |
|------|------|
| `agent/nodes/action_planner.py` | +`_handle_dj_monologue()` 透传 dj_speech + tts_speak action |
| `agent/runtime/ws_handler.py` | `play_start` 同步 RDS `current_song` + 推 `DJ_MONOLOGUE` 事件 |
| `agent/runtime/ws_sender.py` | +`build_music_update_playlist()` + `_queue_song_to_frontend()` |
| `agent/nodes/emit_response.py` | `music.play` 后发 `music.update_playlist` 同步完整队列 |
| `agent/prompts/dj_speech_prompt.py` | prompt 指令改为"以当前歌曲为主，下一首为延伸" |
| `agent/runtime/lifespan.py` | WS 端点注入 `_runtime_dj_state` |
| `frontend/src/stores/player.ts` | `onSongEnded` 顺序交换；`next()`/`_playFromQueue` 加 `play_start` 通知 |
| `frontend/src/composables/useWebSocket.ts` | +`case 'dj'` 处理 DJ 话术显示 |
| `frontend/src/types/chat.ts` | +`'dj'` WS 类型 + `DjSpeechPayload` 接口 |

### DJ 触发新架构

```
旧：song_progress ≥85%（前端不发）→ 死代码
     scheduler heartbeat 30s 兜底 → 延迟高

新：play_start 主触发（前端每切歌必发）
  → ws_handler 同步 RDS current_song + 推 DJ_MONOLOGUE
  → scheduler heartbeat 30s 兜底（作为 safety net，被 play_start dedup 压制）

队列同步：
  每次 music.play → emit_response 发 music.update_playlist
  → 前端 QueuePanel 显示完整"接下来播放"列表
```

### 关键设计

| # | 决策 | 理由 |
|---|------|------|
| ① | `play_start` 触发 DJ_MONOLOGUE，不依赖 song_progress | 前端每切歌必发 play_start，实时性远高于 30s 心跳 |
| ② | `play_start` 先更新 RDS 再推 DJ_MONOLOGUE | 保证 dj_host 读到最新 current_song，context 不 stale |
| ③ | 移除"介绍下一首" prompt 指令 | 用户期望 DJ 介绍当前正在播的歌，不是下一首 |
| ④ | `music.update_playlist` 随 `music.play` 发送 | 无需额外事件驱动，前端队列始终与后端同步 |
