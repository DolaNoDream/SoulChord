/** 用户画像相关类型定义（v0.3） */

/** 用户基本信息（对齐 GET /api/init 的 user_profile） */
export interface UserProfile {
  name: string                      // 用户昵称
  favorite_genres: string[]         // 喜欢的曲风
  favorite_artists: string[]        // 喜欢的艺人（名字列表）
  disliked_genres: string[]         // 不喜欢的曲风
  created_at: number                // 创建时间（毫秒时间戳）
}

/** Memory 条目 */
export interface Memory {
  key: string                           // 如 'favorite_genres'
  category: 'profile' | 'preference' | 'context' | 'feedback'
  value: unknown                        // 值
  confidence: number                    // 0-1
  source: 'user_input' | 'inferred' | 'feedback'
  updated_at: number                    // 毫秒时间戳
}

/** 最近情绪记录 */
export interface RecentMood {
  mood: string
  ts: number
}

/** Agent 信息 */
export interface AgentInfo {
  version: string           // 语义化版本
  persona: string           // DJ 人格 ID
}
