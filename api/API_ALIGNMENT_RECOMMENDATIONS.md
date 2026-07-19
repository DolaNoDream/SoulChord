# SoulChord 前后端接口对齐建议文档

> 基于 [API_DOC.md](API_DOC.md)（后端）与 front 分支前端代码逐项对比，提出双方修改建议。

---

## 一、对比基准

以实训项目两份权威文档为准：

| 基准文档 | 作用 |
|----------|------|
| 前端功能设计文档v1.1.md | 定义数据结构（UserProfits / Playlist / Song） |
| frotend-agent-api-v1.1.md | 定义 HTTP 接口路径、请求体、响应格式、错误码 |

若 API_DOC.md 与基准文档冲突，以基准文档为准；若基准文档未明确而双方实现不同，选择更合理的方案。

---

## 二、建议后端修改（4 项）

### B-1. 【必须】UserProfits 补充 `disliked_genres` 字段

| 对比 | 内容 |
|------|------|
| 基准文档 | ✅ 前端功能设计文档v1.1 第145行明确：`disliked_genres: string[]` |
| 后端 API_DOC | ❌ UserProfits 无此字段 |
| 前端 | ✅ 已定义 `disliked_genres: string[]` |

**建议**：后端 UserProfits 增加字段：

```python
class UserProfits(BaseModel):
    # ... 现有字段 ...
    disliked_genres: List[str] = []   # 新增：排斥曲风
```

对应 JSON 文件中添加 `"disliked_genres": []`。

---

### B-2. 【必须】修正 `AI_conclustion` 拼写错误

| 对比 | 内容 |
|------|------|
| 基准文档 | frotend-agent-api-v1.1.md 第337行：`AI_conclustion`（本身就有拼写错误） |
| 后端 API_DOC | `AI_conclustion` |
| 前端 | `AI_conclusion`（正确拼写） |

**建议**：后端修正为 `AI_conclusion`。基准文档虽然有同样拼写错误，但正确的英文是 "conclusion"，修正后也更利于后续维护。同时前端保持不变。

```python
AI_conclusion: str = ""   # 修正拼写
```

> 如果不想改后端代码，前端改为 `AI_conclustion` 也可以，但拼写错误会一直保留。推荐后端修正。

---

### B-3. 【建议】补充缺失的 6 个错误码

| 对比 | 内容 |
|------|------|
| 基准文档 | frotend-agent-api-v1.1.md 第46-57行：10 个错误码 |
| 后端 API_DOC | 仅有 4 个：`0, 1001, 1003, 9999` |
| 前端 | 已定义全部 10 个（[utils/errorCodes.ts](src/utils/errorCodes.ts)） |

**建议**：后端补充以下 6 个错误码，在对应业务场景返回：

| code | 含义 | 触发场景 |
|------|------|----------|
| 1002 | APIKey未配置 / 网易云账号未登录 | AI 对话、歌单分析时 Key 为空 |
| 2001 | LLM大模型调用失败 | DeepSeek API 异常 |
| 2002 | 工具调用失败 | Agent 工具执行异常 |
| 2003 | 请求超时 | LLM 调用超时 |
| 3001 | 网易云音乐服务不可用 | 网易云 API 无响应 |
| 3002 | 网易云接口请求异常 | 网易云 API 返回错误 |

---

### B-4. 【必须】新增 HTTP 接口：POST /api/feedback

| 对比 | 内容 |
|------|------|
| 基准文档 | frontend-agent-api-v1.1 未明确定义（但前端功能设计文档 4.4 定义了 SongFeedback 数据结构） |
| 后端 API_DOC | ❌ 无此接口 |
| 前端 | ✅ 已调用：`POST /api/feedback` ( [src/api/agent.ts:169-174](src/api/agent.ts#L169-L174) ) |

**用途**：用户对当前播放歌曲的反馈（喜欢/不喜欢/收藏/切歌）。

**建议后端新增路由**（`api/http/` 下新增 `feedback_router.py` 或在 `user_router.py` 中添加）：

```
POST /api/feedback
```

请求体：
```json
{
  "song_id": "186001",
  "action": "like",
  "ts": 1739270400000
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `song_id` | string | 歌曲唯一 ID |
| `action` | string | `like` / `dislike` / `favorite` / `skip` |
| `ts` | number | 反馈发生时间（毫秒时间戳） |

响应：`{ "code": 0, "msg": "ok", "data": null }`

参考 Pydantic 模型：
```python
class FeedbackRequest(BaseModel):
    song_id: str
    action: str   # like | dislike | favorite | skip
    ts: int
```

---

### B-5. 【必须】新增 HTTP 接口：GET /api/history/songs

| 对比 | 内容 |
|------|------|
| 基准文档 | frontend-agent-api-v1.1 未明确定义（播放历史为项目额外实现的增强功能） |
| 后端 API_DOC | ❌ 无此接口 |
| 前端 | ✅ 已调用：`GET /api/history/songs?limit=50&offset=0` ( [src/api/agent.ts:179-189](src/api/agent.ts#L179-L189) ) |

**用途**：分页查询用户播放历史记录。数据来源于前端 WS `status.player_event` 上报（见 B-6），后端负责记录并持久化。

**建议后端新增路由**：

```
GET /api/history/songs?limit=50&offset=0
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `limit` | int | 否 | 50 | 每页条数 |
| `offset` | int | 否 | 0 | 偏移量 |

响应：
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "total": 128,
    "items": [
      {
        "song_id": "186001",
        "played_at": 1739270400000,
        "feedback": "favorite",
        "duration_played_ms": 234000
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 总记录数 |
| `items[].song_id` | string | 歌曲 ID |
| `items[].played_at` | int | 播放时间（毫秒时间戳） |
| `items[].feedback` | string | `like` / `dislike` / `skip` / `favorite` / `""` |
| `items[].duration_played_ms` | int | 实际播放时长（毫秒） |

数据来源链路：
```
前端 WS status.player_event { event: "play_start", song_id }
  → 后端创建记录（started_at = now）
前端 HTTP POST /api/feedback { song_id, action }
  → 后端更新 feedback
前端 WS status.player_event { event: "play_end"|"skip", song_id, played_ms }
  → 后端写入 duration_played_ms
前端 HTTP GET /api/history/songs
  → 后端按 played_at 倒序返回
```

---
---

### B-7. （原 B-4）init 接口 ✅ 已满足

---

## 三、建议前端修改（6 项）

### F-1. 【必须】init 响应对齐后端 `player_state`

| 对比 | 内容 |
|------|------|
| 后端 | 字段名 `player_state`，内容 `{ current_song, play_url, is_playing, playlist, current_index }` |
| 前端 | 字段名 `current_state`，内容 `{ is_playing, current_song, scene, active_expression }` |

**问题**：字段名不同，且前端多了 `scene`/`active_expression`（旧 AI DJ 遗留），少了 `play_url`/`playlist`/`current_index`。

**建议前端修改**：

```typescript
// src/api/agent.ts — fetchInit 返回类型
export async function fetchInit(): Promise<{
  user_profile: UserProfits
  playlists: Playlist[]
  netease_status: { login_status: boolean; nickname: string }
  settings: Record<string, unknown>
  player_state: {                          // ← 改名 + 改结构
    current_song: Song | null
    play_url: string | null
    is_playing: boolean
    playlist: Song[]
    current_index: number
  }
}>
```

同时删除 `agent: AgentInfo`、`recent_moods: RecentMood[]` 两个后端不返回的字段。相应地 [src/stores/user.ts](src/stores/user.ts) 中 `loadInit()` 不再设置 `agentInfo`。

[src/App.vue](src/App.vue) 中 init 后同步播放器状态：

```typescript
if (initData.player_state) {
  playerStore.queue = initData.player_state.playlist
  if (initData.player_state.current_song) {
    playerStore.playSong(
      initData.player_state.current_song,
      initData.player_state.play_url || ''
    )
    if (!initData.player_state.is_playing) playerStore.togglePlay()
  }
}
```

---

### F-2. 【必须】歌单详情响应对齐后端

| 对比 | 内容 |
|------|------|
| 后端 | Playlist 对象内直接包含 `songs: Song[]` |
| 前端 | 期望 `{ playlist: Playlist, songs: Song[] }` 的包装结构 |

**建议前端修改**：

1. `src/types/music.ts` — Playlist 增加 `songs` 字段：

```typescript
export interface Playlist {
  playlist_id: string
  name: string
  source_url: string
  song_count: number
  created_at: number
  songs?: Song[]   // ← 新增：歌曲列表（详情接口返回）
}
```

2. `src/api/agent.ts` — getPlaylistDetail 返回类型改为直接返回 Playlist：

```typescript
export async function getPlaylistDetail(playlistId: string): Promise<Playlist> {
  const res = await http.get(`/playlist/${playlistId}`)
  return res.data   // 直接返回 Playlist（含 songs）
}
```

3. `src/stores/playlist.ts` — viewPlaylist 适配：

```typescript
async function viewPlaylist(playlistId: string): Promise<void> {
  const detail = await getPlaylistDetail(playlistId)
  selectedPlaylist.value = detail
  selectedSongs.value = detail.songs || []
}
```

---

### F-3. 【必须】网易云登录请求体改为 `{ credential }`

| 对比 | 内容 |
|------|------|
| 后端 | `{ "credential": "xxx" }` |
| 前端 | `{ "type": "qr"|"sms", "token": "xxx" }` |

**理由**：后端已按 `credential` 实现，前端改动成本更低（仅一个函数的参数）。

**建议前端修改**：

```typescript
// src/api/agent.ts
export async function postNeteaseLogin(credential: string): Promise<{
  login_status: boolean; nickname: string
}> {
  const res = await http.post('/netease/login', { credential })
  return res.data
}
```

[src/components/SettingsDrawer.vue](src/components/SettingsDrawer.vue) 中调用处同步修改，去掉 `type` 字段，将 Token/验证码作为 `credential` 传入。

---

### F-4. 【必须】PUT /api/playlist 的 `note` → `remark`

| 对比 | 内容 |
|------|------|
| 后端 | 请求体字段名 `remark` |
| 前端 | 请求体字段名 `note` |

**建议前端修改**：

```typescript
// src/api/agent.ts — updatePlaylist
export async function updatePlaylist(playlistId: string, data: {
  name?: string
  remark?: string   // ← note → remark
}): Promise<void> {
  await http.put(`/playlist/${playlistId}`, data)
}
```

---

### F-5. 【建议】Song 类型 `fee` 改为可选

| 对比 | 内容 |
|------|------|
| 后端 | Song 无 `fee` 字段 |
| 前端 | Song 有 `fee: number`（必填） |

**建议前端修改**：`fee` 改为可选，兼容后端不返回此字段的情况。

```typescript
// src/types/music.ts
export interface Song {
  // ...
  fee?: number   // 改为可选
}
```

---

### F-6. 【建议】删除 `AgentInfo` 和 `RecentMood` 类型

| 对比 | 内容 |
|------|------|
| 后端 | 无这两个类型 |
| 前端 | 定义了 `AgentInfo`、`RecentMood`，在 fetchInit 中期望返回 |

**理由**：这两个是旧 AI DJ 设计的遗留类型，后端 API_DOC 未定义。前端 App.vue 中 `userStore.agentInfo?.persona` 的日志输出也可移除。

---

## 四、建议双方都不改（差异可接受）

| # | 差异 | 原因 |
|---|------|------|
| 1 | GET /api/playlist/list 返回含 `songs: []` | 前端仅读 `playlist_id/name/song_count`，多余字段自动忽略，不影响功能 |
| 2 | PUT /api/settings 后端返回完整配置 | 前端不读响应 data，多余数据无影响 |
| 3 | PUT /api/user/baseinfo 后端返回完整画像 | 前端不读响应 data，多余数据无影响 |
| 4 | Song 后端不返回 `cover_url` 时为空 | 前端已用 `cover_url?` 可选，兼容 |

---

## 五、修改优先级汇总

### 后端（4 项 → 7 项）

| 优先级 | 编号 | 内容 | 改动量 |
|--------|------|------|--------|
| **P0** | B-1 | UserProfits 增加 `disliked_genres` | 1 行 |
| **P0** | B-2 | `AI_conclustion` → `AI_conclusion` | 全局替换 |
| **P0** | B-4 | 新增 `POST /api/feedback` 接口 | ~15 行 |
| **P0** | B-5 | 新增 `GET /api/history/songs` 接口 | ~20 行 |
| **P0** | B-6 | 新增 WebSocket 实时通信层（11 种消息） | 核心功能 |
| P1 | B-3 | 补充 6 个错误码 | ~10 行 |

### 前端

| 优先级 | 编号 | 内容 | 改动文件 |
|--------|------|------|----------|
| **P0** | F-1 | init 响应对齐 `player_state` | agent.ts, user.ts, App.vue |
| **P0** | F-2 | 歌单详情对齐后端 Playlist 含 songs | types/music.ts, agent.ts, playlist.ts |
| **P0** | F-3 | 登录请求体改为 `{ credential }` | agent.ts, SettingsDrawer.vue |
| **P0** | F-4 | `note` → `remark` | agent.ts |
| P1 | F-5 | Song `fee` 改为可选 | types/music.ts |
| P1 | F-6 | 删除 AgentInfo/RecentMood | types/user.ts, agent.ts, user.ts, App.vue |

