## 🛠️ 给 Agent 侧的交付指引 (Tools 接入)

本项目不仅提供了 RESTful 接口，还包含了一层为 LLM 量身定制的 Tool 封装。负责开发 Agent 大脑的同学请遵循以下流程：

### 1. 引入工具箱

可以直接复制本项目中的 `agent_tools.py` 文件到你的 Agent 工程（如 `agent/tools/` 目录）下。该文件已经使用 `@tool` 装饰器对以下核心能力进行了封装，可直接注入给 LangChain/LangGraph：

- `search_songs(q, limit)`：精准搜歌
- `get_play_url(song_id)`：获取降级处理后的可播放流媒体 MP3 URL
- `recommend_scene(scene)`：基于场景/情绪的音乐推荐（支持 late_night, relax, workout 等）
- `report_playback(...)`：播放结束后的云端数据打卡

### 2. Base URL 配置

Agent 侧在发起 HTTP 模块调用时，请将底座 API 的基准地址设置为：

Python

```
API_BASE = "[http://127.0.0.1:8081/api/v1](http://127.0.0.1:8081/api/v1)"
```

### 3. 关于鉴权机制 (MVP 阶段)

当前系统处于 MVP（最小可行性产品）阶段。

- **自动匿名态**：服务在启动时会自动下发请求获取网易云的“匿名 Token”并在容器内缓存。
- **零配置**：Agent 在调用所有开放的 API 时，**无需**在 Header 中携带任何授权 Token 或 API-Key，即插即用。
- *(进阶：后续版本将解锁基于扫码的实名用户授权登录，以支持真实的红心歌单同步与日推千人千面)*

## 🛑 常用运维命令

**查看服务实时日志** (用于排查接口报错或网络连通性)：

Bash

```
docker-compose logs -f music-agent-api
```

**停止服务并释放网络/端口**：

Bash

```
docker-compose down
```