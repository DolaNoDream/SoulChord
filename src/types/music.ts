/** 音乐播放相关类型定义 */

/** 歌曲情绪类型 */
export type EmotionType =
  | 'energetic'   // 充满活力
  | 'calm'        // 平静
  | 'melancholic' // 忧伤
  | 'happy'       // 开心
  | 'romantic'    // 浪漫
  | 'dark'        // 暗黑
  | 'neutral'     // 中性

/** 场景类型 */
export type ScenarioType =
  | 'morning'    // 清晨
  | 'afternoon'  // 午后
  | 'evening'    // 傍晚
  | 'lateNight'  // 深夜
  | 'workout'    // 运动
  | 'focus'      // 专注
  | 'relax'      // 放松
  | 'sleep'      // 睡眠
  | 'commute'    // 通勤
  | 'party'      // 派对

/** 播放模式 */
export type PlaybackMode =
  | 'sequential'  // 顺序播放
  | 'random'      // 随机播放
  | 'singleLoop'  // 单曲循环

/** 音乐来源 */
export type MusicSource =
  | 'local'    // 本地文件
  | 'netease'  // 网易云音乐
  | 'qq'       // QQ 音乐
  | 'spotify'  // Spotify

/** 歌曲 */
export interface Song {
  id: string            // 歌曲唯一标识
  title: string         // 歌曲标题
  artist: string        // 歌手/艺人名
  album: string         // 所属专辑名
  coverUrl: string      // 专辑封面图片地址
  audioUrl: string      // 音频文件播放地址
  duration: number      // 歌曲时长（秒）
  genres: string[]      // 音乐风格标签（如 ['pop', 'rock']）
  emotion: EmotionType  // 歌曲传达的情绪
  bpm: number | null    // 每分钟节拍数，可能为空
  year: number | null   // 发行年份，可能为空
  source: MusicSource   // 音乐来源平台
  externalId: string | null  // 来源平台的原始 ID，本地文件为空
  reason?: string       // AI 推荐理由（可选）
}

/** 歌单 */
export interface Playlist {
  id: string                  // 歌单唯一标识
  name: string                // 歌单名称
  description: string         // 歌单简介/推荐语
  coverUrl: string            // 歌单封面图片地址
  songs: Song[]               // 歌单包含的歌曲列表
  scenario: ScenarioType      // 适用场景
  generatedBy: 'ai' | 'curator' | 'user'  // 生成方式：AI 生成 / 人工策划 / 用户创建
  createdAt: string           // 创建时间（ISO 8601 格式）
}

/** 听歌记录 */
export interface ListeningRecord {
  songId: string        // 歌曲 ID
  playedAt: string      // 播放时间（ISO 8601 格式）
  durationListened: number  // 实际收听时长（秒）
  skipped: boolean      // 是否被跳过
  source: 'queue' | 'recommendation' | 'chat' | 'manual'  // 播放来源：队列 / 推荐 / 对话 / 手动
}

/** 播放器状态 */
export interface PlayerState {
  currentSong: Song | null    // 当前播放的歌曲，无则为 null
  queue: Song[]               // 播放队列
  history: Song[]             // 已播放的历史列表
  isPlaying: boolean          // 是否正在播放
  volume: number              // 音量（0.0 ~ 1.0）
  currentTime: number         // 当前播放进度（秒）
  duration: number            // 当前歌曲总时长（秒）
  playbackMode: PlaybackMode  // 播放模式
  isMuted: boolean            // 是否静音
  isLoading: boolean          // 是否正在缓冲加载
}
