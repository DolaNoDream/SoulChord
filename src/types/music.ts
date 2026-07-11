/** 音乐播放相关类型定义（v0.3 — 对齐 frontend-agent-api.md） */

/** 艺人 */
export interface Artist {
  id: string       // 艺人 ID
  name: string     // 艺人名称
}

/** 专辑 */
export interface Album {
  id: string       // 专辑 ID
  name: string     // 专辑名称
}

/** 歌曲（对齐网易云数据模型） */
export interface Song {
  id: string                 // 歌曲唯一 ID（网易云加密 id，32 位）
  name: string               // 歌曲名称
  artists: Artist[]          // 艺人列表（多人合作时有多个）
  album: Album               // 所属专辑
  duration_ms: number        // 时长（毫秒）
  fee: number                // 0=免费 1=VIP 4=数字专辑 8=低质免费
  cover_url?: string         // 专辑封面 URL
}

/** 音乐播放控制消息（WS music.* 相关） */
export interface MusicPlayPayload {
  song: Song
  play_url: string             // 可播放的音频 URL
  play_url_expires_at: number  // 播放链接过期时间（毫秒时间戳）
  auto_play: boolean           // 是否自动播放
  reason: string               // AI 推荐理由
}

/** 播放器事件类型 */
export type PlayerEventType = 'play_start' | 'play_end' | 'pause' | 'resume' | 'error'

/** 播放模式 */
export type PlaybackMode = 'sequential' | 'random' | 'singleLoop'

/** 播放器状态 */
export interface PlayerState {
  currentSong: Song | null
  queue: Song[]
  history: Song[]
  isPlaying: boolean
  volume: number
  currentTime: number
  duration: number
  playbackMode: PlaybackMode
  isMuted: boolean
  isLoading: boolean
}
