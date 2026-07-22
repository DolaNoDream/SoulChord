/**
 * WebSocket 连接管理（v1.1 — 对齐 frontend-agent-api.md）
 */
import { ref, onUnmounted } from 'vue'
import { createAgentSocket, buildWsMsg, ERROR_CODES } from '@/api/agent'
import { usePlayerStore, setWsSend, setMusicVolume, getMusicVolume } from '@/stores/player'
import { useChatStore } from '@/stores/chat'
import type { WsMessage, ChatReplyPayload, DjSpeechPayload, TtsSynthesizePayload, OperationType } from '@/types/chat'
import type { Song, MusicPlayPayload } from '@/types/music'

/**
 * 持久的 TTS 音频元素 — 避免 GC 回收导致播放中断。
 * 所有 TTS/DJ speech 音频复用此元素，每次切换 src 播放。
 *
 * 音频闪避（Audio Ducking）：TTS 说话时压低音乐音量，说完恢复。
 */
let _ttsAudio: HTMLAudioElement | null = null
/** 闪避比例：DJ 说话时音量降到原音量的 25% */
const DUCK_RATIO = 0.25

/** 音量渐变时长（毫秒） */
const DUCK_FADE_MS = 1500

/** 当前渐变 RAF 句柄（用于取消上一轮） */
let _fadeRafId: number | null = null

/** 闪避前保存的音乐音量，用于恢复 */
let _savedMusicVolume: number | null = null

function _getTtsAudio(): HTMLAudioElement {
  if (!_ttsAudio) {
    _ttsAudio = new Audio()
    _ttsAudio.volume = 1.0  // TTS 自身满音量
    _ttsAudio.addEventListener('error', () => {
      const errMsg = _ttsAudio?.error?.message || 'unknown'
      console.warn('[TTS] audio error:', errMsg, 'src:', _ttsAudio?.src)
    })
  }
  return _ttsAudio
}

/** 逐帧渐变音量 —— 从 from 平滑过渡到 to */
function _fadeVolume(from: number, to: number, durationMs: number) {
  if (_fadeRafId !== null) cancelAnimationFrame(_fadeRafId)
  const start = performance.now()

  function _tick() {
    try {
      const p = Math.min((performance.now() - start) / durationMs, 1)
      // smoothstep ease-in-out
      const eased = p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2
      setMusicVolume(from + (to - from) * eased)
      if (p < 1) {
        _fadeRafId = requestAnimationFrame(_tick)
        return
      }
    } catch (e) {
      console.error('[TTS] _tick error:', e)
      // 渐变失败时跳到最终值
      setMusicVolume(to)
    }
    _fadeRafId = null
  }

  _fadeRafId = requestAnimationFrame(_tick)
}

/** 降低音乐音量（渐变开始） */
function _duckMusic() {
  if (_savedMusicVolume !== null) return  // 已在闪避中
  _savedMusicVolume = getMusicVolume()
  const target = _savedMusicVolume * DUCK_RATIO
  console.log('[TTS] ducking music: volume', _savedMusicVolume, '→', target)
  try {
    _fadeVolume(_savedMusicVolume, target, DUCK_FADE_MS)
  } catch (e) {
    console.error('[TTS] _fadeVolume error, falling back to direct setMusicVolume:', e)
    setMusicVolume(target)
  }
}

/** 恢复音乐音量（渐变结束） */
function _unduckMusic() {
  if (_savedMusicVolume === null) return  // 未被闪避
  const from = getMusicVolume()
  console.log('[TTS] unducking music: volume', from, '→', _savedMusicVolume)
  try {
    _fadeVolume(from, _savedMusicVolume, DUCK_FADE_MS)
  } catch (e) {
    console.error('[TTS] _fadeVolume error, falling back to direct setMusicVolume:', e)
    setMusicVolume(_savedMusicVolume)
  }
  _savedMusicVolume = null
}

function _playTtsAudio(audioUrl: string) {
  if (!audioUrl) {
    console.warn('[TTS] audio_url is empty, skip playback')
    return
  }
  const el = _getTtsAudio()
  console.log('[TTS] playing:', audioUrl)

  // 移除旧事件处理器
  el.onplay = null
  el.onended = null
  el.onerror = null

  // ★ TTS 真正开始播放时 duck，避免"音乐先降了 TTS 还没响"的空档
  el.onplay = () => {
    console.log('[TTS] playback started')
    _duckMusic()
  }
  el.onended = () => {
    console.log('[TTS] playback ended')
    _unduckMusic()
    el.onended = null
  }
  el.onerror = () => {
    console.warn('[TTS] playback error')
    _unduckMusic()
    el.onerror = null
  }

  el.src = audioUrl
  el.load()
  el.play().catch((err: unknown) => {
    console.warn('[TTS] play() blocked:', (err as Error)?.message || err)
    // play 失败 => onplay 不会触发 => duck 不会执行 => 不需要 unduck
  })
}

export function useWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const sessionId = ref<string | null>(null)
  const agentVersion = ref('')
  const heartbeatTimer = ref<ReturnType<typeof setInterval> | null>(null)
  /** ★ WS 断连期间的消息队列 — 重连后自动发送 */
  const pendingQueue = ref<Array<{type: string; subtype: string; payload: unknown; id?: string}>>([])
  /** 是否是主动断开（不自动重连） */
  let intentionalDisconnect = false

  const playerStore = usePlayerStore()
  const chatStore = useChatStore()

  /** 连接 WebSocket */
  function connect() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) return

    ws.value = createAgentSocket()

    ws.value.onopen = () => {
      isConnected.value = true
      setWsSend(send)
      flushPending()
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
      // ★ 不设 wsSend=null — send() 内部会检查 WS 状态并自动入队
      //   这样 onSongEnded 等回调在断连期间调用 wsSend 时不会丢失消息
      stopHeartbeat()
      if (!intentionalDisconnect) {
        console.log('[WS] 已断开，5 秒后重连')
        setTimeout(connect, 5000)
      }
    }

    ws.value.onerror = (err) => {
      console.error('[WS] 连接错误:', err)
    }
  }

  /** 断开连接（主动断开，不自动重连） */
  function disconnect() {
    intentionalDisconnect = true
    stopHeartbeat()
    ws.value?.close()
    ws.value = null
    isConnected.value = false
    setWsSend(null)
  }

  /** ★ 发送消息 — WS 未连接时入队等待重连后发送 */
  function send(type: string, subtype: string, payload: unknown, id?: string) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      console.warn('[WS] 未连接，消息入队等待重连:', type, subtype)
      pendingQueue.value.push({type, subtype, payload, id})
      return
    }
    ws.value.send(buildWsMsg(type, subtype, payload, id))
  }

  /** ★ 重连后发送所有积压消息 */
  function flushPending() {
    if (pendingQueue.value.length === 0) return
    const queue = [...pendingQueue.value]
    pendingQueue.value = []
    for (const msg of queue) {
      if (ws.value && ws.value.readyState === WebSocket.OPEN) {
        ws.value.send(buildWsMsg(msg.type, msg.subtype, msg.payload, msg.id))
      }
    }
    console.log(`[WS] 已发送 ${queue.length} 条积压消息`)
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
          chatStore.isSending = false  // ★ 解锁输入框
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

      // AI DJ speech
      case 'dj':
        if (subtype === 'speech') {
          const p = payload as DjSpeechPayload
          if (p.text) {
            chatStore.addMessage({
              id: crypto.randomUUID(),
              role: 'system',
              content: `🎙️ ${p.text}`,
              timestamp: new Date().toISOString(),
            })
          }
          // 播放 TTS 音频（复用持久元素，避免 GC 回收）
          if (p.audio_url) {
            _playTtsAudio(p.audio_url)
          } else {
            console.warn('[WS] dj.speech without audio_url, text:', p.text?.slice(0, 40))
          }
        }
        break

      // TTS 语音合成（transition speech，含实际音频 URL）
      case 'tts':
        if (subtype === 'synthesize') {
          const p = payload as TtsSynthesizePayload
          if (p.audio_url) {
            _playTtsAudio(p.audio_url)
          } else {
            console.warn('[WS] tts.synthesize without audio_url, text:', p.text?.slice(0, 40))
          }
        }
        break

      // heartbeat
      case 'heartbeat':
        if (subtype === 'pong') {
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
