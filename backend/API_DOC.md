# SoulChord Backend API 文档

## 1 项目目录结构

```
backend/
├── main.py                    # FastAPI 应用入口
├── requirements.txt           # Python 依赖配置
├── __init__.py               # 包初始化文件
├── api/
│   ├── __init__.py
│   └── http/                 # HTTP 接口路由分组
│       ├── __init__.py       # 路由导出文件
│       ├── init_router.py    # /api/init 初始化接口
│       ├── setting_router.py # API 密钥配置接口
│       ├── netease_router.py # 网易云登录接口
│       ├── playlist_router.py# 歌单导入/增删改查接口
│       └── user_router.py    # 用户画像、AI分析接口
├── db/                       # 数据库模块
│   ├── __init__.py           # 数据库模块初始化，导出所有 store
│   ├── json_store.py         # JSON 文件存储工具类
│   └── models.py             # Pydantic 数据模型定义
├── data/                     # JSON 数据文件存储目录（运行时生成）
│   ├── settings.json
│   ├── netease.json
│   ├── user_profile.json
│   ├── playlists.json
│   └── player.json
└── test/                     # 测试目录
    ├── test_db.py            # 数据库操作测试
    ├── test_init.py          # 初始化接口测试
    ├── test_settings.py      # 密钥配置接口测试
    ├── test_netease.py       # 网易云登录接口测试
    ├── test_playlist.py      # 歌单接口测试
    ├── test_user.py          # 用户画像接口测试
    └── run_tests.py          # 统一测试运行入口
```

## 2 文件作用说明

### 2.1 入口文件

| 文件 | 作用 |
|------|------|
| `main.py` | FastAPI 应用入口，创建 app 实例并注册所有路由 |
| `requirements.txt` | Python 依赖列表：fastapi, uvicorn, pydantic, pytest, httpx |

### 2.2 API 路由文件

| 文件 | 作用 | 包含接口 |
|------|------|----------|
| `api/http/__init__.py` | 导出所有路由对象，供 main.py 导入注册 | - |
| `init_router.py` | 程序启动初始化接口 | `GET /api/init` |
| `setting_router.py` | API 密钥配置管理 | `GET/PUT /api/settings` |
| `netease_router.py` | 网易云音乐账号登录 | `POST /api/netease/login`, `GET /api/netease/status` |
| `playlist_router.py` | 歌单 CRUD 操作 | 5 个接口 |
| `user_router.py` | 用户画像管理 | `GET/PUT /api/user/*`, `POST /api/user/analyze` |

### 2.3 数据库模块

| 文件 | 作用 |
|------|------|
| `db/__init__.py` | 初始化所有 JSONStore/CollectionStore 实例，导出供路由使用 |
| `db/json_store.py` | JSONStore 和 CollectionStore 两个核心存储类 |
| `db/models.py` | Pydantic 数据模型定义，包含请求体和数据实体 |

## 3 HTTP 接口文档

### 3.1 统一响应格式

所有 HTTP 接口返回统一格式：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0 表示成功，非 0 表示业务异常 |
| `msg` | string | 提示信息 |
| `data` | any | 业务数据 |

### 3.2 通用错误码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1001 | 参数错误 |
| 1003 | 歌单/歌曲资源不存在 |
| 9999 | 服务内部异常 |

### 3.3 初始化接口

#### GET /api/init

**用途**：程序启动一次性拉取全部基础数据

**请求**：无参数

**响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "settings": { "llm_apikey": "", "netease_apikey": "" },
    "netease_status": { "login_status": false, "nickname": "" },
    "user_profile": {
      "nickname": "用户",
      "avatar_url": null,
      "favorite_genres": [],
      "favorite_artists": [],
      "music_preference_desc": "",
      "AI_conclustion": "",
      "update_at": 0
    },
    "playlists": [],
    "player_state": {
      "current_song": null,
      "play_url": null,
      "is_playing": false,
      "playlist": [],
      "current_index": 0
    }
  }
}
```

### 3.4 设置功能模块

#### GET /api/settings

**用途**：获取所有服务密钥配置

**请求**：无参数

**响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "llm_apikey": "xxx",
    "netease_apikey": "xxx"
  }
}
```

#### PUT /api/settings

**用途**：增量更新 APIKey 配置

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `llm_apikey` | string | 否 | DeepSeek 平台 APIKey |
| `netease_apikey` | string | 否 | 网易云 APIKey |

```json
{
  "llm_apikey": "xxx",
  "netease_apikey": "xxx"
}
```

**响应**：返回更新后的完整配置

### 3.5 网易云账号登录

#### POST /api/netease/login

**用途**：传入登录凭证完成网易云账号授权登录

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `credential` | string | 是 | 登录凭证（验证码/扫码临时token） |

```json
{
  "credential": "xxx"
}
```

**响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "login_status": true,
    "nickname": "网易云用户"
  }
}
```

#### GET /api/netease/status

**用途**：查询当前网易云登录状态、用户昵称

**请求**：无参数

**响应**：同登录成功响应

### 3.6 歌单管理

#### POST /api/playlist/import

**用途**：通过网易云歌单分享链接导入歌单

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `playlist_url` | string | 是 | 网易云歌单分享链接 |

```json
{
  "playlist_url": "https://music.163.com/#/playlist?id=123456"
}
```

**响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "playlist_id": "uuid-string",
    "name": "未命名歌单",
    "source_url": "https://music.163.com/#/playlist?id=123456",
    "song_count": 0,
    "created_at": 1739270400000,
    "songs": []
  }
}
```

#### GET /api/playlist/list

**用途**：查询本地全部导入歌单

**请求**：无参数

**响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": [
    {
      "playlist_id": "uuid-1",
      "name": "歌单1",
      "source_url": "xxx",
      "song_count": 10,
      "created_at": 1739270400000,
      "songs": []
    }
  ]
}
```

#### GET /api/playlist/{playlist_id}

**用途**：查询单个歌单内所有歌曲详情

**路径参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `playlist_id` | string | 歌单 ID |

**成功响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "playlist_id": "uuid-1",
    "name": "歌单1",
    "source_url": "xxx",
    "song_count": 10,
    "created_at": 1739270400000,
    "songs": [...]
  }
}
```

**失败响应**（歌单不存在）：

```json
{
  "code": 1003,
  "msg": "歌单不存在",
  "data": null
}
```

#### PUT /api/playlist/{playlist_id}

**用途**：修改歌单基础信息

**路径参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `playlist_id` | string | 歌单 ID |

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 歌单名称 |
| `remark` | string | 否 | 歌单备注 |

**成功响应**：返回更新后的歌单信息

**失败响应**：
- `code: 1001` - 参数错误（未传任何参数）
- `code: 1003` - 歌单不存在

#### DELETE /api/playlist/{playlist_id}

**用途**：删除本地存储的指定歌单及歌曲缓存

**路径参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `playlist_id` | string | 歌单 ID |

**成功响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": null
}
```

**失败响应**（歌单不存在）：

```json
{
  "code": 1003,
  "msg": "歌单不存在",
  "data": null
}
```

### 3.7 用户画像

#### POST /api/user/analyze

**用途**：手动触发 AI 分析全部本地歌单，生成用户音乐画像

**请求**：无参数

**响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "update_at": 1739270400000
  }
}
```

#### GET /api/user/profile

**用途**：查询完整 UserProfits 用户画像数据

**请求**：无参数

**响应**：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "nickname": "用户",
    "avatar_url": "https://example.com/avatar.jpg",
    "favorite_genres": ["流行", "摇滚", "民谣"],
    "favorite_artists": ["周杰伦", "陈奕迅"],
    "music_preference_desc": "根据您的歌单分析生成的音乐偏好描述",
    "AI_conclustion": "您是一位热爱音乐的用户",
    "update_at": 1739270400000
  }
}
```

#### PUT /api/user/baseinfo

**用途**：修改用户基础信息（昵称、头像）

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `nickname` | string | 否 | 用户昵称 |
| `avatar_url` | string | 否 | 头像图片地址 |

**成功响应**：返回更新后的完整用户画像

**失败响应**（无参数）：

```json
{
  "code": 1001,
  "msg": "参数错误",
  "data": null
}
```

## 4 数据库模块文档

### 4.1 存储类说明

#### JSONStore 类

**文件**：[db/json_store.py](file:///e:/Code/gitRepo/SoulChord/SoulChord/backend/db/json_store.py#L8-L56)

**作用**：键值对类型数据的 JSON 文件存储工具

**构造函数**：

```python
JSONStore(file_path: str, default_data: Any = None)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `file_path` | string | JSON 文件路径 |
| `default_data` | any | 默认数据，文件不存在时使用 |

**方法**：

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `read()` | any | 读取文件内容，返回字典或默认数据 |
| `write(data)` | None | 写入数据到文件 |
| `update(data)` | dict | 增量更新，合并字典并写入 |
| `get(key, default)` | any | 获取指定键的值 |
| `set(key, value)` | None | 设置指定键的值 |

**使用示例**：

```python
from backend.db.json_store import JSONStore

store = JSONStore("data/settings.json", {"llm_apikey": "", "netease_apikey": ""})
store.update({"llm_apikey": "new-key"})
settings = store.read()
```

#### CollectionStore 类

**文件**：[db/json_store.py](file:///e:/Code/gitRepo/SoulChord/SoulChord/backend/db/json_store.py#L58-L115)

**作用**：列表集合类型数据的 JSON 文件存储工具

**构造函数**：

```python
CollectionStore(file_path: str)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `file_path` | string | JSON 文件路径 |

**方法**：

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `list()` | list | 获取所有项目列表 |
| `get_by_id(item_id, id_field)` | dict/None | 根据 ID 查询单个项目 |
| `add(item)` | dict | 添加新项目 |
| `update(item_id, updates, id_field)` | dict/None | 更新指定项目 |
| `delete(item_id, id_field)` | bool | 删除指定项目 |

**使用示例**：

```python
from backend.db.json_store import CollectionStore

store = CollectionStore("data/playlists.json")
store.add({"playlist_id": "1", "name": "我的歌单"})
playlists = store.list()
playlist = store.get_by_id("1", id_field="playlist_id")
store.update("1", {"name": "新名称"}, id_field="playlist_id")
store.delete("1", id_field="playlist_id")
```

### 4.2 预设存储实例

**文件**：[db/__init__.py](file:///e:/Code/gitRepo/SoulChord/SoulChord/backend/db/__init__.py#L16-L38)

| 实例名 | 类型 | 文件路径 | 用途 |
|--------|------|----------|------|
| `settings_store` | JSONStore | `data/settings.json` | 存储 API 密钥配置 |
| `netease_store` | JSONStore | `data/netease.json` | 存储网易云登录状态 |
| `user_profile_store` | JSONStore | `data/user_profile.json` | 存储用户画像数据 |
| `playlist_store` | CollectionStore | `data/playlists.json` | 存储歌单列表 |
| `player_store` | JSONStore | `data/player.json` | 存储播放器状态 |

**使用示例**：

```python
from backend.db import settings_store, playlist_store

settings = settings_store.read()
playlists = playlist_store.list()
```

### 4.3 数据模型

**文件**：[db/models.py](file:///e:/Code/gitRepo/SoulChord/SoulChord/backend/db/models.py)

#### 核心数据实体

##### Artist（歌手）

```python
class Artist(BaseModel):
    id: str           # 歌手 ID
    name: str         # 歌手名称
```

##### Album（专辑）

```python
class Album(BaseModel):
    id: str           # 专辑 ID
    name: str         # 专辑名称
```

##### Song（歌曲）

```python
class Song(BaseModel):
    id: str                  # 歌曲 ID
    name: str                # 歌曲名称
    artists: List[Artist]    # 歌手列表
    album: Album             # 专辑信息
    duration_ms: int         # 时长（毫秒）
    cover_url: Optional[str] # 封面图片 URL
```

##### Playlist（歌单）

```python
class Playlist(BaseModel):
    playlist_id: str        # 歌单 ID
    name: str               # 歌单名称
    source_url: str         # 导入来源链接
    song_count: int         # 歌曲数量
    created_at: int         # 创建时间戳（毫秒）
    songs: List[Song] = []  # 歌曲列表
```

##### UserProfits（用户画像）

```python
class UserProfits(BaseModel):
    nickname: str = "用户"              # 用户昵称
    avatar_url: Optional[str] = None    # 头像 URL
    favorite_genres: List[str] = []     # 最喜欢的流派
    favorite_artists: List[str] = []    # 最喜欢的音乐家
    music_preference_desc: str = ""     # 音乐偏好描述
    AI_conclustion: str = ""            # AI 一句话总结
    update_at: int = 0                  # 更新时间戳（毫秒）
```

##### Settings（设置）

```python
class Settings(BaseModel):
    llm_apikey: str = ""       # DeepSeek APIKey
    netease_apikey: str = ""   # 网易云 APIKey
```

##### NeteaseLoginStatus（网易云登录状态）

```python
class NeteaseLoginStatus(BaseModel):
    login_status: bool = False  # 登录状态
    nickname: str = ""          # 用户昵称
```

##### PlayerState（播放器状态）

```python
class PlayerState(BaseModel):
    current_song: Optional[Song] = None  # 当前播放歌曲
    play_url: Optional[str] = None       # 播放链接
    is_playing: bool = False             # 是否正在播放
    playlist: List[Song] = []            # 播放列表
    current_index: int = 0               # 当前播放索引
```

#### 请求体模型

##### ImportPlaylistRequest

```python
class ImportPlaylistRequest(BaseModel):
    playlist_url: str  # 网易云歌单分享链接
```

##### UpdatePlaylistRequest

```python
class UpdatePlaylistRequest(BaseModel):
    name: Optional[str] = None   # 歌单名称
    remark: Optional[str] = None # 歌单备注
```

##### UpdateUserBaseInfoRequest

```python
class UpdateUserBaseInfoRequest(BaseModel):
    nickname: Optional[str] = None    # 用户昵称
    avatar_url: Optional[str] = None  # 头像 URL
```

##### NeteaseLoginRequest

```python
class NeteaseLoginRequest(BaseModel):
    credential: str  # 登录凭证
```

## 5 启动方式

### 5.1 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 5.2 启动服务

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 5.3 运行测试

```bash
# 从项目根目录运行
python backend/test/run_tests.py    # API 接口测试
python backend/test/test_db.py       # 数据库操作测试
```

## 6 数据文件说明

所有数据存储在 `backend/data/` 目录下的 JSON 文件中：

| 文件 | 内容 | 结构类型 |
|------|------|----------|
| `settings.json` | API 密钥配置 | `{"llm_apikey": "", "netease_apikey": ""}` |
| `netease.json` | 网易云登录状态 | `{"login_status": false, "nickname": ""}` |
| `user_profile.json` | 用户画像 | UserProfits 结构 |
| `playlists.json` | 歌单列表 | `[Playlist, Playlist, ...]` |
| `player.json` | 播放器状态 | PlayerState 结构 |

> **注意**：`backend/data/` 目录已加入 `.gitignore`，不会被提交到版本控制。