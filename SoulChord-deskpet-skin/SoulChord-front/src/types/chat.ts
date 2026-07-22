/** AI 对话 / WebSocket 消息相关类型定义（v1.1 — 对齐 frontend-agent-api.md） */

import type { Song } from './music'

// ===== WS 统一消息信封 =====

/** WS 消息类型（对齐文档 2.1 消息 type 枚举） */
export type WsMessageType =
  | 'chat'       // AI聊天交互
  | 'music'      // 音乐控制
  | 'status'     // 系统状态
  | 'error'      // 错误
  | 'heartbeat'  // 心跳
  | 'dj'         // AI DJ 话术
  | 'tts'        // TTS 语音合成

/** WS 消息统一格式 */
export interface WsMessage<T = unknown> {
  type: WsMessageType
  subtype?: string
  id?: string               // 请求-响应匹配用
  ts?: number               // 毫秒时间戳
  payload: T
}

// ===== 对话消息（对齐文档 2.2、2.3） =====

/** 用户文本输入（chat.user_text） */
export interface ChatUserTextPayload {
  text: string
}

/** 语音识别文本输入（chat.voice_text） */
export interface ChatVoiceTextPayload {
  text: string
  confidence: number   // ASR 识别置信度 0-1
}

/** Agent 回复（chat.reply — 对齐文档 2.3.1 三段核心数据） */
export interface ChatReplyPayload {
  text: string          // AI回复文案/歌曲介绍文字
  url: string           // 歌曲播放链接/歌曲封面资源地址
  operation: OperationType  // 后端下发操作指令
  intent?: IntentType   // 后端识别的意图类型
}

/** AI DJ 话术（dj.speech — 主持人过渡语） */
export interface DjSpeechPayload {
  text: string
  audio_url?: string
  audio_duration_ms?: number
  mood?: string
}

/** TTS 语音合成（tts.synthesize — DJ 语音播报） */
export interface TtsSynthesizePayload {
  text: string
  audio_url: string
  audio_duration_ms: number
  voice: string
  expression: string
  mood?: string
  theme?: string
}

/** 操作指令标识（对齐文档 3.3 节） */
export type OperationType =
  | 'recommend'       // 推荐歌曲，展示推荐列表
  | 'play_song'       // 自动播放指定歌曲
  | 'skip_song'       // 执行切歌
  | 'add_playlist'    // 将歌曲加入播放队列
  | 'song_intro'      // 仅展示歌曲介绍，无播放动作

/** 意图类型 */
export type IntentType =
  | 'music_recommend'
  | 'chat'
  | 'song_info'
  | 'playlist_operate'

// ===== 快捷场景 =====

export interface QuickScene {
  id: string              // 场景 ID
  label: string           // 按钮文字
  icon: string            // 图标名
  promptTemplate: string  // 预设提问
  scenario: string        // 关联场景
}

// ===== 对话会话 =====

export interface ConversationSession {
  id: string
  startedAt: string
  lastMessageAt: string
  messageCount: number
  summary: string
}

/** 前端 UI 中使用的消息（对齐文档 3.3 后端返回数据处理规则） */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  attachments?: ChatAttachment[]
  isStreaming?: boolean
  // chat.reply 扩展字段
  url?: string
  operation?: OperationType
  intent?: IntentType
}

export type ChatAttachment =
  | { type: 'song'; song: Song; reason: string }
  | { type: 'playlist'; songs: Song[]; reason: string }
  | { type: 'image'; url: string; caption: string }
