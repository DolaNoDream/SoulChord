# SoulChord

> 本地 AI 音乐推荐客户端 —— 基于 AI Agent 的桌面音乐应用，支持歌单管理、AI 画像分析、智能对话与本地音乐播放。

## 项目简介

SoulChord 是一款基于 AI Agent 的桌面音乐应用，围绕五大核心能力设计：

1. **账号配置** — LLM API Key + 网易云 API Key 管理，网易云账号登录
2. **歌单管理** — 网易云歌单链接导入、本地 CRUD、歌曲预览
3. **AI 用户画像** — AI 自动分析听歌偏好，生成完整音乐画像（喜爱曲风/歌手/排斥曲风）
4. **AI 对话交互** — WebSocket 实时双向通信，统一 `chat.reply` 三段式返回（text/url/operation）
5. **本地音乐播放器** — 播放/暂停/切歌/进度/音量/播放模式/喜欢反馈

**核心约束**：本项目无虚拟桌宠、DJ 角色、TTS 语音播报、Live2D 动画功能。

---

## 前端技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **桌面框架** | Electron | PC 跨平台桌面应用，支持无边框、始终置顶 |
| **UI 框架** | Vue 3 + TypeScript | 核心前端框架，组合式 API |
| **构建工具** | Vite | 极速 HMR 开发体验 |
| **状态管理** | Pinia | 全局状态管理（播放器、对话、用户画像、设置、歌单） |
| **组件库** | Element Plus | 基础 UI 组件（开关、对话框、消息提示等） |
| **通信** | WebSocket（主）+ HTTP（补充） | 实时双向通信 |
| **音频播放** | HTMLAudioElement | 音乐播放控制 |
| **打包分发** | electron-builder | 桌面应用打包 |
| **接口规范** | V1.1 前端设计文档 + API 契约文档 | 前后端对接依据 |

---

## 项目结构

```
SoulChord/
├── 📦 配置文件
│   ├── package.json              # 项目元数据、依赖、npm 脚本
│   ├── tsconfig.json             # TypeScript 主配置
│   ├── tsconfig.node.json        # TypeScript 配置（Electron/Vite）
│   ├── vite.config.ts            # Vite 构建配置
│   ├── vite.web.config.ts        # 纯 Web 模式构建配置
│   ├── electron-builder.yml      # Electron 打包配置
│   ├── env.d.ts                  # 类型声明（Vue SFC、ElectronAPI）
│   ├── index.html                # Vite 入口 HTML
│   └── .gitignore
│
├── ⚡ Electron 主进程
│   └── electron/
│       ├── main.ts               # 桌面窗口（无边框+置顶）、系统托盘
│       └── preload.ts            # 安全桥梁：暴露 electronAPI
│
└── 🖥️ Vue 应用 (src/)
    ├── main.ts                   # Vue 启动：挂载 Pinia、Router、ElementPlus
    ├── App.vue                   # 根组件：标题栏、路由出口、设置入口
    │
    ├── types/                    # 🧩 类型定义
    │   ├── music.ts              # Song、Playlist、Artist、Album、SongFeedback
    │   ├── chat.ts               # ChatMessage、ChatReplyPayload（text/url/operation）
    │   └── user.ts               # UserProfits、AgentInfo
    │
    ├── stores/                   # 🗄️ 状态管理 (Pinia)
    │   ├── player.ts             # 播放器状态：当前歌曲、队列、音量、进度
    │   ├── chat.ts               # AI 对话：消息列表、快捷场景
    │   ├── user.ts               # 用户画像：UserProfits、AI 分析触发
    │   ├── settings.ts           # 设置：LLM/网易云 Key、网易云登录状态
    │   └── playlist.ts           # 歌单管理：导入、CRUD、自动触发画像分析
    │
    ├── api/                      # 🌐 API 请求层
    │   └── agent.ts              # HTTP 接口（20+ 端点）+ WebSocket 连接工厂 + 错误码
    │
    ├── composables/              # 🔧 组合式函数
    │   ├── useAudio.ts           # 音频引擎封装
    │   ├── useChat.ts            # 对话逻辑
    │   ├── useElectron.ts        # Electron API 封装
    │   └── useWebSocket.ts       # WebSocket 连接管理、消息分发
    │
    ├── components/               # 🎨 UI 组件
    │   ├── MusicPlayer.vue       # 完整播放器（封面/进度/控制/喜欢）
    │   ├── SongCard.vue          # 歌曲卡片
    │   ├── Playlist.vue          # 播放队列列表
    │   ├── PlaylistPanel.vue     # 歌单管理面板（导入/CRUD）
    │   ├── UserProfilePanel.vue  # 用户画像面板（AI生成字段只读）
    │   ├── ChatBubble.vue        # 对话气泡（支持 operation 标签）
    │   ├── MiniWindow.vue        # 迷你悬浮窗
    │   ├── SettingsDrawer.vue    # 设置面板（Key配置/网易云登录/用户信息）
    │   └── HistoryPanel.vue      # 播放历史记录
    │
    ├── views/                    # 📄 页面视图
    │   └── DashboardView.vue     # 主界面：Tab切换（对话/歌单/画像）
    │
    ├── utils/                    # 🛠️ 工具
    │   └── errorCodes.ts         # 错误码映射与判断函数
    │
    ├── router/                   # 🧭 路由
    │   └── index.ts              # 路由表
    │
    └── assets/styles/            # 🎨 样式
        ├── variables.scss        # 设计系统（暗色主题变量）
        └── global.scss           # 全局样式 + Element Plus 主题覆盖
```

---

## 功能清单

### ✅ 已实现

#### 系统设置
- [x] LLM API Key 配置（输入/隐藏/保存）
- [x] 网易云 API Key 配置
- [x] 网易云账号登录状态展示
- [x] 用户头像/昵称编辑
- [x] 窗口始终置顶切换

#### 歌单管理
- [x] 网易云歌单链接导入
- [x] 本地歌单列表展示（名称/歌曲数/日期）
- [x] 歌单重命名
- [x] 歌单删除（自动触发 AI 画像分析）
- [x] 歌单内歌曲预览

#### AI 用户画像
- [x] AI 自动生成音乐偏好画像展示（只读）
- [x] 喜爱曲风 / 喜爱歌手 / 排斥曲风
- [x] 音乐偏好描述 + AI 一句话总结
- [x] 画像最后更新时间
- [x] 手动触发重新分析画像
- [x] 导入/删除歌单后自动触发分析

#### AI 对话交互
- [x] WebSocket 实时双向通信
- [x] 文本消息发送（chat.user_text）
- [x] 语音转文字消息格式支持（chat.voice_text）
- [x] AI 回复三段式处理（text/url/operation）
- [x] 操作指令：recommend / play_song / skip_song / add_playlist / song_intro
- [x] 快捷场景按钮（6 个预设场景）
- [x] 30s 心跳保活 + 断线自动重连
- [x] 错误消息实时推送展示

#### 本地音乐播放器
- [x] 播放/暂停/上一首/下一首
- [x] 进度条拖拽跳转
- [x] 音量调节 + 静音
- [x] 播放模式切换（顺序/随机/单曲循环）
- [x] 歌曲封面 + 歌名/艺人展示
- [x] 喜欢/不喜欢反馈
- [x] 播放列表管理（清空/队列）
- [x] 播放状态上报（play_start/end/pause/resume）

#### 其他
- [x] Electron 桌面窗口（无边框/置顶/托盘）
- [x] 播放历史记录查询
- [x] 快捷场景按钮
- [x] 迷你悬浮窗
- [x] 媒体会话 API（OS 媒体控件集成）
- [x] 暗色主题设计系统

### ❌ 未实现（依赖后端）

| 功能 | 原因 |
|------|------|
| 网易云扫码/验证码实际登录 | 依赖后端完成网易云登录凭证签发逻辑 |
| 歌单导入后自动获取歌曲详情 | 后端 POST /api/playlist/import 拉取并存储 |
| AI 画像实际分析执行 | 后端 POST /api/user/analyze 调用 LLM 分析 |
| 歌曲播放 URL 资源获取 | 后端 music.play 消息下发播放链接 |
| 麦克风语音采集 + ASR | 前端不内置 ASR 引擎，语音识别由后端处理 |

---

## 前后端通信架构

```
┌──────────────────────────────────────────────┐
│              Electron 桌面应用                │
│  ┌──────────────────────────────────────┐   │
│  │          Vue3 渲染进程                 │   │
│  │   • 播放器 UI                         │   │
│  │   • AI 对话界面                        │   │
│  │   • 歌单管理 / 用户画像面板             │   │
│  │   • 设置面板                           │   │
│  └───────┬──────────────────────────────┘   │
│          │                                   │
│          │ WebSocket（主通道）                │
│          │ ws://localhost:8000/ws/client     │
│          │ • chat.user_text / chat.reply    │
│          │ • music.play / pause / skip      │
│          │ • status.player_event            │
│          │ • heartbeat ping/pong            │
│          │                                   │
│          │ HTTP（配置/查询通道）              │
│          │ http://localhost:8000/api/        │
│          │ • GET  /init                     │
│          │ • GET/PUT /settings              │
│          │ • POST /netease/login            │
│          │ • GET  /netease/status           │
│          │ • POST /playlist/import          │
│          │ • GET  /playlist/list            │
│          │ • GET/PUT/DELETE /playlist/{id}  │
│          │ • POST /user/analyze             │
│          │ • GET  /user/profile             │
│          │ • PUT  /user/baseinfo            │
│          │ • POST /feedback                 │
│          │ • GET  /history/songs            │
│          │                                   │
│  ┌───────▼──────────────────────────────┐   │
│  │      Python FastAPI (本地 Agent)      │   │
│  │   • LLM 调用 (DeepSeek)              │   │
│  │   • 网易云音乐 API 代理               │   │
│  │   • SQLite 数据持久化                 │   │
│  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

---

## 如何运行

### 1. 环境要求
- Node.js v18+
- 后端 Python FastAPI 服务运行于 `http://localhost:8000`

### 2. 安装依赖
```bash
npm install --registry https://registry.npmmirror.com
```

### 3. 启动开发
```bash
# 纯 Web 模式（推荐，浏览器打开，不需要 Electron）
npm run dev:web

# Electron 桌面模式
npm run dev
```

浏览器打开 `http://localhost:5173/`，自动连接后端 WebSocket `ws://localhost:8000/ws/client`。

### 4. 常用命令
```bash
npm run dev:web      # 纯 Web 模式 ★ 后端联调用这个
npm run dev          # Electron 桌面模式
npm run build        # 构建生产版本
npm run typecheck    # TypeScript 类型检查
```

---

## HTTP 接口速查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/init` | 启动初始化，拉取全量数据 |
| GET | `/api/settings` | 获取 API Key 配置 |
| PUT | `/api/settings` | 更新 API Key（`llm_apikey`, `netease_apikey`） |
| POST | `/api/netease/login` | 网易云账号登录（`type`: qr/sms, `token`） |
| GET | `/api/netease/status` | 查询网易云登录状态 |
| POST | `/api/playlist/import` | 导入歌单（`playlist_url`） |
| GET | `/api/playlist/list` | 本地歌单列表 |
| GET | `/api/playlist/{id}` | 歌单详情 + 歌曲列表 |
| PUT | `/api/playlist/{id}` | 修改歌单名称/备注 |
| DELETE | `/api/playlist/{id}` | 删除歌单 |
| POST | `/api/user/analyze` | 手动触发 AI 画像分析 |
| GET | `/api/user/profile` | 查询用户完整画像 |
| PUT | `/api/user/baseinfo` | 修改昵称/头像 |
| POST | `/api/feedback` | 歌曲反馈（like/dislike/favorite/skip） |
| GET | `/api/history/songs` | 播放历史记录 |

所有 HTTP 响应统一格式：`{ code: 0, msg: "ok", data: {} }`，`code=0` 为成功。

### 通用错误码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1001 | 参数错误 |
| 1002 | APIKey未配置 / 网易云账号未登录 |
| 1003 | 歌单/歌曲资源不存在 |
| 2001 | LLM大模型调用失败 |
| 2002 | 工具调用失败 |
| 2003 | 请求超时 |
| 3001 | 网易云音乐服务不可用 |
| 3002 | 网易云接口请求异常 |
| 9999 | 服务内部异常 |

---

## WebSocket 消息速查

### 前端 → 服务端

| type | subtype | 说明 |
|------|---------|------|
| `chat` | `user_text` | 用户文本输入（`payload.text`） |
| `chat` | `voice_text` | 语音识别文本（`payload.text` + `confidence`） |
| `status` | `player_event` | 播放状态上报（`payload.event`） |
| `heartbeat` | `ping` | 心跳保活（30s） |

### 服务端 → 前端

| type | subtype | 说明 |
|------|---------|------|
| `chat` | `reply` | AI 回复（`text` + `url` + `operation`） |
| `music` | `play` | 播放歌曲（`song` + `play_url`） |
| `music` | `pause` | 暂停 |
| `music` | `resume` | 恢复播放 |
| `music` | `skip` | 切歌 |
| `music` | `update_playlist` | 更新播放列表 |
| `status` | `welcome` | 连接欢迎（`session_id`） |
| `error` | — | 错误推送（`code` + `msg`） |
| `heartbeat` | `pong` | 心跳响应 |

### 消息格式

所有 WS 消息统一 JSON 结构：
```json
{
  "type": "chat",
  "subtype": "user_text",
  "id": "uuid",
  "ts": 1739270400000,
  "payload": {}
}
```

---

## 设计原则

- **五大核心能力** — 账号配置、歌单管理、AI 画像、AI 对话、音乐播放
- **HTTP + WebSocket 混合通信** — 配置/查询用 HTTP，实时交互用 WebSocket
- **AI 画像仅自动生成** — 音乐偏好由 AI 分析产生，前端不做手动编辑入口
- **统一 chat.reply 三段式返回** — text（文案）/ url（资源链接）/ operation（操作指令）
- **温暖的暗色主题** — 适合长时间使用的深色 UI

---

## 前端依赖一览

| 依赖 | 说明 |
|------|------|
| **Node.js v18+** | JS 运行时 |
| **Vue 3 + Vite + Pinia** | 前端框架 |
| **Element Plus** | UI 组件库 |
| **Electron** | 桌面壳（可选，约 100MB） |
| **Python FastAPI** | 后端 AI Agent 服务，默认 `http://localhost:8000` |
