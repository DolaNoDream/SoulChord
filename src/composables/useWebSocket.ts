/**
 * WebSocket 连接管理（v1.1 — 对齐 frontend-agent-api.md）
 */
import { ref, onUnmounted } from 'vue'
import { createAgentSocket, buildWsMsg, ERROR_CODES } from '@/api/agent'
import { usePlayerStore, setWsSend } from '@/stores/player'
import { useChatStore } from '@/stores/chat'
import type { WsMessage, ChatReplyPayload, OperationType } from '@/types/chat'
import type { Song, MusicPlayPayload } from '@/types/music'

export function useWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const sessionId = ref<string | null>(null)
  const agentVersion = ref('')
  const heartbeatTimer = ref<ReturnType<typeof setInterval> | null>(null)

  const playerStore = usePlayerStore()
  const chatStore = useChatStore()

  /** 连接 WebSocket */
  function connect() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) return

    ws.value = createAgentSocket()

    ws.value.onopen = () => {
      isConnected.value = true
      setWsSend(send)
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
      setWsSend(null)
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

  /** 处理 chat.reply 中的 operation 指令 */
  function handleOperation(operation: OperationType) {
    switch (operation) {
      case 'play_song':
        // 实际播放由 music.play 消息单独触发，chat.reply 仅标记文案
        break
      case 'skip_song':
        playerStore.next()
        break
      case 'add_playlist':
        // 添加到队列的歌曲由 music.play / music.update_playlist 下发
        // 如果当前正在播放的歌曲存在，将其加入队列
        if (playerStore.currentSong) {
          playerStore.addToQueue({ ...playerStore.currentSong })
        }
        break
      case 'recommend':
        // 推荐歌曲列表通过 music.update_playlist 或后续 music.play 下发
        break
      case 'song_intro':
        // 仅展示歌曲介绍文字，无播放动作
        break
    }
  }

  /** 处理收到的消息 */
  function handleMessage(msg: WsMessage) {
    const { type, subtype, payload } = msg

    switch (type) {
      // 系统状态
      case 'status':
        if (subtype === 'welcome') {
          const p = payload as { session_id: string }
          sessionId.value = p.session_id
        }
        break

      // AI 回复（对齐文档 2.3.1 chat.reply — text/url/operation 三段核心数据）
      case 'chat':
        if (subtype === 'reply') {
          const p = payload as ChatReplyPayload
          const messageId = msg.id || crypto.randomUUID()
          chatStore.addMessage({
            id: messageId,
            role: 'assistant',
            content: p.text,
            timestamp: new Date().toISOString(),
            url: p.url,
            operation: p.operation,
            intent: p.intent,
          })
          chatStore.isStreaming = false
          // 处理操作指令
          handleOperation(p.operation)
        }
        break

      // 音乐控制
      case 'music':
        handleMusicMessage(subtype || '', payload)
        break

      // 错误
      case 'error': {
        const p = payload as { code: number; msg: string }
        const errText = p.msg || ERROR_CODES[p.code] || '未知错误'
        console.error(`[WS] Agent 错误 [${p.code}]: ${errText}`)
        // 把错误消息也展示在对话中
        chatStore.addMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: `⚠️ ${errText}`,
          timestamp: new Date().toISOString(),
        })
        break
      }

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
        if (playerStore.isPlaying) playerStore.togglePlay()
        break
      case 'resume':
        if (!playerStore.isPlaying) playerStore.togglePlay()
        break
      case 'skip':
        playerStore.next()
        break
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
    ws, isConnected, sessionId, agentVersion,
    connect, disconnect, send,
  }
}
