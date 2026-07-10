/**
 * AI Agent 通信层
 * 与本地 Python FastAPI Agent 通过 HTTP 通信
 */
import axios, { type AxiosInstance } from 'axios'
import type { ChatMessage } from '@/types/chat'
import type { Playlist } from '@/types/music'
import type { UserProfile, MusicDNA } from '@/types/user'
import type { Song } from '@/types/music'

/** Agent API 基础地址（本地 FastAPI） */
const AGENT_BASE_URL = 'http://localhost:8000/api'

/** 创建 axios 实例 */
const http: AxiosInstance = axios.create({
  baseURL: AGENT_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器：统一解包 {error, data} → 直接返回 data
http.interceptors.response.use(
  (res) => {
    const body = res.data
    // 如果后端按 {error: false, data: {...}} 格式返回，自动解包
    if (body && typeof body === 'object' && 'error' in body && 'data' in body) {
      if (body.error) {
        return Promise.reject(new Error(body.message || '请求失败'))
      }
      return { ...res, data: body.data }
    }
    return res
  },
  (err) => {
    // 网络错误或 HTTP 错误
    return Promise.reject(err)
  }
)

/** 健康检查 */
export async function healthCheck(): Promise<boolean> {
  try {
    const res = await http.get('/health')
    return res.status === 200
  } catch {
    return false
  }
}

/** 发送流式对话消息（SSE 逐字推送） */
export async function sendStreamMessage(
  text: string,
  conversationId: string | null,
  onChunk: (chunk: string) => void,
  onDone: (fullMessage: ChatMessage) => void,
  onError: (err: Error) => void
): Promise<void> {
  try {
    const res = await fetch(`${AGENT_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, conversation_id: conversationId }),
    })

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let fullText = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      fullText += chunk
      onChunk(chunk)
    }

    const fullMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'assistant',
      content: fullText,
      timestamp: new Date().toISOString(),
    }
    onDone(fullMessage)
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}

/** 触发快捷场景（预设按钮） */
export async function triggerScene(
  sceneId: string,
  promptTemplate: string
): Promise<ChatMessage> {
  const res = await http.post('/scene', {
    scene_id: sceneId,
    prompt: promptTemplate,
  })
  return res.data
}

/** 获取今日推荐歌单 */
export async function getRecommendations(params?: {
  scenario?: string
  mood?: string
}): Promise<Playlist> {
  const res = await http.get('/recommendations', { params })
  return res.data
}

/** 获取用户音乐画像 */
export async function getUserProfile(): Promise<{
  profile: UserProfile
  musicDNA: MusicDNA
}> {
  const res = await http.get('/profile')
  return res.data
}

/** 分析用户喜欢的歌曲，生成音乐DNA */
export async function analyzeProfile(songs: Song[]): Promise<{
  profile: UserProfile
  musicDNA: MusicDNA
}> {
  const res = await http.post('/profile/analyze', {
    favorite_songs: songs.map(s => ({
      title: s.title,
      artist: s.artist,
      genres: s.genres,
    })),
  })
  return res.data
}

/** 歌曲反馈（喜欢/不喜欢） */
export async function sendSongFeedback(
  songId: string,
  feedback: 'like' | 'dislike'
): Promise<void> {
  await http.post('/feedback', { song_id: songId, feedback })
}

/** 更新用户基本信息（昵称、头像等） */
export async function updateProfile(data: {
  nickname?: string
  avatarUrl?: string
}): Promise<void> {
  await http.put('/profile', data)
}

export { http }
