/** AI 对话 / WebSocket 消息相关类型定义（v0.3） */

import type { Song } from './music'

// ===== WS 统一消息信封 =====

/** WS 消息类型（7 种枚举） */
export type WsMessageType =
  | 'chat'       // 对话
  | 'tool_call'  // 工具调用（debug）
  | 'tts'        // 语音合成
  | 'music'      // 音乐控制
  | 'status'     // 系统状态
  | 'error'      // 错误
  | 'heartbeat'  // 心跳

/** WS 消息统一格式 */
export interface WsMessage<T = unknown> {
  type: WsMessageType
  subtype?: string
  id?: string               // 请求-响应匹配用
  ts?: number               // 毫秒时间戳
  payload: T
}

// ===== 对话消息 =====

/** 用户文本输入 */
export interface ChatUserTextPayload {
  text: string
  source: 'chat' | 'voice'
}

/** Agent 回复（核心消息） */
export interface ChatReplyPayload {
  reply: string                       // AI 文字回复
  emotion?: string                    // 推断的用户情绪
  intent?: string                     // chat | request_music | skip | ...
  scene?: string                      // 当前场景
  confidence?: number                 // 置信度 0-1
  decision_summary?: string           // Agent 决策摘要
  should_speak: boolean               // 是否主动说话
  should_play_music: boolean          // 是否切歌/推荐
  agent?: {
    version: string
    persona: string
  }
}

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

/** 前端 UI 中使用的消息（兼容 WS 消息结构） */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  attachments?: ChatAttachment[]
  isStreaming?: boolean
  emotion?: string
  intent?: string
}

export type ChatAttachment =
  | { type: 'song'; song: Song; reason: string }
  | { type: 'playlist'; songs: Song[]; reason: string }
  | { type: 'image'; url: string; caption: string }
