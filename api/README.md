# AI 音乐电台 Agent - API 文档总览

> 本目录是 Agent 服务的所有 API 接口契约文档集合。  
> 适用：Python Agent（LangGraph + DeepSeek）↔ 音乐 API 服务（聚合服务）

---

## 1. 文档目录

| 文档 | 内容 | Base URL（开发期） |
|---|---|---|
| [`frontend-agent-api.md`](./frontend-agent-api.md) | **前端 ↔ Agent** 的 WebSocket + HTTP 接口契约 | `ws://localhost:8000/ws/client` + `http://localhost:8000/api/...` |
| [`agent-music-api.md`](./agent-music-api.md) | **音乐模块**：网易云搜索/播放/推荐/红心 | `http://localhost:8001/api/v1/...` |
| [`agent-speech-api.md`](./agent-speech-api.md) | **语音模块**：讯飞 TTS / ASR / 音色管理 | `http://localhost:8001/api/v1/...` |
| [`agent-feishu-api.md`](./agent-feishu-api.md) | **飞书模块**：OAuth / 日程读取 / 端点映射 | `http://localhost:8001/feishu/...` |

---

## 2. 系统架构总览

```
┌────────────────────────────────────────────────────────────┐
│                  Electron 桌宠前端                          │
│        (Vue3 + 桌宠窗口 + 主窗口)                            │
└─────────────────────┬──────────────────────────────────────┘
                      │ HTTP / WebSocket
┌─────────────────────▼──────────────────────────────────────┐
│                  Agent 服务                                 │
│              (Python + LangGraph + DeepSeek)                │
│                                                            │
│   ┌──────────────────────────────────────────────────┐     │
│   │         Tool 层（agent/tools/）                  │     │
│   │  @tool 装饰的 Python 函数，对 LLM 屏蔽 HTTP 细节  │     │
│   └──────────────────────────────────────────────────┘     │
└─────────────────────┬──────────────────────────────────────┘
                      │ HTTP REST
┌─────────────────────▼──────────────────────────────────────┐
│            音乐 API 服务（聚合服务）                          │
│                                                            │
│   ┌────────────┐  ┌────────────┐  ┌──────────────┐         │
│   │ 音乐模块   │  │ 语音模块   │  │ 飞书模块     │         │
│   │ (music/)  │  │ (speech/)  │  │(integration/ │         │
│   │           │  │            │  │  feishu/)    │         │
│   │ 网易云     │  │ 讯飞 TTS   │  │ OAuth        │         │
│   │           │  │ 讯飞 ASR   │  │ 日程读取     │         │
│   └────────────┘  └────────────┘  └──────────────┘         │
└────────────────────────────────────────────────────────────┘
```

**关键设计原则**：
- 前端**不直接调**音乐 API 服务，全部通过 Agent 中转
- Agent 内部把 HTTP 接口封装成 **Tool 函数** 给 LLM 调用
- 三个模块虽然在同一个 FastAPI app（MVP），但**代码分目录**，未来可拆为独立服务

---

## 3. 三模块职责划分（重要！）

| 模块 | 负责 | 不负责 |
|---|---|---|
| **音乐** | 网易云搜索、播放 URL、私人漫游、场景音乐、红心收藏、数据回传 | 用户画像、决策逻辑、播放器控制 |
| **语音** | 讯飞 TTS 合成、ASR 识别、音色管理 | 文案生成（由 LLM 负责）|
| **飞书** | OAuth 授权、日程读取、`current_block` 计算 | 日程策略决策（"会议中应该怎么做"）|

> ❌ 三模块**都不负责**：用户画像、情绪记忆（→ Agent Memory）、工具编排决策（→ LangGraph）、UI 渲染（→ 前端）

---

## 4. 共享约定（适用于所有模块）

### 4.1 基础环境
- 所有服务**本地运行**，无鉴权（开发期）
- 生产期预留 `X-API-Key` Header

### 4.2 响应统一格式
```json
{
  "code": 0,
  "msg": "ok",
  "data": { ... }
}
```

### 4.3 时间格式
所有时间戳统一用 **毫秒级 Unix 时间戳**（number）。

### 4.4 错误码体系（跨模块）

| 范围 | 归属 |
|---|---|
| `4001-4099` | 通用（参数、资源不存在） |
| `4101-4199` | 音乐模块（网易云） |
| `4201-4299` | 语音模块（讯飞） |
| `4301-4399` | 飞书模块 |
| `5001-5099` | 内部异常 |

> 各模块具体错误码见各自文档

---

## 5. Tool 层完整列表

> 这是 Agent 调用三模块的**全部 Tool**，写代码时直接对照。  
> 每个 Tool 是 Python 函数（`@tool` 装饰），内部用 HTTP 调用对应模块的接口。

### 5.1 音乐模块 Tools
| Tool 名 | HTTP 接口 | 说明 |
|---|---|---|
| `search_songs(q, limit)` | `GET /api/v1/songs/search` | 搜索歌曲 |
| `get_song_detail(id)` | `GET /api/v1/songs/{id}` | 歌曲详情 |
| `get_play_url(id, br)` | `GET /api/v1/songs/{id}/playurl` | 获取播放 URL（含降级） |
| `get_aidj_speech(id, timbre)` | `GET /api/v1/songs/{id}/aidj_speech` | AIDJ 口播 |
| `get_lyric(id)` | `GET /api/v1/songs/{id}/lyric` | 歌词 |
| `recommend_fm(count)` | `GET /api/v1/recommend/fm` | 私人漫游 |
| `recommend_scene(scene, limit)` | `GET /api/v1/recommend/scene` | 场景音乐 |
| `recommend_daily()` | `GET /api/v1/recommend/daily` | 每日推荐 |
| `get_favorite_songs()` | `GET /api/v1/user/favorite_songs` | 红心歌单 |
| `like_song(id)` | `POST /api/v1/user/favorite_songs/{id}` | 收藏 |
| `unlike_song(id)` | `DELETE /api/v1/user/favorite_songs/{id}` | 取消收藏 |
| `report_playback(...)` | `POST /api/v1/playback/report` | 网易云数据回传 |

### 5.2 语音模块 Tools
| Tool 名 | HTTP 接口 | 说明 |
|---|---|---|
| `tts_synthesize(text, voice, speed, volume)` | `POST /api/v1/tts/synthesize` | TTS 合成 |
| `get_voices()` | `GET /api/v1/tts/voices` | 音色列表 |
| `asr_recognize(audio_bytes, format)` | `POST /api/v1/asr/recognize` | ASR 识别 |

### 5.3 飞书模块 Tools
| Tool 名 | HTTP 接口 | 说明 |
|---|---|---|
| `get_calendar_today(date, timezone)` | `GET /feishu/calendar/today` | 今日所有日程 |
| `get_calendar_current()` | `GET /feishu/calendar/current` | 当前进行中 + 下一个日程 |
| `refresh_calendar()` | `POST /feishu/calendar/refresh` | 主动刷新缓存 |
| `get_feishu_status()` | `GET /feishu/status` | 连接状态 |

---

## 6. 调用关系示意

```
用户对桌宠说话
    │
    ▼
前端 (Electron) ── WS chat.voice_text ──> Agent
    │                                          │
    │                                          ├─ LLM 推理（DeepSeek）
    │                                          │
    │                                          ├─ get_calendar_current() ── HTTP ──> 飞书模块
    │                                          │                              └─ 拿 current_block
    │                                          │
    │                                          ├─ recommend_scene(scene) ── HTTP ──> 音乐模块
    │                                          │                              └─ 拿候选歌曲
    │                                          │
    │                                          └─ tts_synthesize(text) ── HTTP ──> 语音模块
    │                                                                          └─ 拿音频 URL
    │
    ◄── WS music.play + tts.synthesize + chat.reply ────
    │
    ▼
前端播放音乐 + 播放 TTS + 渲染 DJ 字幕
```

---

## 7. 未来演进（不在 MVP 范围）

| 项 | 当前 | 未来 |
|---|---|---|
| 三模块部署 | 同一 FastAPI app | 拆为 Music / Speech / Integration 三个独立服务 |
| 飞书日程推送 | 5 分钟轮询 | 事件订阅（需云端中转）|
| 网易云账号 | 匿名 token | 扫码登录 |
| 鉴权 | 无 | `X-API-Key` |

---

## 8. 文档版本

| 文档 | 版本 |
|---|---|
| `README.md`（本文档） | v0.1 |
| `frontend-agent-api.md` | v0.6 |
| `agent-music-api.md` | v1.0（拆分重构）|
| `agent-speech-api.md` | v1.0（首次发布）|
| `agent-feishu-api.md` | v1.0（首次发布）|