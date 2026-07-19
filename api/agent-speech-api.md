# Agent ↔ 音乐 API 服务 接口契约（语音模块）

> 版本：v1.0（首次发布，从原 `agent-music-api.md` v0.4 拆分而来）  
> 适用：Python Agent（LangGraph） ↔ Python 音乐 API 服务 · 语音模块  
> 通道：HTTP REST  
> 架构总览：见 [`README.md`](./README.md)

---

## 0. 本模块职责边界

### 0.1 负责的事
- 讯飞 **TTS**（文字转语音）合成
- 讯飞 **ASR**（语音转文字）识别
- 音色列表管理（前端展示 + Agent 选择）

### 0.2 不负责的事
- ❌ 文案生成（DJ 说什么）→ Agent（DeepSeek LLM）
- ❌ 用户画像、情绪记忆 → Agent Memory
- ❌ 网易云相关 → 音乐模块
- ❌ 飞书相关 → 飞书模块

### 0.3 未来可拆分
本模块后续可独立为 **Speech Service**，路径前缀 `/api/v1/speech/...`。  
当前 MVP 阶段位于 `music_api/speech/` 目录。

---

## 1. Tool 映射（语音模块）

> 完整 Tool 列表见 [`README.md` §5](./README.md#5-tool-层完整列表)。

| Tool 名 | HTTP 接口 | 说明 |
|---|---|---|
| `tts_synthesize(text, voice, speed, volume)` | `POST /api/v1/tts/synthesize` | TTS 合成 |
| `get_voices()` | `GET /api/v1/tts/voices` | 音色列表 |
| `asr_recognize(audio_bytes, format)` | `POST /api/v1/asr/recognize` | ASR 识别 |

> Tool 代码组织在 Agent 端的 `agent/tools/speech_tools.py`。

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

### 2.4 错误码（语音模块）
| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数错误 |
| 4003 | 资源不存在 |
| 4201 | 讯飞 TTS 合成失败 |
| 4202 | 讯飞 ASR 识别失败 |
| 4291 | 讯飞 QPS 超限 |
| 5001 | 内部异常 |

> 跨模块错误码体系见 [`README.md` §4.4](./README.md#44-错误码体系跨模块)

---

## 3. TTS（文字转语音）

### 3.1 `POST /api/v1/tts/synthesize`
**用途**：讯飞 TTS 合成（DJ 主动说话、回应用户、播报歌曲信息）

**请求 body**：
```json
{
  "text": "晚上好，今天是不是又忙了一天？",
  "voice": "male_gentle",
  "speed": 1.0,
  "volume": 50
}
```

请求字段：
| 字段 | 必填 | 说明 |
|---|---|---|
| `text` | 是 | 待合成文本，长度 ≤ 1000 字符 |
| `voice` | 是 | 音色 key（见 §3.2） |
| `speed` | 否 | 语速倍率，默认 1.0，范围 0.5-2.0 |
| `volume` | 否 | 音量，默认 50，范围 0-100 |

**响应 data**：
```json
{
  "audio_url": "http://localhost:8001/media/tts/20260711_xxx.mp3",
  "duration_ms": 4500,
  "text_length": 18,
  "voice": "male_gentle"
}
```

**实现细节**：
- 合成后保存为本地 mp3 文件（`media/tts/{时间戳}_{hash}.mp3`）
- 文件 URL 通过 `http://localhost:8001/media/...` 暴露
- **同一文本 + 同一音色**的请求，缓存 24 小时复用

**降级策略**：
- 讯飞 TTS 失败 → 返回 4201
- Agent 决定是否降级为"只显示文字不播语音"

---

### 3.2 `GET /api/v1/tts/voices`
**用途**：获取可用音色列表（前端在设置面板展示）

**响应 data**：
```json
{
  "voices": [
    {"key": "male_gentle", "name": "男声·温柔", "gender": "male", "style": "gentle"},
    {"key": "female_warm", "name": "女声·温暖", "gender": "female", "style": "warm"},
    {"key": "male_late_night", "name": "男声·深夜主播", "gender": "male", "style": "gentle"}
  ]
}
```

音色字段：
| 字段 | 说明 |
|---|---|
| `key` | 音色唯一标识，传给 `tts_synthesize` 的 `voice` 字段 |
| `name` | 中文展示名 |
| `gender` | `male` / `female` |
| `style` | 风格（`gentle` / `warm` / `lively` 等）|

**已知音色枚举**（待与讯飞对接后补全）：

| key | name | 默认人格 |
|---|---|---|
| `male_gentle` | 男声·温柔 | `night_dj` |
| `female_warm` | 女声·温暖 | `warm_companion` |
| `male_late_night` | 男声·深夜主播 | `night_dj` |
| `male_lively` | 男声·活力 | `energetic_jockey` |

> 新增音色时只追加枚举，接口字段不变。

---

## 4. ASR（语音转文字）

### 4.1 `POST /api/v1/asr/recognize`
**用途**：语音识别（前端录音后识别为文字）

**请求**：multipart/form-data

| 字段 | 说明 |
|---|---|
| `audio` | 音频文件（wav/pcm，16k 采样率，单声道）|
| `format` | `wav` / `pcm` |

**响应 data**：
```json
{
  "text": "今天有点累",
  "confidence": 0.95,
  "duration_ms": 2400
}
```

响应字段：
| 字段 | 说明 |
|---|---|
| `text` | 识别出的文字 |
| `confidence` | 置信度 0-1 |
| `duration_ms` | 音频时长（毫秒）|

**实现细节**：
- 音频大小上限 10MB
- 时长上限 60 秒
- 超过限制返回 4001

**降级策略**：
- 讯飞 ASR 失败 → 返回 4202
- 前端可降级为"显示文字输入框"

---

## 5. 通用接口

### 5.1 `GET /api/v1/health`
**用途**：健康检查

**响应 data**：
```json
{
  "status": "ok",
  "xfyun": {"available": true}
}
```

---

## 6. 数据结构

### 6.1 Voice
```typescript
interface Voice {
  key: string;            // 音色唯一标识
  name: string;           // 中文展示名
  gender: 'male' | 'female';
  style: string;          // 风格描述
}
```

### 6.2 TTSResult
```typescript
interface TTSResult {
  audio_url: string;
  duration_ms: number;
  text_length: number;
  voice: string;
}
```

### 6.3 ASRResult
```typescript
interface ASRResult {
  text: string;
  confidence: number;
  duration_ms: number;
}
```

---

## 7. 待定 / 后续补充

- [ ] 讯飞 API key 申请
- [ ] TTS 音频格式（mp3 / wav / pcm）
- [ ] TTS 缓存策略（同文本 24 小时复用）
- [ ] 失败重试策略（带退避）
- [ ] ASR 静音检测（避免无效识别）
- [ ] 长音频识别（> 60 秒分段处理）