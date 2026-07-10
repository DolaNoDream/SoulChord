# SoulChord

> 你的专属 24 小时 AI 电台 —— 不只是音乐，更是陪你度过每一刻。

## 项目简介

SoulChord 是一款基于 AI Agent 的桌面音乐电台应用，模拟一位 24 小时在线的私人电台 DJ。与传统音乐播放器不同，SoulChord 的核心价值不在于"帮你找到歌"，而在于通过 AI DJ 的说话方式传递**陪伴感**——安静时默默播放，合适时说恰到好处的话，懂得什么时候陪伴、什么时候保持沉默。

---

## 前端技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **桌面框架** | Electron | PC 跨平台桌面应用，支持无边框、始终置顶、透明背景 |
| **UI 框架** | Vue 3 + TypeScript | 核心前端框架，组合式 API |
| **构建工具** | Vite | 极速 HMR 开发体验 |
| **状态管理** | Pinia | 全局状态管理（播放器、对话、用户画像） |
| **组件库** | Element Plus | 基础 UI 组件（按钮、对话框、表单等） |
| **音频播放** | Web Audio API | 音乐播放控制 |
| **动画** | CSS Animations / Live2D Cubism SDK | AI DJ 角色动画 |
| **打包分发** | electron-builder | 桌面应用打包 |

---

## 项目结构

```
SoulChord/
│
├── 📦 配置文件
│   ├── package.json              项目元数据：依赖列表、npm 脚本（dev/build/typecheck）
│   ├── package-lock.json          锁定依赖版本，确保团队安装一致
│   ├── tsconfig.json              TypeScript 主配置（Vue 源码）
│   ├── tsconfig.node.json         TypeScript 配置（Electron/Vite 构建工具）
│   ├── vite.config.ts             Vite 构建配置：Vue 插件、Electron 插件、路径别名、SCSS
│   ├── electron-builder.yml       Electron 打包配置（Windows/macOS/Linux 安装包）
│   ├── env.d.ts                   类型声明：Vue SFC 模块、ElectronAPI 接口
│   ├── index.html                 Vite 入口 HTML，浏览器加载的第一个页面
│   ├── .gitignore                 Git 忽略：node_modules、dist、dist-electron、.env 等
│   ├── .vscode/settings.json      VSCode 配置：使用项目中的 TypeScript SDK
│   └── README.md                  项目说明文档
│
├── ⚡ Electron 主进程
│   └── electron/
│       ├── main.ts                创建桌面窗口（无边框+透明+置顶）、系统托盘、迷你模式
│       └── preload.ts             安全桥梁：暴露 electronAPI 给 Vue 页面（窗口控制、IPC）
│
└── 🖥️ Vue 应用 (src/)
    ├── main.ts                    Vue 应用启动：挂载 Pinia、Router、ElementPlus
    ├── App.vue                    根组件：标题栏、路由出口、底部导航栏、迷你悬浮窗
    │
    ├── types/                     🧩 类型定义
    │   ├── music.ts               歌曲 Song、歌单 Playlist、播放模式、情绪 EmotionType
    │   ├── chat.ts                AI 对话 ChatMessage、快捷场景 QuickScene、附件类型
    │   └── user.ts                用户 UserProfile、音乐DNA、风格偏好
    │
    ├── stores/                    🗄️ 状态管理 (Pinia)
    │   ├── player.ts              播放器：当前歌曲、队列、音量、进度、播放模式
    │   ├── chat.ts                AI 对话：消息列表、流式输出中状态、快捷场景
    │   ├── user.ts                用户：音乐DNA、听歌历史、引导状态
    │   └── settings.ts            设置：主题、窗口模式、始终置顶、语言
    │
    ├── api/                       🌐 API 请求层
    │   ├── agent.ts               与后端 FastAPI Agent 通信（聊天、推荐、画像分析）
    │   └── music.ts               音乐 API（搜索、歌单）+ Mock 模拟数据（后端不可用时）
    │
    ├── composables/               🔧 组合式函数
    │   ├── useAudio.ts            音频引擎：HTMLAudioElement 封装，与 PlayerStore 同步
    │   ├── useChat.ts             对话逻辑：发送消息、流式接收、场景触发
    │   └── useElectron.ts         Electron API 封装：窗口控制、媒体会话
    │
    ├── components/                🎨 UI 组件
    │   ├── MusicPlayer.vue        完整播放器：封面、进度条、播放/暂停/上下首、音量
    │   ├── SongCard.vue           歌曲卡片：封面、歌名、情绪标签、AI 推荐理由
    │   ├── Playlist.vue           播放列表：当前播放、等待队列、清空
    │   ├── ChatBubble.vue         对话气泡：用户/AI 消息、流式动画、内嵌歌曲推荐
    │   └── MiniWindow.vue         迷你悬浮窗：紧凑播放条、拖拽、展开按钮
    │
    ├── views/                     📄 页面视图
    │   ├── HomeView.vue           首页：播放器 + 今日推荐歌单 + 播放队列
    │   ├── ChatView.vue           AI DJ 对话页：消息列表、输入框、快捷场景按钮
    │   └── ProfileView.vue        个人页：音乐DNA可视化、风格/艺人偏好
    │
    ├── router/                    🧭 路由
    │   └── index.ts               路由表：/ → 首页、/chat → AI DJ、/profile → 我的
    │
    └── assets/styles/             🎨 样式
        ├── variables.scss         设计系统：暗色主题颜色、字体、圆角、阴影
        └── global.scss            全局样式：CSS Reset、滚动条、Element Plus 主题覆盖
```

---

## 前端功能清单

### MVP 核心功能（第一版）

#### 1. 基础音乐播放器
- [ ] 播放 / 暂停 / 上一首 / 下一首
- [ ] 快进 / 快退
- [ ] 音量调节
- [ ] 播放进度条
- [ ] 播放模式切换（顺序、随机、单曲循环）
- [ ] 当前歌曲信息展示（封面、歌名、歌手）

#### 2. AI DJ 对话窗口
- [ ] 聊天界面（消息气泡列表）
- [ ] 用户文字输入
- [ ] AI 回复展示（推荐歌曲卡片 + 推荐理由 + DJ 口播文案）
- [ ] 对话历史记录
- [ ] 快捷场景入口（"有点累"、"需要专注"、"想放松"等预设）

#### 3. 今日推荐 / 情境歌单
- [ ] 根据时间 + 场景自动生成推荐歌单
- [ ] 歌曲卡片列表（封面、歌名、推荐理由）
- [ ] 一键播放全部

#### 4. 用户音乐画像
- [ ] "音乐 DNA" 可视化展示
- [ ] 喜欢的风格 / 艺人 / 年代 / 情绪偏好
- [ ] 从喜欢的歌曲列表导入后自动分析

#### 5. 桌面悬浮窗
- [ ] 无边框窗口 + 透明背景
- [ ] 始终置顶
- [ ] 迷你模式 / 完整模式切换
- [ ] 拖拽移动窗口
- [ ] 系统托盘驻留

### 进阶功能（后续迭代）

#### 6. Live2D AI DJ 角色
- [ ] AI DJ 虚拟形象集成
- [ ] 根据音乐情绪和对话内容展示不同表情动作
- [ ] 说话时嘴部动画同步

#### 7. 语音交互
- [ ] 语音输入 → Whisper 识别 → 发送给 Agent
- [ ] TTS 语音合成播放（AI DJ 口播）

#### 8. 多模态感知
- [ ] 情绪表情拍照输入
- [ ] 当前天气 / 时间 / 位置展示

#### 9. 长期记忆可视化
- [ ] 听歌历史时间线
- [ ] "年度音乐记忆地图" 可视化报告

---

## 前后端通信架构

```
┌─────────────────────────────────────────┐
│           Electron 桌面应用              │
│  ┌───────────────────────────────────┐  │
│  │        Vue3 渲染进程               │  │
│  │   • 播放器 UI                     │  │
│  │   • AI 对话界面                   │  │
│  │   • 歌单展示                      │  │
│  └──────────┬────────────────────────┘  │
│             │ HTTP / WebSocket           │
│  ┌──────────▼────────────────────────┐  │
│  │    Python FastAPI (本地 Agent)     │  │
│  │   • LangChain/LangGraph Agent     │  │
│  │   • LLM 调用 (DeepSeek)           │  │
│  │   • SQLite 记忆存储               │  │
│  │   • TTS 语音合成                  │  │
│  │   • 音乐 API 代理                 │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 设计原则

- **AI 不要过于主动** — 最好的电台 DJ 大部分时间保持安静，偶尔说合适的话
- **陪伴感优先于推荐精准度** — 核心价值在于 DJ 说话方式传递的陪伴感
- **交互比例 9:0.8:0.2** — 90% 安静播放 + 8% 简单交互 + 2% 深度对话
- **温暖的 UI 氛围** — 暗色主题为主，适合深夜场景

---

## 新电脑上如何运行（从零开始）

### 1. 安装 Node.js

项目需要 Node.js **v18 或更高版本**。

下载地址：https://nodejs.org/zh-cn

安装完成后，打开终端（PowerShell 或 CMD）验证：

```bash
node --version   # 应显示 v18.x 或更高
npm --version    # 应显示 9.x 或更高
```

### 2. 克隆项目

```bash
git clone https://github.com/DolaNoDream/SoulChord.git
cd SoulChord
git checkout front     # 切换到前端分支
```

> 如果已经拿到项目文件夹，跳过此步，直接在文件夹内打开终端即可。

### 3. 安装依赖

```bash
# 使用国内镜像（推荐，下载更快）
npm install --registry https://registry.npmmirror.com
```

这会安装 `package.json` 中列出的所有依赖，包括 Vue、Element Plus、Vite 等。安装后项目根目录会出现 `node_modules/` 文件夹。

### 4. 安装 Electron（可选，仅桌面模式需要）

Electron 二进制文件约 100MB，从 GitHub 下载较慢。**如果只需要在浏览器中开发调试，可以跳过此步。**

```bash
# Windows CMD 设置镜像后安装
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
npm install electron

# 或使用 PowerShell
$env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
npm install electron
```

### 5. 启动项目

```bash
# Web 开发模式（推荐，不需要 Electron）
npm run dev
```

终端会显示：
```
VITE v6.x  ready in xxx ms
➜  Local:   http://localhost:5173/
```

浏览器打开 **`http://localhost:5173/`** 即可看到 SoulChord 界面。修改代码后页面会自动刷新。

### 6. 其他常用命令

```bash
npm run dev          # 启动 Electron 桌面模式（会弹出桌面窗口）
npm run dev:web      # 启动纯 Web 模式（浏览器打开，不弹窗）★ 后端联调时用这个
npm run build        # 构建生产版本（输出到 dist/ 和 dist-electron/）
npm run typecheck    # TypeScript 类型检查
npm run preview      # 预览构建后的生产版本
```

### 7. VSCode 插件（建议安装）

| 插件 | 用途 |
|------|------|
| **Vue - Official** | Vue 3 语法高亮、类型提示、模板智能补全 |
| **TypeScript** | TS 类型检查 |


## 项目依赖一览

| 依赖 | 说明 | 安装方式 |
|------|------|---------|
| **Node.js v18+** | JS 运行时 | 官网下载安装 |
| **Vue / Vite / Pinia / Element Plus 等** | 前端框架和组件库 | `npm install` 自动安装 |
| **Electron** | 桌面壳（可选，约 100MB） | 见第 4 步 |
| **Python FastAPI** | 后端 AI Agent 服务 | 后端项目独立部署，默认 `http://localhost:8000` |

