/** 用户画像相关类型定义 */

import type { EmotionType } from './music'

/** 用户基本信息 */
export interface UserProfile {
  id: string              // 用户唯一标识
  nickname: string        // 用户昵称
  avatarUrl: string       // 头像图片地址
  createdAt: string       // 注册/首次使用时间（ISO 8601 格式）
  totalSongsPlayed: number   // 累计播放歌曲数
  totalHoursListened: number // 累计收听时长（小时）
  favoriteTimeOfDay: string  // 最常听歌的时段（如 '22:00-02:00'）
}

/** 音乐风格偏好 */
export interface GenrePreference {
  genre: string                     // 风格名称（如 'pop'、'jazz'）
  weight: number                    // 偏好权重（0.0 ~ 1.0，越高越喜欢）
  trend: 'rising' | 'stable' | 'declining'  // 近期趋势：上升 / 稳定 / 下降
}

/** 艺人偏好 */
export interface ArtistPreference {
  artist: string        // 艺人名称
  playCount: number     // 播放次数
  lastPlayed: string    // 最近一次播放时间（ISO 8601 格式）
}

/** 年代偏好 */
export interface DecadePreference {
  decade: string    // 年代（如 '1990s'、'2010s'）
  weight: number    // 偏好权重（0.0 ~ 1.0，越高越喜欢）
}

/** 情绪偏好 */
export interface MoodPreference {
  mood: EmotionType  // 情绪类型
  weight: number     // 偏好权重（0.0 ~ 1.0，越高越常听）
}

/** 音乐DNA（AI 对用户音乐品味的综合画像） */
export interface MusicDNA {
  genres: GenrePreference[]     // 最爱的音乐风格排行
  artists: ArtistPreference[]   // 最爱的艺人排行
  decades: DecadePreference[]   // 年代偏好分布
  moods: MoodPreference[]       // 情绪偏好分布
  energyLevel: number           // 能量水平（0 = 纯氛围音乐 ~ 100 = 纯高能音乐）
  vocalsPreference: number      // 人声偏好（0 = 纯器乐 ~ 100 = 纯人声）
  noveltyScore: number          // 探索倾向（0 = 只听熟悉的 ~ 100 = 热衷新歌）
  summary: string               // AI 生成的一句话总结（如"90年代华语流行的怀旧灵魂"）
}

/** 用户完整状态（Pinia store 数据结构） */
export interface UserState {
  profile: UserProfile | null                  // 用户基本信息
  listeningHistory: Array<{ songId: string; playedAt: string }>  // 听歌历史
  musicDNA: MusicDNA | null                    // 音乐DNA画像
  isOnboarded: boolean                         // 是否已完成首次引导
  isAnalyzing: boolean                         // AI 是否正在分析中
}
