/** 用户画像相关类型定义（v1.1 — 对齐前端功能设计文档 4.1） */

/** 用户完整画像 UserProfits（对齐文档 4.1 + v9.15 P4 扩展） */
export interface UserProfits {
  // 前端手动维护基础信息
  nickname: string
  avatar_url?: string
  // AI 自动生成音乐偏好（不可手动编辑）
  favorite_genres: string[]         // 喜爱曲风
  favorite_artists: string[]        // 喜爱歌手
  disliked_genres: string[]         // 排斥曲风
  music_preference_desc: string     // 整体听歌偏好描述
  AI_conclusion: string             // AI 一句话总结
  update_at: number                 // 画像AI更新毫秒时间戳
  // v9.15 P4 扩展画像字段
  energy_baseline?: number          // 能量基线 0.0-1.0
  tempo_preference?: string         // 速度偏好 fast/moderate/slow/mixed
  mood_distribution?: Record<string, number>  // 情绪分布
  era_affinity?: Record<string, number>       // 年代偏好
  vocal_preference?: string         // 人声偏好
  discovery_openness?: number       // 探索意愿 0.0-1.0
  listening_pattern?: string        // 聆听模式
  confidence?: number               // 分析置信度 0.0-1.0
}

/** @deprecated 旧版用户信息（保留兼容，新代码请使用 UserProfits） */
export interface UserProfile {
  name: string
  favorite_genres: string[]
  favorite_artists: string[]
  disliked_genres: string[]
  created_at: number
}

/** 最近情绪记录 */
export interface RecentMood {
  mood: string
  ts: number
}

/** Agent 信息 */
export interface AgentInfo {
  version: string
  persona: string
}
