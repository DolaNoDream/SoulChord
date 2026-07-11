/**
 * AI Agent 通信层（v0.3 — 对齐 frontend-agent-api.md）
 * 通道：WebSocket（主）+ HTTP（补充）
 */
import axios, { type AxiosInstance } from 'axios'
import type { Song } from '@/types/music'
import type { UserProfile, Memory, RecentMood, AgentInfo } from '@/types/user'

/** Agent 基础地址 */
const AGENT_BASE_URL = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/ws/client'

// ===== Axios 实例 =====
const http: AxiosInstance = axios.create({
  baseURL: `${AGENT_BASE_URL}/api`,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 响应拦截器：检查 {code, msg, data} 格式
http.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        return Promise.reject(new Error(body.msg || `Error code ${body.code}`))
      }
      return { ...res, data: body.data }
    }
    return res
  },
  (err) => Promise.reject(err)
)

// ===== HTTP 接口 =====

/** 1.1 启动初始化：拉取用户画像、情绪、当前状态 */
export async function fetchInit(): Promise<{
  agent: AgentInfo
  user_profile: UserProfile
  recent_moods: RecentMood[]
  current_state: {
    is_playing: boolean
    current_song: Song | null
    scene: string
    active_expression: string
  }
  settings: Record<string, unknown>
}> {
  const res = await http.get('/init')
  return res.data
}

/** 1.2 获取设置 */
export async function getSettings(): Promise<Record<string, unknown>> {
  const res = await http.get('/settings')
  return res.data
}

/** 1.3 更新设置（增量） */
export async function updateSettings(data: Record<string, unknown>): Promise<void> {
  await http.put('/settings', data)
}

/** 1.4 歌曲反馈 */
export async function sendFeedback(params: {
  song_id: string
  action: 'like' | 'dislike' | 'skip' | 'favorite'
}): Promise<void> {
  await http.post('/feedback', { ...params, ts: Date.now() })
}

/** 1.5 播放历史 */
export async function fetchSongHistory(limit = 50, offset = 0): Promise<{
  total: number
  items: Array<{
    song_id: string
    played_at: number
    feedback: string
    duration_played_ms: number
  }>
}> {
  const res = await http.get('/history/songs', { params: { limit, offset } })
  return res.data
}

/** 1.6 更新用户画像偏好 */
export async function updateUserProfile(data: {
  favorite_genres?: string[]
  favorite_artists?: string[]
  disliked_genres?: string[]
}): Promise<void> {
  await http.post('/user/profile', data)
}

/** 1.7 查询 Memory */
export async function queryMemory(params?: {
  key?: string
  category?: 'profile' | 'preference' | 'context' | 'feedback'
}): Promise<{ memories: Memory[] }> {
  const res = await http.get('/memory/query', { params })
  return res.data
}

/** 1.8 更新 Memory */
export async function updateMemory(data: {
  key: string
  category: 'profile' | 'preference' | 'context' | 'feedback'
  value: unknown
  source?: 'user_input' | 'inferred' | 'feedback'
}): Promise<{ updated: boolean; ts: number }> {
  const res = await http.post('/memory/update', { ...data, source: data.source || 'user_input' })
  return res.data
}

/** 1.9 删除 Memory */
export async function deleteMemory(key: string): Promise<void> {
  await http.delete(`/memory/${key}`)
}

// ===== WebSocket 连接 =====

/** 创建 WebSocket 连接 */
export function createAgentSocket(): WebSocket {
  const ws = new WebSocket(WS_URL)
  return ws
}

/** 构建 WS 消息 */
export function buildWsMsg<T>(type: string, subtype: string, payload: T, id?: string): string {
  return JSON.stringify({
    type,
    subtype,
    id: id || crypto.randomUUID(),
    ts: Date.now(),
    payload,
  })
}

export { http, AGENT_BASE_URL, WS_URL }
