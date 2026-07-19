# Agent ↔ 音乐 API 服务 接口契约（音乐模块）

> 版本：v1.0（拆分重构，原 v0.4 内容剥离为三个独立文件）  
> 适用：Python Agent（LangGraph） ↔ Python 音乐 API 服务 · 音乐模块  
> 通道：HTTP REST（全 REST，无 WebSocket）  
> 架构总览：见 [`README.md`](./README.md)

---

## 0. 本模块职责边界

### 0.1 负责的事
- 网易云搜索、播放 URL（含外链降级）
- 私人漫游、场景音乐、每日推荐
- 歌曲详情、歌词、AIDJ 口播
- 用户红心收藏
- 播放数据回传

### 0.2 不负责的事
- ❌ 用户画像、情绪记忆 → Agent Memory
- ❌ 选歌/推荐决策 → Agent LangGraph
- ❌ TTS/ASR → 语音模块（见 `agent-speech-api.md`）
- ❌ 飞书日程 → 飞书模块（见 `agent-feishu-api.md`）

### 0.3 未来可拆分
本模块后续可独立为 **Music Service**，路径前缀 `/api/v1/music/...`。  
当前 MVP 阶段位于 `music_api/music/` 目录，方便后续拆分。

---

## 1. Tool 映射（音乐模块）

> Agent 内部把 HTTP 接口封装为 Tool 函数（`@tool` 装饰）。  
> 完整 Tool 列表见 [`README.md` §5](./README.md#5-tool-层完整列表)。

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

> Tool 代码组织在 Agent 端的 `agent/tools/music_tools.py`。

---

## 2. 通用约定

### 2.1 基础信息
- **音乐 API Base URL**：`http://localhost:8001`（开发期可配置）
- **路径前缀**：`/api/v1/`
- **编码**：UTF-8
- **消息格式**：JSON

### 2.2 鉴权
- 开发期：**无鉴权**（同机本地服务）
- 生产期：预留 `X-API-Key` Header

### 2.3 响应统一格式
```json
{
  "code": 0,
  "msg": "ok",
  "data": { ... }
}
```

### 2.4 错误码（音乐模块）
| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数错误 |
| 4003 | 资源不存在 |
| 4101 | 网易云官方接口失败 |
| 4102 | 网易云鉴权失败（token 失效） |
| 4103 | 播放 URL 获取失败（已降级但仍失败） |
| 4291 | 网易云 QPS 超限 |
| 5001 | 内部异常 |

> 跨模块错误码体系见 [`README.md` §4.4](./README.md#44-错误码体系跨模块)

### 2.5 降级策略总则
> 音乐模块对网易云官方接口失败有**两层降级**：

```
官方 API  →  外链直拼 (music.163.com/song/media/outer/url?id=xxx)
                ↓ 失败
            返回错误 4103
```

---

## 3. 歌曲相关

### 3.1 `GET /api/v1/songs/search`
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

### 3.2 `GET /api/v1/songs/{id}`
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

### 3.3 `GET /api/v1/songs/{id}/playurl`
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
  "source": "outer_url",
  "song": { "id": "...", "name": "...", "duration_ms": 296000 }
}
```

`source` 枚举：`official` / `outer_url` / `fallback`

**降级逻辑**：
1. 先尝试官方 `/song/playurl/get/v2`
2. 失败 → 拼外链 `https://music.163.com/song/media/outer/url?id={id}.mp3`
3. 都失败 → 返回 4103

---

### 3.4 `GET /api/v1/songs/{id}/lyric`
**用途**：获取歌词（LRC 格式文本）

**响应 data**：
```json
{
  "lyric": "[00:00.00] 作曲：周杰伦\n[00:01.00] 作词：方文山\n[00:05.20] 窗外的麻雀\n..."
}
```

---

### 3.5 `GET /api/v1/songs/{id}/aidj_speech`
**用途**：获取网易云 AIDJ 官方口播音频（DJ 介绍这首歌）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `timbre_id` | 否 | 音色 ID（不传则用默认音色） |

**响应 data**：
```json
{
  "audio_url": "http://localhost:8001/media/aidj/1962364527_t1.mp3",
  "duration_ms": 18000,
  "text": "接下来这首七里香，来自周杰伦...",
  "timbre": "male_gentle",
  "source": "official_aidj"
}
```

**降级**：官方接口失败 → 返回 4101，由 Agent 决定是否改用 TTS 合成。

---

## 4. 推荐相关

### 4.1 `GET /api/v1/recommend/fm`
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

### 4.2 `GET /api/v1/recommend/scene`
**用途**：场景音乐推荐（深夜、运动、工作等）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `scene` | 是 | `late_night` / `work` / `workout` / `commute` / `relax` / `rainy` |
| `limit` | 否 | 默认 10，最大 30 |

**响应 data**：同 §4.1

---

### 4.3 `GET /api/v1/recommend/daily`
**用途**：每日推荐（30-35 首）

**响应 data**：
```json
{
  "songs": [ /* Song 数组 */ ]
}
```

---

### 4.4 `GET /api/v1/recommend/tags`
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

### 5.1 `GET /api/v1/user/favorite_songs`
**用途**：获取用户红心歌曲

**响应 data**：
```json
{
  "songs": [ /* Song 数组 */ ],
  "user_logged_in": false
}
```

> 注：用户未登录网易云时返回空数组 + `user_logged_in: false`

---

### 5.2 `POST /api/v1/user/favorite_songs/{id}`
**用途**：将歌曲加入红心

**响应**：`{ "code": 0 }`

---

### 5.3 `DELETE /api/v1/user/favorite_songs/{id}`
**用途**：取消红心

**响应**：`{ "code": 0 }`

---

### 5.4 `POST /api/v1/playback/report`
**用途**：向网易云回传播放数据（开始/结束）

**请求 body**：
```json
{
  "song_id": "1962364527",
  "event": "play_end",
  "duration_ms": 280000,
  "ts": 1739270400000,
  "source": "ai_dj"
}
```

**响应**：`{ "code": 0 }`

> ⚠️ **必须调用**，否则影响网易云推荐效果

---

## 6. 通用接口

### 6.1 `GET /api/v1/health`
**用途**：健康检查（Agent 启动时调一次）

**响应 data**：
```json
{
  "status": "ok",
  "netease": {"available": true, "qps_left": 48}
}
```

---

### 6.2 `GET /api/v1/device/info`
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

## 7. 数据结构

### 7.1 Song
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

### 7.2 Artist / Album
```typescript
interface Artist { id: string; name: string; }
interface Album { id: string; name: string; }
```

### 7.3 PlayUrl
```typescript
interface PlayUrl {
  url: string;
  expires_at: number;
  br: number;
  source: 'official' | 'outer_url' | 'fallback';
  song: Song;
}
```

### 7.4 SceneTag
```typescript
interface SceneTag {
  key: string;        // late_night / work / workout / commute / relax / rainy
  name: string;       // 中文展示名
  icon?: string;
}
```

---

## 8. 网易云鉴权说明（关键！）

### 8.1 匿名 token 流程
1. 首次启动 → `POST /openapi/music/basic/oauth2/login/anonymous` 拿匿名 token
2. 缓存到本地 JSON（`netease_token.json`），**永不过期**
3. 后续所有请求都带 `deviceid` + 匿名 token

### 8.2 实名 token（可选，用户主动扫码登录）
1. `GET /openapi/music/basic/user/oauth2/qrcodekey/get/v2` 拿 qrcode key
2. 前端展示二维码
3. 轮询 `POST /openapi/music/basic/user/oauth2/device/login/qrcode/get`
4. 授权成功 → 拿 access_token + refresh_token
5. token 7 天过期 → 用 refresh_token 续期
6. 失败重登

### 8.3 MVP 建议
- MVP 阶段**只用匿名 token**，不做扫码登录
- 等基础功能跑通后再加实名登录（解锁红心同步、个性化推荐）

---

## 9. 待定 / 后续补充

- [ ] 网易云官方接口申请状态（需要联系商务）
- [ ] 失败重试策略（带退避）
- [ ] 数据回传的真实码率计算
- [ ] 缓存策略：搜索结果是否缓存到本地