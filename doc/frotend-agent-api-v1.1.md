# 前端 ↔ Agent 接口契约文档 v1.1

# 0 通用基础约定

## 0.1 服务地址

- Agent HTTP 服务地址：`http://localhost:8000`
- HTTP 接口统一前缀：`/api/`
- WebSocket 实时通道：`ws://localhost:8000/ws/client`
- 编码：UTF-8，传输格式统一为 JSON

## 0.2 统一消息格式

### HTTP 响应标准格式

```json
{
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

`code = 0` 代表请求成功，非0代表业务异常。

### WebSocket 双向消息标准结构

所有 WS 消息统一结构，无二进制音频传输：

```json
{
  "type": "chat",
  "subtype": "user_text",
  "id": "前端生成唯一UUID",
  "ts": 1739270400000,
  "payload": {}
}
```

- `id`：请求类消息必填，用于请求与响应匹配；
- `ts`：毫秒级时间戳；
- `payload`：存放业务数据。

## 0.3 通用错误码

| code | 含义                            |
| ---- | ------------------------------- |
| 0    | 成功                            |
| 1001 | 参数错误                        |
| 1002 | APIKey未配置 / 网易云账号未登录 |
| 1003 | 歌单/歌曲资源不存在             |
| 2001 | LLM大模型调用失败               |
| 2002 | 工具调用失败                    |
| 2003 | 请求超时                        |
| 3001 | 网易云音乐服务不可用            |
| 3002 | 网易云接口请求异常              |
| 9999 | 服务内部异常                    |

## 0.4 WebSocket 连接建立规则

1. 前端程序启动后，先调用 `GET /api/init` 获取初始化数据；
2. HTTP 初始化请求成功后，建立 WS 长连接；
3. 连接成功服务端推送 `status.welcome`；
4. 前端每30s发送心跳 `heartbeat.ping`，断线自动重连。

# 1 HTTP 接口（一次性配置、数据查询、业务操作）

按前端功能模块划分，仅保留文档规定功能。

## 1.1 初始化接口

### GET /api/init

**用途**：程序启动一次性拉取全部基础数据
返回 data 包含：

1. 系统配置（deepseek平台APIKey）
2. 网易云账号登录状态
3. UserProfits 用户完整画像数据
4. 本地全部导入歌单列表
5. 当前播放器播放列表、播放状态

## 1.2 设置功能模块（APIKey 设置）

### GET /api/settings

**用途**：获取所有服务密钥配置
返回 data：`{ llm_apikey: "", netease_apikey: "" }`

### PUT /api/settings

**用途**：增量更新 APIKey 配置
请求体：

```json
{
  "llm_apikey": "xxx",
  "netease_apikey": "xxx"
}
```

## 1.3 设置功能模块（网易云账号登录）（暂定，等后端同学处理完网易登录逻辑后再更改）

### POST /api/netease/login

**用途**：传入登录凭证完成网易云账号授权登录
请求体：登录凭证（验证码/扫码临时token）
响应 data：`{ login_status: true, nickname: "用户昵称" }`

### GET /api/netease/status

**用途**：查询当前网易云登录状态、用户昵称

## 1.4 AI画像功能 - 歌单管理（歌单增删查改、链接导入）

### POST /api/playlist/import

**用途**：通过网易云歌单分享链接导入歌单，导入完成自动触发AI画像分析
请求体：

```json
{
  "playlist_url": "网易云歌单链接"
}
```

### GET /api/playlist/list

**用途**：查询本地全部导入歌单，前端页面展示歌单列表

### GET /api/playlist/

**用途**：查询单个歌单内所有歌曲详情

### PUT /api/playlist/

**用途**：修改歌单基础信息（歌单名称、备注）

### DELETE /api/playlist/

**用途**：删除本地存储的指定歌单及歌曲缓存

## 1.5 AI画像功能 - UserProfits 用户画像

### POST /api/user/analyze

**用途**：手动触发AI分析全部本地歌单，自动生成/更新用户音乐画像，存入UserProfits（画像无需前端手动编辑）
响应：`{ code: 0, data: { update_at: 1739270400000 } }`

### GET /api/user/profile

**用途**：查询完整 UserProfits 用户画像数据，前端展示用户喜好

### PUT /api/user/baseinfo

**用途**：仅手动修改用户基础信息（昵称、头像），AI生成的音乐画像不可手动修改
请求体：

```json
{
  "nickname": "小李",
  "avatar_url": "图片地址"
}
```

## 1.6 播放器反馈功能

### POST /api/feedback

**用途**：用户对当前播放歌曲的反馈（喜欢/不喜欢/收藏/切歌）
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
| song_id | string | 歌曲唯一ID |
| action | string | like / dislike / favorite / skip |
| ts | number | 反馈发生时间（毫秒时间戳） |

响应：`{ "code": 0, "msg": "ok", "data": null }`

# 2 WebSocket 实时通信接口（AI Chat、播放器实时控制）

## 2.1 消息 type 枚举（仅保留业务必需类型）

| type      | 通信流向     | 用途                            |
| --------- | ------------ | ------------------------------- |
| chat      | 双向         | AI聊天交互、意图识别（核心）    |
| music     | 服务端→前端 | 播放/暂停/切歌/更新播放列表指令 |
| status    | 双向         | 连接欢迎、播放器状态上报        |
| error     | 服务端→前端 | 实时异常推送                    |
| heartbeat | 双向         | 心跳保活                        |

## 2.2 前端发送至服务端消息

### 2.2.1 chat.user_text（AI Chat统一入口）

前端所有对话、歌曲操作、推荐需求统一使用该消息发送，后端自动识别意图，无需区分细分请求。

```json
{
  "type": "chat",
  "subtype": "user_text",
  "id": "uuid-001",
  "ts": 1739270400000,
  "payload": {
    "text": "从我的歌单推荐一首抒情歌曲"
  }
}
```

### 2.2.3 status.player_event

前端播放器状态变更上报

```json
{
  "type": "status",
  "subtype": "player_event",
  "payload": {
    "event": "play_start / play_end / pause / resume"
  }
}
```

### 2.2.4 heartbeat.ping

心跳探测包，30秒发送一次

```json
{
  "type": "heartbeat",
  "subtype": "ping",
  "ts": 1739270400000
}
```

## 2.3 服务端推送至前端消息

### 2.3.1 chat.reply（AI Chat核心返回消息，严格匹配文档要求）

后端自动分析用户意图，返回 `text`、`url`、`operation` 三段核心内容，前端监听统一处理。

```json
{
  "type": "chat",
  "subtype": "reply",
  "id": "uuid-001",
  "payload": {
    "text": "AI回复文案/歌曲介绍文字",
    "url": "歌曲播放链接/歌曲封面资源地址",
    "operation": "play_song / skip_song / add_playlist / song_intro / recommend",
    "intent": "music_recommend / chat / song_info / playlist_operate"
  }
}
```

字段释义（完全对应前端设计文档）：

1. `text`：AI对话文本、歌曲介绍文案；
2. `url`：歌曲播放资源链接、封面图片链接；
3. `operation`：后端下发操作指令，前端播放器执行对应逻辑。

### 2.3.2 music 播放器控制消息

1. music.play：下发完整歌曲信息与播放链接，前端执行播放

```json
{
  "type": "music",
  "subtype": "play",
  "payload": {
    "song": {},
    "play_url": "歌曲播放地址",
    "auto_play": true
  }
}
```

2. music.pause / music.resume / music.skip：暂停、继续、切歌指令
3. music.update_playlist：同步更新前端本地播放列表

### 2.3.3 status.welcome

WebSocket连接成功后自动推送

```json
{
  "type": "status",
  "subtype": "welcome",
  "payload": {
    "session_id": "会话唯一id"
  }
}
```

### 2.3.4 error

实时异常推送

```json
{
  "type": "error",
  "payload": {
    "code": 3002,
    "msg": "网易云接口请求失败"
  }
}
```

### 2.3.5 heartbeat.pong

心跳响应包，回应前端ping请求

```json
{
  "type": "heartbeat",
  "subtype": "pong",
  "ts": 1739270400000
}
```

# 3 核心数据实体定义

## 3.1 UserProfits 用户画像（文档规定）

```typescript
interface UserProfits {
  // 前端手动维护基础信息
  nickname: string;
  avatar_url?: string;
  // AI分析歌单自动生成，不可前端手动修改
  favorite_genres: string[];    //最喜欢的流派
  disliked_genres: string[];    //不喜欢的流派
  favorite_artists: string[];   //最喜欢的音乐家
  music_preference_desc: string;    //音乐偏好（降序）
  AI_conclustion: String;   //AI一句话总结
  update_at: number; // AI画像最后更新时间戳
}
```

## 3.2 Playlist 歌单

这里仅作参考

```typescript
interface Playlist {
  playlist_id: string;
  name: string;
  source_url: string; // 导入的歌单分享链接
  song_count: number;
  created_at: number;
}
```

## 3.3 Song / Artist / Album 歌曲基础结构

仅作参考

```typescript
interface Song {
  id: string;
  name: string;
  artists: Artist[];
  album: Album;
  duration_ms: number;
  cover_url?: string;
}
interface Artist { id: string; name: string; }
interface Album { id: string; name: string; }
```
