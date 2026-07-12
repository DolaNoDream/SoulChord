# 🎵 Music Agent API Service

本项目为 LLM Agent（大模型智能体）提供标准化的网易云音乐能力聚合服务。
作为智能体的底层“工具库（Tools）”，本项目将复杂的第三方音乐 SDK 和网易云原生协议封装为标准的 RESTful 接口，供 Agent 的决策大脑（如基于 LangGraph/ReAct 架构）直接调用。

---

## 🏗️ 架构概览

本项目采用 Docker 容器化编排，包含两个核心微服务，两者在独立隔离的容器网络中无缝通信：
1. **Node.js 爬虫服务**：基于开源的 `binaryify/netease_cloud_music_api`，负责与网易云官方服务器进行最底层的协议交互。
2. **FastAPI 代理服务**：我们编写的核心业务网关，负责数据清洗、双层降级兜底、场景标签映射以及数据结构规范化。

---

## 🚀 快速启动 (一键部署)

本项目已全面容器化，部署方**无需**在本地配置 Python 或 Node.js 开发环境。

### 前置条件
- 确保系统已安装 **Docker** 与 **Docker Compose**。
- (Windows 用户) 请确保 Docker Desktop 处于 Running 状态。

### 启动命令
在本项目根目录下（即 `docker-compose.yml` 所在目录），打开终端执行：

```bash
docker-compose up -d --build
```
**⚠️ 端口映射说明 (必读)**：

为避免与 Windows 系统底层 Hyper-V / WinNAT 的保留端口（如 8001）发生冲突，我们在 `docker-compose.yml` 中将宿主机对外的端口映射为了 **`8081`**（即 `8081:8001`）。后续所有的本地访问均需通过 `8081` 端口。

## 📖 接口文档与联调调试

服务启动后，自带完善的交互式 API 调试面板：

- **健康检查**：[http://127.0.0.1:8081/api/v1/health](https://www.google.com/search?q=http://127.0.0.1:8081/api/v1/health) (查看底层依赖是否连通)
- **Swagger UI 接口面板**：👉 **[http://127.0.0.1:8081/docs](https://www.google.com/search?q=http://127.0.0.1:8081/docs)**
- **ReDoc 面板**：[http://127.0.0.1:8081/redoc](https://www.google.com/search?q=http://127.0.0.1:8081/redoc)