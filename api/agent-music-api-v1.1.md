# Agent ↔ 音乐 API 服务 接口契约

> 版本：v0.2（修订：职责边界 + Tool 抽象）  
> 适用：Python Agent（LangGraph） ↔ Python 音乐 API 服务  
> 通道：HTTP REST（全 REST，无 WebSocket）

---

## 0. 职责边界（重要！先读）

### 0.1 当前边界（MVP）

音乐 API 服务是一个**聚合服务**，对外统一暴露音乐能力，对内封装第三方 SDK。

```
┌────────────────────────────────┐
│        音乐 API 服务           │
│                               │
│   ┌──────────────────┐          │
│   │   音乐能力模块    │         │
│   │                  │        │
│   │  - 网易云搜索     │        │
│   │  - 播放 URL      │         │
│   │  - 私人漫游      │        │
│   │  - AIDJ 口播     │        │
│   │  - 歌词/详情     │        │
│   │  - 红心/收藏     │        │
│   │  - 数据回传      │        │
│   └──────────────────┘          │
└───────────────────────────────┘
```

## 1. Tool 抽象说明（Agent 视角）

> 本文档定义的是 **HTTP 层契约**。在 Agent 内部，**HTTP 接口被进一步封装为 LangGraph Tool**。

### 0.5.1 三层关系

```
┌────────────────┐
│   Agent 决策    │  LangGraph StateGraph 节点
│   (推理/规划)   │  ← 决定"现在要不要换歌"
└────────┬───────┘
         │ 调用
┌────────▼───────┐
│     Tool 层     │  @tool 装饰的 Python 函数
│                │  ← 真正的 Agent 接口
└────────┬───────┘
         │ HTTP
┌────────▼───────┐
│  音乐 API 服务  │  本文档定义的 REST 接口
│                │  ← 把 Tool 调用翻译成 HTTP
└────────────────┘
```

### 0.5.2 为什么不直接让 Agent 调 HTTP

Agent 直接调 HTTP 的问题：
- LLM 要理解 HTTP 协议（容易出错）
- 鉴权、错误处理、参数校验全压在 Prompt 里
- 难以做单元测试和 Mock

**Tool 层的好处**：
- Tool 是 Python 函数，LLM 只需调用 `play_music(song_id="...")`
- 错误处理、参数校验在 Python 代码里
- HTTP 切换成 gRPC / 本地调用，Tool 接口不变

### 0.5.3 Tool 列表（与本接口的映射）

| Tool 名 | 内部调用 | 说明 |
|---|---|---|
| `search_songs(q, limit)` | `GET /songs/search` | 搜索歌曲 |
| `get_song_detail(id)` | `GET /songs/{id}` | 歌曲详情 |
| `get_play_url(id, br)` | `GET /songs/{id}/playurl` | 获取播放 URL（含降级） |
| `recommend_scene(scene, limit)` | `GET /recommend/scene` | 场景音乐 |
| `recommend_daily()` | `GET /recommend/daily` | 每日推荐 |
| `like_song(id)` | `POST /user/favorite_songs/{id}` | 收藏 |
| `unlike_song(id)` | `DELETE /user/favorite_songs/{id}` | 取消收藏 |
| `report_playback(...)` | `POST /playback/report` | 网易云数据回传 |

> Tool 层代码组织在 Agent 端的 `agent/tools/` 目录。Tool 函数的输入输出 schema 与本接口的 HTTP 字段对齐，但用 Pydantic 模型定义。

---

## 2. 通用约定

### 1.1 基础信息
- **音乐 API Base URL**：`http://localhost:8001`（开发期可配置）
- **路径前缀**：`/api/v1/`
- **编码**：UTF-8
- **消息格式**：JSON

### 1.2 鉴权
- 开发期：**无鉴权**（同机本地服务）
- 生产期：预留 `X-API-Key` Header

### 1.3 响应统一格式
```json
{
  "code": 0,
  "msg": "ok",
  "data": { ... }
}
```

### 1.4 错误码
| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数错误 |
| 4003 | 资源不存在 |
| 4101 | 网易云官方接口失败 |
| 4102 | 网易云鉴权失败（token 失效） |
| 4103 | 播放 URL 获取失败（已降级但仍失败） |
| 4291 | QPS 超限 |
| 5001 | 内部异常 |

### 1.5 降级策略总则
> 音乐 API 服务对网易云官方接口失败有**两层降级**：

```
官方 API  →  外链直拼 (music.163.com/song/media/outer/url?id=xxx)
                ↓ 失败
            返回错误 4103
```

---

## 3. 歌曲相关

### 1.1 `GET /api/v1/songs/search`
**用途**：根据关键词搜索歌曲

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `q` | 是 | 搜索关键词 |
| `limit` | 否 | 默认 20，最大 50 |

**响应 data**：
```json
{
  "total": 235,
  "songs": [
    {
      "id": "1962364527",
      "name": "七里香",
      "artists": [{"id": "a1", "name": "周杰伦"}],
      "album": {"id": "al1", "name": "七里香"},
      "duration_ms": 296000,
      "fee": 0,
      "cover_url": "https://..."
    }
  ]
}
```

---

### 1.2 `GET /api/v1/songs/{id}`
**用途**：获取歌曲详情

**路径参数**：`id` —— 网易云加密 id

**响应 data**：
```json
{
  "song": {
    "id": "1962364527",
    "name": "七里香",
    "artists": [{"id": "a1", "name": "周杰伦"}],
    "album": {"id": "al1", "name": "七里香", "cover_url": "..."},
    "duration_ms": 296000,
    "fee": 0,
    "lyric_url": "http://localhost:8001/api/v1/songs/1962364527/lyric"
  }
}
```

---

### 1.3 `GET /api/v1/songs/{id}/playurl`
**用途**：获取歌曲播放 URL（带过期时间）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `br` | 否 | 码率，默认 128000（kbps，可选 320000） |

**响应 data**：
```json
{
  "url": "https://music.163.com/song/media/outer/url?id=1962364527.mp3",
  "expires_at": 1739272200000,
  "br": 128000,
  "source": "outer_url",  // official | outer_url | fallback
  "song": { "id": "...", "name": "...", "duration_ms": 296000 }
}
```

**降级逻辑**：
1. 先尝试官方 `/song/playurl/get/v2`
2. 失败 → 拼外链 `https://music.163.com/song/media/outer/url?id={id}.mp3`
3. 都失败 → 返回 4103

---

### 1.4 `GET /api/v1/songs/{id}/lyric`
**用途**：获取歌词（LRC 格式文本）

**响应 data**：
```json
{
  "lyric": "[00:00.00] 作曲：周杰伦\n[00:01.00] 作词：方文山\n[00:05.20] 窗外的麻雀\n..."
}
```

---

## 4. 推荐相关

### 2.1 `GET /api/v1/recommend/fm`
**用途**：网易云私人漫游（千人千面）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `count` | 否 | 默认 3，最大 3 |

**响应 data**：
```json
{
  "songs": [
    {
      "id": "1962364527",
      "name": "七里香",
      "artists": [{"id": "a1", "name": "周杰伦"}],
      "album": {"id": "al1", "name": "七里香"},
      "duration_ms": 296000,
      "fee": 0
    }
  ]
}
```

---

### 2.2 `GET /api/v1/recommend/scene`
**用途**：场景音乐推荐（深夜、运动、工作等）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `scene` | 是 | `late_night` / `work` / `workout` / `commute` / `relax` / `rainy` |
| `limit` | 否 | 默认 10，最大 30 |

**响应 data**：同 §2.1

---

### 2.3 `GET /api/v1/recommend/daily`
**用途**：每日推荐（30-35 首）

**响应 data**：
```json
{
  "songs": [ /* Song 数组 */ ]
}
```

---

### 2.4 `GET /api/v1/recommend/tags`
**用途**：获取可用场景标签列表

**响应 data**：
```json
{
  "tags": [
    {"key": "late_night", "name": "深夜", "icon": "..."},
    {"key": "work", "name": "工作", "icon": "..."},
    {"key": "workout", "name": "运动", "icon": "..."}
  ]
}
```

---

## 5. 用户数据相关

### 3.1 `GET /api/v1/user/favorite_songs`
**用途**：获取用户红心歌曲

**响应 data**：
```json
{
  "songs": [ /* Song 数组 */ ]
}
```

> 注：用户未登录网易云时返回空数组 + `data.user_logged_in: false`

---

### 3.2 `POST /api/v1/user/favorite_songs/{id}`
**用途**：将歌曲加入红心

**响应**：`{ "code": 0 }`

---

### 3.3 `DELETE /api/v1/user/favorite_songs/{id}`
**用途**：取消红心

**响应**：`{ "code": 0 }`

---

### 3.4 `POST /api/v1/playback/report`
**用途**：向网易云回传播放数据（开始/结束）

**请求 body**：
```json
{
  "song_id": "1962364527",
  "event": "play_end",  // play_start | play_end
  "duration_ms": 280000,
  "ts": 1739270400000,
  "source": "ai_dj"
}
```

**响应**：`{ "code": 0 }`

> 必须调用，否则影响网易云推荐效果

---

## 7. 通用接口

### 5.1 `GET /api/v1/health`
**用途**：健康检查（Agent 启动时调一次）

**响应 data**：
```json
{
  "status": "ok",
  "netease": {"available": true, "qps_left": 48},
  "xfyun": {"available": true}
}
```

---

### 5.2 `GET /api/v1/device/info`
**用途**：当前 deviceid 和 token 信息（调试用）

**响应 data**：
```json
{
  "device_id": "win11-dev-001",
  "anonymous_token": "at_xxx",
  "token_expires": -1,
  "netease_logged_in": false
}
```

---

## 8. 数据结构

### 6.1 Song
同 frontend-agent-api §3.1

### 6.2 PlayUrl
```typescript
interface PlayUrl {
  url: string;
  expires_at: number;
  br: number;
  source: 'official' | 'outer_url' | 'fallback';
  song: Song;
}
```

### 6.3 SceneTag
```typescript
interface SceneTag {
  key: string;        // late_night / work / workout / commute / relax / rainy
  name: string;       // 中文展示名
  icon?: string;
}
```

---

## 9. 网易云鉴权说明（关键！）

### 7.1 匿名 token 流程
1. 首次启动 → `POST /openapi/music/basic/oauth2/login/anonymous` 拿匿名 token
2. 缓存到本地 JSON（`netease_token.json`），**永不过期**
3. 后续所有请求都带 `deviceid` + 匿名 token

### 7.2 实名 token（可选，用户主动扫码登录）
1. `GET /openapi/music/basic/user/oauth2/qrcodekey/get/v2` 拿 qrcode key
2. 前端展示二维码
3. 轮询 `POST /openapi/music/basic/user/oauth2/device/login/qrcode/get`
4. 授权成功 → 拿 access_token + refresh_token
5. token 7 天过期 → 用 refresh_token 续期
6. 失败重登

### 7.3 MVP 建议
- MVP 阶段**只用匿名 token**，不做扫码登录
- 等基础功能跑通后再加实名登录（解锁红心同步、个性化推荐）

---

## 10. 待定 / 后续补充

- [ ] 网易云官方接口申请状态（需要联系商务）
- [ ] 讯飞 API key 申请
- [ ] TTS 音频格式（mp3 / wav）
- [ ] 缓存策略：同一文本的 TTS 是否缓存到本地
- [ ] 失败重试策略（带退避）
- [ ] 数据回传的真实码率计算