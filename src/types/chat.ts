/** AI 对话相关类型定义 */

import type { Song, Playlist, EmotionType, ScenarioType } from './music'

/** 消息角色 */
export type MessageRole =
  | 'user'       // 用户发送的消息
  | 'assistant'  // AI DJ 的回复
  | 'system'     // 系统通知（如连接状态、引导提示）

/** 对话附件类型（消息中可携带的富媒体内容） */
export type ChatAttachment =
  | { type: 'song'; song: Song; reason: string }            // 歌曲推荐 + 推荐理由
  | { type: 'playlist'; playlist: Playlist; reason: string } // 歌单推荐 + 推荐理由
  | { type: 'image'; url: string; caption: string }         // 图片 + 说明文字

/** 对话消息 */
export interface ChatMessage {
  id: string              // 消息唯一标识
  role: MessageRole       // 发送者角色
  content: string         // 消息正文（纯文本）
  timestamp: string       // 发送时间（ISO 8601 格式）
  attachments?: ChatAttachment[]  // 附件列表（歌曲、歌单、图片等，可选）
  isStreaming?: boolean   // 是否正在流式输出中（AI 回复逐字显示时）
  emotion?: EmotionType   // AI DJ 回复时带有的情绪色彩
}

/** 快捷场景（预设的对话入口按钮） */
export interface QuickScene {
  id: string              // 场景唯一标识
  label: string           // 按钮显示文字（如"有点累"）
  icon: string            // 按钮图标名（Element Plus 图标组件名）
  promptTemplate: string  // 点击后发送给 AI 的预设提问
  scenario: ScenarioType  // 关联的场景类型
}

/** 对话会话（一次完整的聊天记录） */
export interface ConversationSession {
  id: string              // 会话唯一标识
  startedAt: string       // 会话开始时间（ISO 8601 格式）
  lastMessageAt: string   // 最后一条消息时间（ISO 8601 格式）
  messageCount: number    // 消息总数
  summary: string         // AI 生成的会话摘要（一句话概括）
}

/** 聊天状态（Pinia store 数据结构） */
export interface ChatState {
  messages: ChatMessage[]           // 消息列表
  isStreaming: boolean              // AI 是否正在回复中
  currentStreamingMessage: string   // 当前正在流式输出的文字
  inputText: string                 // 输入框中的文字
  conversationId: string | null     // 当前会话 ID
  quickScenes: QuickScene[]         // 快捷场景按钮列表
}
