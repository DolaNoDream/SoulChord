# Agent ↔ 音乐 API 服务 接口契约（飞书模块）

> 版本：v1.0（首次发布，从原 `agent-music-api.md` v0.4 拆分而来）  
> 适用：Python Agent（LangGraph） ↔ Python 音乐 API 服务 · 飞书模块  
> 通道：HTTP REST  
> 架构总览：见 [`README.md`](./README.md)

---

## 0. 本模块职责边界

### 0.1 负责的事
- 飞书 **OAuth 2.0** 授权流程
- 用户日程**读取**（MVP 只读）
- `current_block` 计算（in_meeting / free / before_event / after_event / offline）
- 飞书官方端点适配

### 0.2 不负责的事
- ❌ **日程策略决策**（"会议中应该怎么做"）→ Agent（LangGraph）
- ❌ 日历事件**写入/修改/删除**（MVP 不开写权限）
- ❌ 用户画像、情绪记忆 → Agent Memory
- ❌ 网易云相关 → 音乐模块
- ❌ 语音合成 → 语音模块

### 0.3 未来可拆分
本模块后续可独立为 **Integration Service**，路径前缀 `/api/v1/integration/feishu/...`。  
当前 MVP 阶段位于 `music_api/integration/feishu/` 目录。

---

## 1. Tool 映射（飞书模块）

> 完整 Tool 列表见 [`README.md` §5](./README.md#5-tool-层完整列表)。

| Tool 名 | HTTP 接口 | 说明 |
|---|---|---|
| `get_calendar_today(date, timezone)` | `GET /feishu/calendar/today` | 今日所有日程 |
| `get_calendar_current()` | `GET /feishu/calendar/current` | 当前进行中 + 下一个日程 |
| `refresh_calendar()` | `POST /feishu/calendar/refresh` | 主动刷新缓存 |
| `get_feishu_status()` | `GET /feishu/status` | 连接状态 |

> Tool 代码组织在 Agent 端的 `agent/tools/feishu_tools.py`。

---

## 2. 通用约定

### 2.1 基础信息
- **音乐 API Base URL**：`http://localhost:8001`（开发期可配置）
- **路径前缀**：`/feishu/...`（注意：**不**带 `/api/v1/`，与音乐/语音模块分开便于权限隔离）
- **OAuth 回调端口**：`http://localhost:8765/feishu/cb`（Agent 本地起 HTTP server）
- **编码**：UTF-8
- **消息格式**：JSON

### 2.2 鉴权
- 模块内部：飞书 **user_access_token**（存于 `feishu_token.json`，见 §3.5）
- 对外暴露：本服务无鉴权（同机本地调用）

### 2.3 响应统一格式
```json
{
  "code": 0,
  "msg": "ok",
  "data": { ... }
}
```

### 2.4 错误码（飞书模块）
| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数错误 |
| 4003 | 资源不存在 |
| 4301 | 飞书 OAuth 未授权 / token 失效 |
| 4302 | 飞书日程读取失败 |
| 4303 | 飞书 refresh_token 也过期，需重新授权 |
| 4291 | 飞书 QPS 超限 |
| 5001 | 内部异常 |

> 跨模块错误码体系见 [`README.md` §4.4](./README.md#44-错误码体系跨模块)

---

## 3. OAuth 鉴权

### 3.1 桌面应用 Loopback 流程

```
┌────────┐  1.打开授权 URL   ┌──────┐  2.用户登录授权  ┌────────┐
│ 前端   │ ────────────────> │ 浏览器 │ ─────────────> │ 飞书   │
│        │ <──────────────── │      │ <───────────── │       │
└────────┘  4.回调带 code   └──────┘  3.重定向到     └────────┘
     │                            │      localhost
     │                            ▼
     │                     ┌──────────────┐
     │   5.后端自动          │ Agent 回调端  │
     └───────────────────> │ /feishu/cb    │
                           └──────┬───────┘
                                  │ 6.用 code 换 token
                                  ▼
                           ┌──────────────┐
                           │  飞书 OAuth   │
                           └──────┬───────┘
                                  │ 7.返回 access_token
                                  ▼
                           存储到 feishu_token.json
```

### 3.2 关键步骤

| 步骤 | Agent 行为 |
|---|---|
| 1. 启动授权 | `POST /feishu/oauth/start` → 返回飞书授权 URL |
| 2. 前端开浏览器 | 前端 Electron `shell.openExternal(auth_url)` |
| 3. 飞书回调 | Agent 本地起 HTTP server 监听 `http://localhost:8765/feishu/cb?code=xxx` |
| 4. 换 token | Agent 用 code 调 `POST https://open.feishu.cn/open-apis/authen/v2/oauth/token` |
| 5. 存 token | 写入 `data/feishu_token.json`（含 access_token + refresh_token + calendar_id）|
| 6. 自动刷新 | 每次调用飞书 API 前检查 expires_at，提前 5 分钟用 refresh_token 续期 |

### 3.3 OAuth Scope（已核对官方文档）

| 用途 | scope |
|---|---|
| **MVP 只读**（推荐） | `calendar:calendar:readonly` |
| 读写日历+日程 | `calendar:calendar` |
| 请假日程管理 | `calendar:timeoff`（不用）|

> MVP 申请 `calendar:calendar:readonly` 就够了，覆盖日历列表、日程查询、忙闲查询。

### 3.4 凭证类型选择

飞书 API 支持两种 token：

| token | 用途 | 是否需要用户授权 |
|---|---|---|
| `tenant_access_token` | 应用身份，访问应用自己的数据 | 否（app_id + app_secret 换）|
| `user_access_token` | 用户身份，访问用户的日历 | **是**（OAuth 流程）|

**AI DJ 必须用 `user_access_token`**，因为要看用户的日历。

### 3.5 Token 持久化

文件路径：`data/feishu_token.json`

```json
{
  "user_access_token": "u-xxx",
  "refresh_token": "ur-xxx",
  "expires_at": 1739274000000,
  "scope": "calendar:calendar:readonly",
  "user_open_id": "ou_xxx",
  "calendar_id": "cal_xxx",
  "updated_at": 1739270400000
}
```

> `calendar_id` 字段：飞书 API 查日程必须指定 calendar_id，所以授权完成后**立即**调一次 `POST /open-apis/calendar/v4/calendars/primary` 拿主日历 id 缓存起来。

---

## 4. OAuth + 连接状态接口

### 4.1 `POST /feishu/oauth/start`
**用途**：启动飞书 OAuth 授权流程，返回授权 URL 给前端

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

### 4.2 `GET /feishu/status`
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

未连接时：
```json
{
  "connected": false,
  "last_sync_at": null
}
```

---

### 4.3 `DELETE /feishu/disconnect`
**用途**：断开飞书授权，清除本地 token

**响应**：`{ "code": 0 }`

> 后端必须**彻底删除** `feishu_token.json` 文件，包括撤销日历缓存

---

## 5. 日程接口

### 5.1 `GET /feishu/calendar/today`
**用途**：获取今日所有日程（按时间排序）

**Query 参数**：
| 参数 | 必填 | 说明 |
|---|---|---|
| `date` | 否 | ISO 日期 `2026-07-11`，默认今天 |
| `timezone` | 否 | 默认 `Asia/Shanghai` |

**响应 data**：
```json
{
  "date": "2026-07-11",
  "events": [
    {
      "event_id": "evt_xxx",
      "summary": "周会",
      "description": "本周项目进度同步",
      "start_at": 1739274000000,
      "end_at": 1739277600000,
      "location": "会议室 A",
      "is_all_day": false,
      "status": "confirmed",
      "busy_status": "busy",
      "attendees_count": 5
    }
  ],
  "cached_at": 1739270000000,
  "is_stale": false
}
```

---

### 5.2 `GET /feishu/calendar/current`
**用途**：获取"当前进行中"和"下一个即将开始"的日程（Agent 决策用，最常调用）

**响应 data**：
```json
{
  "current_event": {
    "event_id": "evt_xxx",
    "summary": "周会",
    "start_at": 1739274000000,
    "end_at": 1739277600000,
    "minutes_remaining": 23,
    "busy_status": "busy",
    "location": "会议室 A"
  },
  "next_event": {
    "event_id": "evt_yyy",
    "summary": "代码评审",
    "start_at": 1739280000000,
    "minutes_until_start": 40,
    "busy_status": "busy"
  },
  "current_block": "in_meeting",
  "snapshot_at": 1739275800000
}
```

**`current_block` 枚举**（Agent 决策核心字段）：

| 值 | 含义 |
|---|---|
| `in_meeting` | 当前有会议/日程进行中 |
| `before_event` | 距下一个日程 < 15 分钟 |
| `after_event` | 刚结束日程 < 30 分钟 |
| `free` | 长时间（> 30 分钟）空闲 |
| `offline` | 飞书未连接 / token 失效 |

> Agent 拿到 `current_block` 后查表决定 DJ 策略（见 §9.0）

---

### 5.3 `POST /feishu/calendar/refresh`
**用途**：强制刷新日程缓存（正常情况 Agent 定时 5 分钟刷新，前端可触发）

**响应**：`{ "code": 0, "data": { "refreshed_at": 1739270000000 } }`

---

## 6. 飞书端点映射表（实现时对照）

> 本节是**实现细节**，给写代码的人对照。本文档定义的内部接口如何映射到飞书官方 API：

| 内部接口 | 飞书官方端点 | 说明 |
|---|---|---|
| `POST /feishu/oauth/start` | `https://open.feishu.cn/open-apis/authen/v2/index?app_id=...&redirect_uri=...&scope=calendar:calendar:readonly` | 拼授权 URL 返回前端 |
| `GET /feishu/status` | （本地读 `feishu_token.json`）| 不调飞书 |
| `GET /feishu/calendar/today` | `GET /open-apis/calendar/v4/calendars/{calendar_id}/events?start_time=...&end_time=...` | 时间范围限定今天 00:00-23:59 |
| `GET /feishu/calendar/current` | 同上 + 本地计算 `current_block` | 智能判断进行中/下一个 |
| `POST /feishu/calendar/refresh` | 同 `today` | 强制重新拉取并更新缓存 |
| `DELETE /feishu/disconnect` | （本地删 `feishu_token.json`）| 可选：调飞书 `revoke` 接口 |

**首次授权后额外调用**：
```
POST /open-apis/calendar/v4/calendars/primary
→ 拿到主日历 calendar_id，存到 feishu_token.json.calendar_id
```

---

## 7. 数据结构

### 7.1 CalendarEvent
```typescript
interface CalendarEvent {
  event_id: string;
  summary: string;
  description?: string;
  start_at: number;          // 毫秒时间戳
  end_at: number;
  location?: string;
  is_all_day: boolean;
  status: 'confirmed' | 'tentative' | 'cancelled';
  busy_status: 'busy' | 'free' | 'tentative';
  attendees_count?: number;
}
```

### 7.2 CurrentSnapshot
```typescript
interface CurrentSnapshot {
  current_event?: CalendarEvent;     // 当前进行中（可空）
  next_event?: CalendarEvent;        // 下一个即将开始（可空）
  current_block: 'in_meeting' | 'before_event' | 'after_event' | 'free' | 'offline';
  snapshot_at: number;
}
```

---

## 8. 隐私约束（重要！）

⚠️ **日程数据是高度敏感的隐私信息**，必须遵守：

1. **不发往 LLM**：日历内容（事件标题、地点、参与人）**不进入 DeepSeek 的 prompt**
   - Agent 内部把 `current_block`（如 `in_meeting`）这种**抽象标签**喂给 LLM
   - 具体事件细节留在本地规则引擎里判断
2. **不写 Memory**：日历原始数据不写入 `memory/*.json`（避免泄露）
   - 只写"用户在会议中"这种状态标签到 `context` category
3. **前端最小展示**：UI 上显示日程时**只显示摘要**，不展示参与人/详细描述
4. **断开即清除**：`DELETE /feishu/disconnect` 必须彻底删除 `feishu_token.json`

---

## 9. 设计目标：日历情境 → DJ 策略

Agent 通过读取用户的飞书日程，**感知用户当前/接下来在做什么**，从而采取不同的 DJ 策略：

| 日历情境 | DJ 策略 |
|---|---|
| 正在开会 | 静音 + 不说话 + 不切歌 |
| 会议前 10 分钟 | 切到轻量专注音乐 |
| 会议刚结束 | 主动关心 + 推荐恢复型音乐 |
| 通勤块（出行日程） | 节奏感音乐 + 适当问候 |
| 午餐/晚餐 | 轻松音乐 + 偶尔互动 |
| 自由块 | 按时间+情绪推荐 |
| 标记"勿扰" | 完全静默 |

---

## 10. MVP 范围

✅ 做：
- OAuth 授权连接
- 读取今日日程
- 计算 `current_block`
- Agent 根据 `current_block` 切换策略

❌ 不做：
- 写入/修改/删除日程（不开写权限）
- 重复日程解析（只处理单次事件）
- 跨日日程（如"明天 8 点"统一按 UTC 转换）
- 事件订阅 webhook（需要公网地址，桌面应用做不到）

---

## 11. 未来规划：事件订阅（Webhooks）

飞书支持日程变更主动推送：
- 端点：`POST /open-apis/calendar/v4/calendars/{calendar_id}/events/subscription`
- 飞书向我们的回调 URL 推送 `calendar.calendar.event.changed_v4` 事件

**当前无法使用的原因**：
- 桌面应用在 NAT 后，没有公网回调地址
- 飞书无法主动连到 `localhost:8765`

**未来解决方案**（任选其一）：
1. **云端中转**：自己起一个云服务（如 Vercel Function），桌面端连它，飞书推给它，它再推给桌面
2. **长轮询**：保留现在轮询方案但缩短到 1 分钟
3. **本地网络穿透**：用 ngrok / frp 暴露本地端口（不推荐，生产环境麻烦）

**MVP 决策**：保持 5 分钟轮询，足够"日程变化 → DJ 策略调整"这个用户感知频率。

---

## 12. 待定 / 后续补充

- [ ] 飞书 App ID / App Secret 申请（需要企业自建应用）
- [ ] 飞书日程刷新频率（默认 5 分钟）
- [ ] 事件订阅方案（见 §11）
- [ ] 多日历支持（当前只读主日历）
- [ ] 失败重试策略（token 刷新 + 接口调用）