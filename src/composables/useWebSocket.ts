/**
 * WebSocket 连接管理（对齐 frontend-agent-api.md v0.3）
 */
import { ref, onUnmounted } from 'vue'
import { createAgentSocket, buildWsMsg } from '@/api/agent'
import { usePlayerStore, setWsSend } from '@/stores/player'
import { useChatStore } from '@/stores/chat'
import type { WsMessage, ChatReplyPayload } from '@/types/chat'
import type { Song, MusicPlayPayload } from '@/types/music'

export function useWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const sessionId = ref<string | null>(null)
  const agentInfo = ref<{ version: string; persona: string } | null>(null)
  const heartbeatTimer = ref<ReturnType<typeof setInterval> | null>(null)

  const playerStore = usePlayerStore()
  const chatStore = useChatStore()

  /** 连接 WebSocket */
  function connect() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) return

    ws.value = createAgentSocket()

    ws.value.onopen = () => {
      isConnected.value = true
      setWsSend(send)  // 注入 WS 发送函数到 playerStore，用于上报播放事件
      console.log('[WS] 已连接')
      startHeartbeat()
    }

    ws.value.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        handleMessage(msg)
      } catch {
        console.warn('[WS] 无法解析消息:', event.data)
      }
    }

    ws.value.onclose = () => {
      isConnected.value = false
      setWsSend(null)  // 清除注入
      stopHeartbeat()
      console.log('[WS] 已断开，5 秒后重连')
      setTimeout(connect, 5000)
    }

    ws.value.onerror = (err) => {
      console.error('[WS] 连接错误:', err)
    }
  }

  /** 断开连接 */
  function disconnect() {
    stopHeartbeat()
    ws.value?.close()
    ws.value = null
    isConnected.value = false
  }

  /** 发送消息 */
  function send(type: string, subtype: string, payload: unknown, id?: string) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      console.warn('[WS] 未连接，无法发送')
      return
    }
    ws.value.send(buildWsMsg(type, subtype, payload, id))
  }

  /** 处理收到的消息 */
  function handleMessage(msg: WsMessage) {
    const { type, subtype, payload } = msg

    switch (type) {
      // 欢迎消息
      case 'status':
        if (subtype === 'welcome') {
          const p = payload as { session_id: string; agent: { version: string; persona: string } }
          sessionId.value = p.session_id
          agentInfo.value = p.agent
        } else if (subtype === 'expression') {
          const p = payload as { expression: string }
          playerStore.currentExpression = p.expression
        }
        break

      // AI 回复
      case 'chat':
        if (subtype === 'reply') {
          const p = payload as ChatReplyPayload
          chatStore.addMessage({
            id: msg.id || crypto.randomUUID(),
            role: 'assistant',
            content: p.reply,
            timestamp: new Date().toISOString(),
            emotion: p.emotion,
            intent: p.intent,
          })
          chatStore.isStreaming = false
        }
        break

      // 音乐控制
      case 'music':
        handleMusicMessage(subtype || '', payload)
        break

      // TTS
      case 'tts':
        if (subtype === 'synthesize') {
          const p = payload as { text: string; audio_url: string; voice: string }
          // 播放 TTS 音频
          const audio = new Audio(p.audio_url)
          audio.play().catch(() => {})
          // 播放完后回执
          audio.onended = () => {
            send('tts', 'played', { played_ms: audio.duration ? audio.duration * 1000 : 0 }, msg.id)
          }
        }
        break

      // 错误
      case 'error':
        console.error('[WS] Agent 错误:', payload)
        break

      // 心跳
      case 'heartbeat':
        if (subtype === 'pong') {
          // 心跳响应，无需处理
        }
        break
    }
  }

  /** 处理音乐类消息 */
  function handleMusicMessage(subtype: string, payload: unknown) {
    switch (subtype) {
      case 'play': {
        const p = payload as MusicPlayPayload
        if (p.song && p.play_url) {
          // 转换新版 Song 格式为 playerStore 期望的格式
          playerStore.playSong({
            id: p.song.id,
            name: p.song.name,
            artists: p.song.artists,
            album: p.song.album,
            duration_ms: p.song.duration_ms,
            fee: p.song.fee,
            cover_url: p.song.cover_url,
          }, p.play_url, p.reason)
        }
        break
      }
      case 'pause':
        playerStore.togglePlay()  // 如果正在播放则暂停
        break
      case 'resume':
        playerStore.togglePlay()  // 如果暂停则恢复
        break
      case 'skip': {
        const p = payload as { song_id: string; reason: string }
        playerStore.next()
        break
      }
      case 'update_playlist': {
        const p = payload as { songs: Song[]; current_index: number }
        playerStore.queue = p.songs.map(s => ({
          id: s.id, name: s.name, artists: s.artists, album: s.album,
          duration_ms: s.duration_ms, fee: s.fee, cover_url: s.cover_url,
        }))
        break
      }
    }
  }

  /** 心跳 */
  function startHeartbeat() {
    heartbeatTimer.value = setInterval(() => {
      send('heartbeat', 'ping', {})
    }, 30000)
  }

  function stopHeartbeat() {
    if (heartbeatTimer.value) {
      clearInterval(heartbeatTimer.value)
      heartbeatTimer.value = null
    }
  }

  // 组件卸载时断开
  onUnmounted(() => disconnect())

  return {
    ws, isConnected, sessionId, agentInfo,
    connect, disconnect, send,
  }
}
