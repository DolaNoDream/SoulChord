# 前端 ↔ Agent 接口契约

> 版本：v0.6（飞书：核对 scope / 错误码新增）  
> 适用：Electron 桌宠前端 ↔ Python Agent 服务  
> 通道：WebSocket（主） + HTTP（补充）

---

## 0. 通用约定

### 0.1 基础信息
- **Agent Base URL**：`http://localhost:8000`（开发期可配置）
- **WebSocket 端点**：`ws://localhost:8000/ws/client`
- **HTTP 前缀**：`/api/`
- **协议**：HTTP/1.1、WebSocket RFC 6455
- **编码**：UTF-8
- **消息格式**：JSON（除明确标注的二进制帧外）

### 0.2 WebSocket 消息统一格式
所有 WS 消息（双向）都是如下 JSON 结构：

```json
{
  "type": "chat",
  "subtype": "user_text",
  "id": "uuid，前端生成，用于请求-响应匹配",
  "ts": 1739270400000,
  "payload": { ... }
}
```

- `type`：必填，**7 个枚举值之一**（见 §2.2）
- `subtype`：可选，按 type 细分
- `id`：请求类消息必填；推送类消息可省略
- `payload`：消息体，结构由 type + subtype 决定

### 0.3 HTTP 响应统一格式
```json
{
  "code": 0,
  "msg": "ok",
  "data": { ... }
}
```
- `code = 0`：成功；非 0：失败（错误码见 §0.5）

### 0.4 时间格式
- 所有时间戳用 **毫秒级 Unix 时间戳**（number）

### 0.5 通用错误码
| code | 含义 |
|---|---|
| 0 | 成功 |
| 1001 | 参数错误 |
| 1002 | 未鉴权 / token 失效 |
| 1003 | 资源不存在 |
| 2001 | LLM 调用失败 |
| 2002 | 工具调用失败 |
| 2003 | 超时 |
| 3001 | 音乐 API 服务不可用 |
| 3002 | 网易云接口失败 |
| 3101 | 飞书未授权 / 需要重新连接 |
| 3102 | 飞书接口调用失败 |
| 3103 | 飞书日程数据为空（前端可引导重连）|
| 9999 | 内部异常 |

---

## 1. HTTP 接口（前端 → Agent）

### 1.1 `GET /api/init`
**用途**：前端启动时拉取初始状态（用户画像、最近情绪、当前播放信息、日历状态）

**请求**：无 body

**响应 data**：
```json
{
  "agent": {
    "version": "0.2.0",
    "persona": "night_dj"
  },
  "user_profile": {
    "name": "小李",
    "favorite_genres": ["lo-fi", "华语流行"],
    "favorite_artists": ["周杰伦", "陈奕迅"],
    "disliked_genres": ["重金属"],
    "created_at": 1738000000000
  },
  "recent_moods": [
    {"mood": "tired", "ts": 1739260000000},
    {"mood": "relaxed", "ts": 1739100000000}
  ],
  "current_state": {
    "is_playing": false,
    "current_song": null,
    "scene": "evening",
    "active_expression": "idle"
  },
  "settings": {
    "dj_voice": "male_gentle",
    "auto_greet": true,
    "greet_silent_minutes": 30
  },
  "calendar": {
    "connected": true,
    "current_block": "in_meeting",
    "current_event_summary": "周会",
    "current_event_minutes_remaining": 23,
    "next_event_summary": "代码评审",
    "next_event_minutes_until_start": 40
  }
}
```

**`agent` 字段说明**：
- `version`：Agent 服务版本（语义化版本）
- `persona`：当前生效的 DJ 人格 ID（如 `night_dj`）
- 前端根据 persona 决定桌宠外观、TTS 音色默认值、问候文案风格
- 未来支持多 persona 切换时，persona 可通过 `PUT /api/settings` 修改（见 §1.3 扩展）

**`calendar` 字段说明**：
- `connected`：飞书是否已连接（影响日历相关功能）
- `current_block`：当前情境块（`in_meeting` / `before_event` / `after_event` / `free` / `offline`）
- 摘要字段（`current_event_summary` 等）只用于 UI 展示，**不发往 LLM**
- 详细事件内容通过 `GET /api/feishu/today` 按需拉取

---

### 1.2 `GET /api/settings`
**用途**：获取全部设置项

**响应 data**：同 §1.1 中 `settings` 字段结构

---

### 1.3 `PUT /api/settings`
**用途**：更新设置项（增量更新，未传字段不变）

**请求 body**：
```json
{
  "dj_voice": "female_warm",
  "auto_greet": false,
  "persona": "warm_companion"
}
```

**响应**：`{ "code": 0 }`

> `persona` 字段：可切换 DJ 人格。切换后，前端通过 `chat.reply.payload.agent.persona` 收到新值（生效时机由 Agent 决定，可能是下一轮对话时）

---

### 1.4 `POST /api/feedback`
**用途**：用户对当前歌曲的显式反馈

**请求 body**：
```json
{
  "song_id": "1962364527",
  "action": "like",
  "ts": 1739270400000
}
```

`action` 枚举：
- `like`：喜欢
- `dislike`：不喜欢
- `skip`：跳过
- `favorite`：收藏（红心）

**响应**：`{ "code": 0, "data": { "recorded": true } }`

---

### 1.5 `GET /api/history/songs`
**用途**：拉取最近播放记录

**Query 参数**：
- `limit`：默认 50，最大 200
- `offset`：默认 0

**响应 data**：
```json
{
  "total": 123,
  "items": [
    {
      "song_id": "1962364527",
      "played_at": 1739270000000,
      "feedback": "like",
      "duration_played_ms": 280000
    }
  ]
}
```

---

### 1.6 `POST /api/user/profile`
**用途**：更新用户画像（手动设置偏好）

**请求 body**：
```json
{
  "favorite_genres": ["lo-fi", "爵士"],
  "favorite_artists": ["周杰伦"],
  "disliked_genres": ["重金属"]
}
```

**响应**：`{ "code": 0 }`

---

### 1.7 `GET /api/memory/query`
**用途**：查询 Memory（前端展示用，比如"AI 记得你喜欢什么"）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `key` | 否 | Memory key（如 `favorite_genres`），不传返回全部 |
| `category` | 否 | `profile` / `preference` / `context` / `feedback` |

**category 枚举说明**（业务上分四类）：

| category | 含义 | 例子 |
|---|---|---|
| `profile` | 长期画像（基本不会变的事实） | 名字、职业、城市、作息规律 |
| `preference` | 音乐偏好（长期偏好，可能随时间微调） | 喜欢的曲风、艺人、不喜欢的类型 |
| `context` | 当前状态/情境（短期有效，需衰减或更新） | 最近考试周、最近熬夜、今天很累 |
| `feedback` | 对推荐结果的反馈事实 | 喜欢这首歌、不喜欢那首 |

**响应 data**：
```json
{
  "memories": [
    {
      "key": "favorite_genres",
      "category": "preference",
      "value": ["lo-fi", "华语流行"],
      "confidence": 0.9,
      "source": "user_input",
      "updated_at": 1739000000000
    },
    {
      "key": "current_phase",
      "category": "context",
      "value": "exam_week",
      "confidence": 0.85,
      "source": "inferred",
      "updated_at": 1739260000000
    }
  ]
}
```

> 说明：前端通常只读，Agent 负责写。Memory 实际存储在 Agent 侧的 JSON 文件中，本接口是查询代理。

---

### 1.8 `POST /api/memory/update`
**用途**：写入/更新一条 Memory（前端主动操作，如用户手动设置偏好）

**请求 body**：
```json
{
  "key": "favorite_genres",
  "category": "preference",
  "value": ["lo-fi", "爵士"],
  "source": "user_input"
}
```

`category` 枚举（同 §1.7）：
- `profile`：长期画像
- `preference`：音乐偏好
- `context`：当前情境
- `feedback`：反馈事实

**响应**：
```json
{ "code": 0, "data": { "updated": true, "ts": 1739270400000 } }
```

---

### 1.9 `DELETE /api/memory/{key}`
**用途**：删除一条 Memory

**路径参数**：`key`

**响应**：`{ "code": 0, "data": { "deleted": true } }`

---

### 1.10 `GET /api/feishu/status`
**用途**：查看飞书连接状态

**响应 data**：
```json
{
  "connected": true,
  "user_open_id": "ou_xxx",
  "scope": "calendar:calendar:readonly",
  "token_expires_at": 1739274000000,
  "calendar_count": 3,
  "calendar_id": "cal_xxx",
  "last_sync_at": 1739270000000
}
```

---

### 1.11 `POST /api/feishu/connect`
**用途**：启动飞书 OAuth 授权流程

**请求 body**：
```json
{
  "scopes": ["calendar:calendar:readonly"]
}
```

**响应 data**：
```json
{
  "auth_url": "https://open.feishu.cn/open-apis/authen/v2/index?app_id=cli_xxx&redirect_uri=http://localhost:8765/feishu/cb&state=xxx",
  "state": "csrf-token-xxx",
  "expires_in_seconds": 300
}
```

> 前端收到 `auth_url` 后用 Electron `shell.openExternal()` 打开系统浏览器，**不要在 WebView 里打开**（避免 cookie 问题）

---

### 1.12 `DELETE /api/feishu/disconnect`
**用途**：断开飞书授权，清除本地 token

**响应**：`{ "code": 0 }`

---

### 1.13 `GET /api/feishu/today`
**用途**：获取今日所有日程（前端展示用）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `date` | 否 | ISO 日期 `2026-07-11`，默认今天 |

**响应 data**：
```json
{
  "date": "2026-07-11",
  "events": [
    {
      "event_id": "evt_xxx",
      "summary": "周会",
      "start_at": 1739274000000,
      "end_at": 1739277600000,
      "location": "会议室 A",
      "busy_status": "busy",
      "minutes_until_start": 5
    }
  ],
  "cached_at": 1739270000000,
  "is_stale": false
}
```

> 注：未连接飞书时返回 `{ "events": [], "is_stale": false }`，前端 UI 应引导用户去连接

---

### 1.14 `POST /api/feishu/refresh`
**用途**：前端主动触发日程刷新（用户在主窗口点了"刷新日程"按钮）

**响应**：`{ "code": 0, "data": { "refreshed_at": 1739270000000 } }`

---

## 2. WebSocket 接口

### 2.1 连接建立
- 路径：`ws://localhost:8000/ws/client`
- 无需鉴权（本地服务）
- 连接后服务端立即推送一条 `system.welcome` 消息

---

### 2.2 统一消息类型枚举（7 种）

> 所有 WS 消息的 `type` 字段必须是以下 7 种之一。  
> 新增类型必须经过讨论后扩展，不允许随意增加。

| type | 方向 | 用途 | 已知 subtype |
|---|---|---|---|
| `chat` | 双向 | 用户对话输入、Agent 回复 | `user_text` / `voice_text` / `reply` |
| `tool_call` | Agent→前端 | Agent 调用 Tool（Debug-Only） | `start` / `result` |
| `tts` | Agent→前端 | DJ 语音合成与播放 | `synthesize` / `played` |
| `music` | Agent→前端 | 音乐播放控制 | `play` / `pause` / `resume` / `skip` / `update_playlist` |
| `status` | 双向 | 系统状态 | `welcome` / `player_event` / `window_event` / `expression` / `calendar_update` / `calendar_disconnected` |
| `error` | Agent→前端 | 错误通知 | — |
| `heartbeat` | 双向 | ping/pong | `ping` / `pong` |

---

### 2.3 客户端 → 服务端

#### 2.3.1 `chat.user_text` —— 用户文本输入
```json
{
  "type": "chat",
  "subtype": "user_text",
  "id": "uuid-001",
  "ts": 1739270400000,
  "payload": {
    "text": "今天写代码写了一天，有点累",
    "source": "chat"
  }
}
```

#### 2.3.2 `chat.voice_text` —— ASR 后的文本
> ASR 在前端/音乐 API 完成，前端拿到文字后再通过 WS 发送，避免传音频字节

```json
{
  "type": "chat",
  "subtype": "voice_text",
  "id": "uuid-002",
  "ts": 1739270400000,
  "payload": {
    "text": "换一首",
    "confidence": 0.95
  }
}
```

#### 2.3.3 `status.player_event` —— 播放器状态上报
```json
{
  "type": "status",
  "subtype": "player_event",
  "payload": {
    "event": "play_end",
    "song_id": "1962364527",
    "played_ms": 280000
  }
}
```

`event` 枚举：`play_start` / `play_end` / `pause` / `resume` / `error`

#### 2.3.4 `status.window_event` —— 窗口状态
```json
{
  "type": "status",
  "subtype": "window_event",
  "payload": {
    "event": "main_window_focus"
  }
}
```

`event` 枚举：`main_window_focus` / `main_window_blur` / `deskpet_click`  
> 用于 Agent 决策主动问候时机

#### 2.3.5 `heartbeat.ping` —— 心跳
```json
{ "type": "heartbeat", "subtype": "ping", "ts": 1739270400000 }
```
> 每 30 秒一次，服务端回 `heartbeat.pong`

---

### 2.4 服务端 → 客户端

#### 2.4.1 `status.welcome` —— 连接建立后立即推送
> 实际 type 用 `status`，subtype 为 `welcome`，便于后续扩展系统消息。

```json
{
  "type": "status",
  "subtype": "welcome",
  "payload": {
    "session_id": "uuid-session",
    "server_ts": 1739270400000,
    "agent": {
      "version": "0.2.0",
      "persona": "night_dj"
    }
  }
}
```

#### 2.4.2 `chat.reply` —— Agent 回复（核心消息，可扩展字段）
> 这是整个 WS 里**最重要的消息**，所有 Agent 推理结果都通过这条返回。  
> 字段设计为**可扩展**，预留 debug 字段，前端按需使用。

```json
{
  "type": "chat",
  "subtype": "reply",
  "id": "uuid-respond-001",
  "payload": {
    "reply": "今天辛苦了。",
    "emotion": "tired",            // 推断的用户情绪（可空）
    "intent": "comfort",           // 推断的用户意图（chat | request_music | skip | praise | complaint | ...）
    "scene": "late_night",         // 当前场景
    "confidence": 0.82,            // 情绪/意图推断置信度
    
    "decision_summary": "检测到疲惫 + 深夜场景 → 准备播放舒缓 Lo-fi",  // Agent 决策摘要（非 LLM CoT）
    
    "should_speak": true,          // Agent 是否决定主动说话
    "should_play_music": true      // Agent 是否决定切歌
    
    // 业务字段结束。以下为扩展/debug 字段，前端可选处理。
    "agent": {
      "version": "0.2.0",
      "persona": "night_dj"
    }
  }
}
```

**字段命名约定**：
- `decision_summary` 是 Agent 的**决策摘要**（面向用户的解释），不是 LLM 的 Chain-of-Thought
  - 不依赖 LLM 暴露 CoT（DeepSeek/Qwen 当前都不返回）
  - 内容由 Agent 在工具调用完成后自己生成
  - 示例："检测到疲惫 + 深夜场景 → 准备播放舒缓 Lo-fi"
- 后续如果需要暴露 LLM CoT，用单独字段 `llm_reasoning_*`，避免再次混用

**字段可扩展性约定**：
- 前端**必须**处理的字段：`reply`、`should_speak`、`should_play_music`
- 前端**可选**处理的字段：`emotion`、`intent`、`scene`、`decision_summary`、`agent`
- 内部调试字段以 `_*` 开头（保留扩展空间），前端忽略也行

#### 2.4.3 `tool_call.start` / `tool_call.result` —— 工具调用过程（⚠️ Debug-Only）

> ⚠️ **本节定义的是 Debug 通道，不是业务协议。**
> - 仅在 Agent 启动配置 `debug_mode=true` 时发送
> - 生产环境可关闭（`debug_mode=false`）
> - **前端不应硬依赖此消息**，仅在调试 UI 开启时订阅

```json
{
  "type": "tool_call",
  "subtype": "start",
  "payload": {
    "tool": "play_music",
    "args": {"song_id": "1962364527"},
    "step": 2
  }
}
```

```json
{
  "type": "tool_call",
  "subtype": "result",
  "payload": {
    "tool": "play_music",
    "ok": true,
    "duration_ms": 240
  }
}
```

> 用于前端在调试 UI 上展示 Agent 的工具调用链。  
> 业务上等价的信号是 `chat.reply.payload.should_play_music=true` + 随后的 `music.play` 消息。

#### 2.4.4 `tts.synthesize` —— DJ 语音合成
```json
{
  "type": "tts",
  "subtype": "synthesize",
  "id": "uuid-tts-001",
  "payload": {
    "text": "晚上好，今天是不是又忙了一天？",
    "audio_url": "http://localhost:8000/media/tts/abc123.mp3",
    "audio_duration_ms": 4500,
    "voice": "male_gentle",
    "expression": "smile"  // 同步切换桌宠表情
  }
}
```

> 前端播放完音频后回 `tts.played` 消息。

#### 2.4.5 `tts.played` —— DJ 语音播放完成（前端→Agent）
```json
{
  "type": "tts",
  "subtype": "played",
  "id": "uuid-tts-001",
  "payload": { "played_ms": 4500 }
}
```

#### 2.4.6 `music.play` —— 播放歌曲
```json
{
  "type": "music",
  "subtype": "play",
  "payload": {
    "song": {
      "id": "1962364527",
      "name": "七里香",
      "artists": [{"id": "a1", "name": "周杰伦"}],
      "album": {"id": "al1", "name": "七里香"},
      "duration_ms": 296000,
      "cover_url": "https://p2.music.126.net/.../xxx.jpg",
      "fee": 0
    },
    "play_url": "https://music.163.com/song/media/outer/url?id=1962364527.mp3",
    "play_url_expires_at": 1739272200000,
    "auto_play": true,
    "reason": "匹配你'疲惫+深夜'的情绪"
  }
}
```

#### 2.4.7 `music.pause` / `music.resume` / `music.skip`
```json
{ "type": "music", "subtype": "pause", "payload": { "song_id": "1962364527" } }
{ "type": "music", "subtype": "resume", "payload": { "song_id": "1962364527" } }
{ "type": "music", "subtype": "skip", "payload": { "song_id": "1962364527", "reason": "user_request" } }
```

#### 2.4.8 `music.update_playlist` —— 更新播放队列
```json
{
  "type": "music",
  "subtype": "update_playlist",
  "payload": {
    "songs": [
      { "id": "...", "name": "...", "artists": [{"name": "..."}], "duration_ms": 296000 }
    ],
    "current_index": 0
  }
}
```

#### 2.4.9 `status.expression` —— 桌宠表情
```json
{
  "type": "status",
  "subtype": "expression",
  "payload": {
    "expression": "playing",
    "duration_ms": 5000
  }
}
```

`expression` 枚举：`idle` / `listening` / `talking` / `playing` / `happy` / `sleepy`

#### 2.4.10 `status.calendar_update` —— 日历状态变化（Agent→前端）
> 当 Agent 检测到日程块切换（如"刚开完会 → 空闲"），主动推送。

```json
{
  "type": "status",
  "subtype": "calendar_update",
  "payload": {
    "current_block": "after_event",
    "previous_block": "in_meeting",
    "current_event_summary": null,
    "next_event_summary": "代码评审",
    "next_event_minutes_until_start": 40,
    "trigger": "event_ended"
  }
}
```

**trigger 枚举**：
- `event_ended`：刚结束一个日程
- `event_starting_soon`：距下一个日程 < 15 分钟
- `manual_refresh`：用户主动刷新
- `token_refreshed`：token 自动续期（带新 cached_at）

> 前端收到此消息后：
> 1. 更新主窗口顶部的"日程条"展示
> 2. **不**做任何业务决策（DJ 行为由 Agent 内部决定）

#### 2.4.11 `status.calendar_disconnected` —— 飞书断开（Agent→前端）
```json
{
  "type": "status",
  "subtype": "calendar_disconnected",
  "payload": {
    "reason": "token_expired",
    "needs_reauth": true
  }
}
```

`reason` 枚举：`token_expired` / `user_revoked` / `network_error`

> 前端收到此消息后在设置面板提示"飞书授权已失效，请重新连接"。

#### 2.4.12 `error` —— 错误通知
```json
{
  "type": "error",
  "payload": {
    "code": 2001,
    "msg": "LLM 调用超时",
    "recoverable": true,
    "related_id": "uuid-respond-001"
  }
}
```

#### 2.4.13 `heartbeat.pong` —— 心跳响应
```json
{ "type": "heartbeat", "subtype": "pong", "ts": 1739270400000 }
```

---

## 3. 数据结构定义

### 3.1 Song（歌曲）
```typescript
interface Song {
  id: string;              // 网易云加密 id（32 位字符串）
  name: string;
  artists: Artist[];
  album: Album;
  duration_ms: number;
  fee: number;             // 0=免费 1=VIP 4=数字专辑 8=低质免费
  cover_url?: string;
}
```

### 3.2 Artist
```typescript
interface Artist {
  id: string;
  name: string;
}
```

### 3.3 Album
```typescript
interface Album {
  id: string;
  name: string;
}
```

### 3.4 Memory
```typescript
interface Memory {
  key: string;             // 如 'favorite_genres'
  category: 'profile' | 'preference' | 'context' | 'feedback';
  value: any;              // 与 category 对应的值
  confidence: number;      // 0-1
  source: 'user_input' | 'inferred' | 'feedback';
  updated_at: number;      // 毫秒时间戳
}
```

**category 选用指南**（避免乱用）：
- 不确定是 profile 还是 preference 时：能改变人的事实放 `profile`（职业），跟音乐有关的偏好放 `preference`（喜欢 Lo-fi）
- 不确定是 preference 还是 context 时：超过 1 周还有效的放 `preference`，否则放 `context`
- 不要新增 `fact` 这种太泛的分类——`profile` 已经覆盖"事实"

### 3.5 Agent
```typescript
interface Agent {
  version: string;         // 语义化版本，如 '0.2.0'
  persona: string;         // DJ 人格 ID，如 'night_dj' / 'warm_companion'
}
```

**persona 已知值**：
| persona | 风格 | 默认音色 |
|---|---|---|
| `night_dj` | 深夜主播，温柔不打扰 | `male_gentle` |
| `warm_companion` | 温暖陪伴，关怀型 | `female_warm` |
| `energetic_jockey` | 动感节奏，鼓励型 | `male_lively` |

> 未来扩展 persona 时，只新增 enum 值即可，接口字段不变。

### 3.6 CalendarEvent（日历事件）
```typescript
interface CalendarEvent {
  event_id: string;
  summary: string;          // 事件标题（前端展示）
  description?: string;     // 仅前端按需拉取，Agent 不主动用
  start_at: number;         // 毫秒时间戳
  end_at: number;
  location?: string;        // 仅前端展示用
  is_all_day: boolean;
  status: 'confirmed' | 'tentative' | 'cancelled';
  busy_status: 'busy' | 'free' | 'tentative';
  attendees_count?: number;
}
```

### 3.7 CurrentSnapshot（当前日历快照，Agent 内部用）
```typescript
interface CurrentSnapshot {
  current_event?: CalendarEvent;   // 当前进行中（可空）
  next_event?: CalendarEvent;      // 下一个即将开始（可空）
  current_block: 'in_meeting' | 'before_event' | 'after_event' | 'free' | 'offline';
  snapshot_at: number;
}
```

> 这个结构在 Agent 内部流转，**不会**通过 API 直接暴露给前端。前端拿到的是 §1.1 中 `calendar` 字段的"摘要版"。

### 3.8 Memory 的 context 范例（含飞书日历）

飞书接入后，`context` category 多了几类典型 key：

| key | value 示例 | 说明 |
|---|---|---|
| `calendar_current_block` | `"in_meeting"` | 当前日历块（实时更新） |
| `calendar_pattern_meeting_density` | `"high"` | 用户会议密度（"high"/"medium"/"low"，由 Agent 推断） |
| `current_phase` | `"exam_week"` | 长期 context（如考试周） |
| `recent_sleep_pattern` | `"late_nights"` | 近期作息（Agent 推断） |

> 注意：日历事件**标题/地点**不写 Memory，只写"会议密度""日程繁忙度"这种**聚合标签**，避免隐私泄露。

---

## 4. 待定 / 后续补充

- [ ] WebSocket 鉴权方案（如果未来 Agent 暴露到局域网）
- [ ] 多设备同步（如果支持手机端）
- [ ] 用户登录态与网易云账号打通
- [ ] TTS 音频是否改为 WS 二进制帧传输（优化延迟）
- [ ] `chat.reply` 字段是否会扩展（如附带的推荐歌单列表）
- [ ] `tool_call` 详细程度（MVP 是否需要把每一步都暴露给前端）
- [ ] 飞书授权回调是否要走前端代理（避免本地 HTTP server）