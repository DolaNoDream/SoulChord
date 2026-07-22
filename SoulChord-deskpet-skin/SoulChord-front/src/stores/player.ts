import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Song, PlaybackMode } from '@/types/music'
import { sendFeedback } from '@/api/agent'

/** WS 发送函数的全局引用（由 useWebSocket 注入） */
let wsSend: ((type: string, subtype: string, payload: unknown) => void) | null = null
export function setWsSend(fn: ((type: string, subtype: string, payload: unknown) => void) | null) { wsSend = fn }

/** 私有引用 — 播放音乐的 HTMLAudioElement，不对外暴露，供音频闪避直接操作 volume */
let _musicEl: HTMLAudioElement | null = null

/**
 * 设置音乐播放音量。
 * 同时更新 Pinia volume 保持 UI 同步 + 直接操作 HTMLAudioElement.volume 确保实际生效。
 */
export function setMusicVolume(vol: number) {
  const v = Math.max(0, Math.min(1, vol))
  if (_musicEl) _musicEl.volume = v
  // 同步 Pinia，使 UI 音量条显示正确值
  try {
    const store = usePlayerStore()
    store.volume = v
  } catch {
    // store 可能还未初始化
  }
}

/** 获取当前音乐播放音量（从 HTMLAudioElement 读真实值） */
export function getMusicVolume(): number {
  return _musicEl?.volume ?? 1
}

/** 播放状态 localStorage 缓存键 — 页面刷新后恢复界面 */
const PLAYER_CACHE_KEY = 'soulchord-player-v1'
const PLAYER_CACHE_TTL_MS = 30 * 60 * 1000  // 30 分钟（URL 可能过期）

export const usePlayerStore = defineStore('player', () => {
  // ========== 状态 ==========
  const currentSong = ref<Song | null>(null)
  const playUrl = ref('')              // 当前歌曲的实际播放地址（来自 WS music.play）
  const playReason = ref('')           // AI 推荐理由
  const queue = ref<Song[]>([])
  const history = ref<Song[]>([])
  const isPlaying = ref(false)
  const volume = ref(0.7)
  const currentTime = ref(0)
  const duration = ref(0)
  const playbackMode = ref<PlaybackMode>('sequential')
  const isMuted = ref(false)
  const isLoading = ref(false)
  const currentExpression = ref('idle')  // 桌宠表情（来自 WS status.expression）
  const audioElement = ref<HTMLAudioElement | null>(null)
  /** 播放 URL 缓存（song_id → url），供 next() 本地切歌使用 */
  const urlCache = ref<Record<string, string>>({})
  /** 歌单播放模式 — next/prev 不走 WS skip，惰性取 URL，本地切换 */
  const isPlaylistMode = ref(false)
  // 喜欢的歌曲 ID 集合
  const likedSongIds = ref<Set<string>>(loadLikedSongs())

  // ========== 计算属性 ==========
  const progress = computed(() => duration.value === 0 ? 0 : (currentTime.value / duration.value) * 100)
  const currentSongIndex = computed(() => currentSong.value ? queue.value.findIndex(s => s.id === currentSong.value!.id) : -1)
  const hasNext = computed(() => playbackMode.value === 'singleLoop' ? true : currentSongIndex.value < queue.value.length - 1)
  const hasPrevious = computed(() => history.value.length > 0 || currentTime.value > 3)
  const isLiked = computed(() => currentSong.value ? likedSongIds.value.has(currentSong.value.id) : false)
  const formattedProgress = computed(() => formatTime(currentTime.value))
  const formattedDuration = computed(() => formatTime(duration.value))

  // ========== 方法 ==========
  function loadLikedSongs(): Set<string> {
    try { const d = localStorage.getItem('soulchord-liked'); return d ? new Set(JSON.parse(d)) : new Set() }
    catch { return new Set() }
  }

  function saveLikedSongs() {
    localStorage.setItem('soulchord-liked', JSON.stringify([...likedSongIds.value]))
  }

  function initAudio(audio: HTMLAudioElement) {
    audioElement.value = audio
    _musicEl = audio  // 音频闪避用私有引用
    audio.volume = volume.value
    audio.addEventListener('timeupdate', () => { currentTime.value = audio.currentTime })
    audio.addEventListener('loadedmetadata', () => { duration.value = audio.duration })
    audio.addEventListener('waiting', () => { isLoading.value = true })
    audio.addEventListener('canplay', () => { isLoading.value = false })
  }

  /**
   * 歌曲自然结束回调（由 useAudio.ts 的 ended 事件触发）。
   * 在调用 next(true) 前捕获正确的 song_id，然后发送 play_end。
   */
  function onSongEnded() {
    const endedId = currentSong.value?.id
    const endedMs = Math.round(currentTime.value * 1000)
    // ★ 先发 play_end 通知后端，再本地推进（避免 RDS current_song 失步）
    if (endedId) {
      wsSend?.('status', 'player_event', { event: 'play_end', song_id: endedId, played_ms: endedMs })
    }
    next(true)
  }

  /** 播放歌曲（新版：Song + play_url 分开） */
  function playSong(song: Song, url: string, reason?: string) {
    const prevId = currentSong.value?.id
    if (currentSong.value && currentSong.value.id !== song.id) {
      history.value.push(currentSong.value)
    }
    // 缓存播放 URL 供 next() 本地切歌使用
    urlCache.value[song.id] = url
    currentSong.value = song
    playUrl.value = url
    playReason.value = reason || ''
    isPlaying.value = true
    isLoading.value = true
    if (audioElement.value) {
      audioElement.value.src = url
      audioElement.value.play().catch((err: unknown) => {
        // 浏览器自动播放策略拦截 — 设回暂停态，用户点击任何地方时恢复
        console.warn('[Player] play blocked, waiting for user click:', (err as Error)?.message || err)
        isPlaying.value = false
        isLoading.value = false
        // 监听下一次用户点击来恢复播放
        const resumeOnClick = () => {
          if (audioElement.value && currentSong.value) {
            audioElement.value.play().then(() => {
              isPlaying.value = true
            }).catch(() => {})
          }
          document.removeEventListener('click', resumeOnClick)
        }
        document.addEventListener('click', resumeOnClick, { once: true })
      })
    }
    // 上报：新歌开始
    const artistName = song.artists?.map(a => a.name).join(', ') || ''
    wsSend?.('status', 'player_event', { event: 'play_start', song_id: song.id, prev_song_id: prevId, song_name: song.name, song_artist: artistName })
    _cacheState()
  }

  function playPlaylist(songs: Song[], startIndex = 0) {
    queue.value = songs
    if (songs.length > 0 && startIndex < songs.length) {
      // playSong needs url — use first song and fetch URL
      // In WS flow, music.play comes with play_url already
    }
  }

  /** 设置为歌单播放模式：同步队列到后端，next/prev 本地切换不走 WS skip */
  async function setPlaylistMode(songs: Song[]) {
    isPlaylistMode.value = true
    queue.value = songs
    try {
      const { syncPlaylistQueue } = await import('@/api/agent')
      await syncPlaylistQueue(songs)
    } catch (e) {
      console.warn('[Player] failed to sync playlist queue to backend:', e)
    }
    _cacheState()
  }

  /**
   * 从队列播放歌曲（歌单模式）：先查 URL 缓存，未命中则惰性取 URL
   */
  function _playFromQueue(song: Song) {
    const cachedUrl = urlCache.value[song.id]
    if (cachedUrl && audioElement.value) {
      audioElement.value.src = cachedUrl
      isPlaying.value = true
      isLoading.value = true
      audioElement.value.play().catch((err: unknown) => {
        console.warn('[Player] playlist next play blocked:', (err as Error)?.message || err)
        isPlaying.value = false
        isLoading.value = false
      })
      // ★ 通知后端本地队列推进（歌单模式也保持 RDS 同步）
      const qArtist = (song.artists as Array<{name: string}> | undefined)?.map(a => a.name).join(', ') || ''
      wsSend?.('status', 'player_event', { event: 'play_start', song_id: song.id, song_name: song.name, song_artist: qArtist })
      _cacheState()
      return
    }
    _lazyFetchUrl(song)
  }

  /** 惰性获取歌曲播放 URL */
  async function _lazyFetchUrl(song: Song) {
    try {
      const { playPlaylistSong } = await import('@/api/agent')
      const result = await playPlaylistSong(song)
      urlCache.value[song.id] = result.play_url
      if (audioElement.value) {
        audioElement.value.src = result.play_url
        isPlaying.value = true
        isLoading.value = true
        await audioElement.value.play()
      }
      _cacheState()
    } catch (e) {
      console.warn('[Player] failed to fetch URL for playlist song, skipping:', e)
      // URL 获取失败 → 跳过此歌，尝试下一首
      next()
    }
  }

  function togglePlay() {
    if (!audioElement.value) return
    if (isPlaying.value) {
      audioElement.value.pause(); isPlaying.value = false
      wsSend?.('status', 'player_event', { event: 'pause', song_id: currentSong.value?.id })
    } else {
      audioElement.value.play().then(() => {
        isPlaying.value = true
      }).catch((err: unknown) => {
        console.warn('[Player] resume failed:', (err as Error)?.message || err)
      })
      wsSend?.('status', 'player_event', { event: 'resume', song_id: currentSong.value?.id })
    }
  }

  /**
   * 切歌（用户点击下一首 或 歌曲自然结束）
   * @param fromEnded 是否由歌曲 ended 事件触发（自然结束 → 不发 WS skip，靠后端 play_end 驱动）
   */
  function next(fromEnded = false) {
    if (!currentSong.value) return
    // ★ 队列空时
    if (queue.value.length === 0) {
      if (fromEnded) return  // 自然结束，后端 play_end 事件会触发 REPLAN
      isPlaylistMode.value = false
      // 用户主动点击下一首 → 通知后端请求新歌
      wsSend?.('status', 'player_event', { event: 'skip', song_id: currentSong.value.id, reason: 'user_next_queue_empty' })
      sendFeedback({ song_id: currentSong.value.id, action: 'skip' }).catch(() => {})
      return
    }
    if (playbackMode.value === 'singleLoop') {
      if (audioElement.value) { audioElement.value.currentTime = 0; audioElement.value.play() }
      isPlaying.value = true
      return
    }
    let nextIndex: number
    if (playbackMode.value === 'random') {
      nextIndex = Math.floor(Math.random() * queue.value.length)
    } else {
      const idx = currentSongIndex.value
      if (idx >= queue.value.length - 1) {
        // ★ 已是最后一首
        if (isPlaylistMode.value) {
          // 歌单播完 → 退出歌单模式，回退 AI 推荐
          isPlaylistMode.value = false
          queue.value = []
          history.value = []
          _cacheState()
          if (fromEnded) return  // 自然结束：靠后端 play_end 触发 REPLAN
          // 用户主动点击：发 skip 触发 REPLAN
          wsSend?.('status', 'player_event', { event: 'skip', song_id: currentSong.value.id, reason: 'playlist_end' })
          sendFeedback({ song_id: currentSong.value.id, action: 'skip' }).catch(() => {})
          return
        }
        nextIndex = 0  // 普通模式从头循环
      } else {
        nextIndex = idx + 1
      }
    }
    const nextSong = queue.value[nextIndex]

    // ★ 歌单模式：不走 WS skip（避免触发后端 REPLAN 覆盖队列），惰性取 URL
    if (isPlaylistMode.value) {
      history.value.push(currentSong.value)
      currentSong.value = nextSong
      playReason.value = ''
      _playFromQueue(nextSong)
      return
    }

    // ★ 自然结束（fromEnded=true）：不发 WS skip 和 HTTP feedback，靠后端 play_end 处理
    //   useAudio.ts ended → next(true) → 本地推进队列，不发 skip
    //   initAudio 的 ended 监听器负责发 WS play_end → 后端消费队列
    //   避免双发 skip + play_end 导致队列推进两次
    if (!fromEnded) {
      // 用户主动点击 → 发 skip 反馈
      sendFeedback({ song_id: currentSong.value.id, action: 'skip' }).catch(() => {})
      wsSend?.('status', 'player_event', { event: 'skip', song_id: currentSong.value.id, reason: 'user_next' })
    }

    history.value.push(currentSong.value)
    // ★ 实际切歌：更新 currentSong + audioElement
    const prevId = currentSong.value.id
    currentSong.value = nextSong
    playReason.value = ''
    // ★ 通知后端新歌已开始（让 RDS current_song 保持同步）
    const nArtist = (nextSong.artists as Array<{name: string}> | undefined)?.map(a => a.name).join(', ') || ''
    wsSend?.('status', 'player_event', { event: 'play_start', song_id: nextSong.id, prev_song_id: prevId, song_name: nextSong.name, song_artist: nArtist })
    const cachedUrl = urlCache.value[nextSong.id]
    if (cachedUrl && audioElement.value) {
      audioElement.value.src = cachedUrl
      isPlaying.value = true
      isLoading.value = true
      audioElement.value.play().catch((err: unknown) => {
        console.warn('[Player] next play blocked:', (err as Error)?.message || err)
        isPlaying.value = false
        isLoading.value = false
      })
      _cacheState()
    }
  }

  function prev() {
    if (currentTime.value > 3 && audioElement.value) { audioElement.value.currentTime = 0; return }
    const prevSong = history.value.pop()
    if (prevSong) {
      if (currentSong.value) { queue.value.unshift(currentSong.value) }
      currentSong.value = prevSong
      playReason.value = ''
      const cachedUrl = urlCache.value[prevSong.id]
      if (cachedUrl && audioElement.value) {
        audioElement.value.src = cachedUrl
        isPlaying.value = true
        isLoading.value = true
        audioElement.value.play().catch((err: unknown) => {
          console.warn('[Player] prev play blocked:', (err as Error)?.message || err)
          isPlaying.value = false
          isLoading.value = false
        })
      }
    }
    _cacheState()
  }

  function seekTo(time: number) {
    if (audioElement.value) {
      audioElement.value.currentTime = time
      currentTime.value = time  // 立即更新 store，不等 timeupdate 异步事件
    }
  }
  function setVolume(vol: number) {
    volume.value = Math.max(0, Math.min(1, vol))
    if (audioElement.value) audioElement.value.volume = volume.value
  }
  function toggleMute() {
    isMuted.value = !isMuted.value
    if (audioElement.value) audioElement.value.volume = isMuted.value ? 0 : volume.value
  }
  function setPlaybackMode(mode: PlaybackMode) { playbackMode.value = mode }
  function addToQueue(song: Song) { queue.value.push(song) }
  function removeFromQueue(index: number) { queue.value.splice(index, 1); _cacheState() }
  function clearQueue() { queue.value = []; history.value = []; _cacheState() }

  // ── localStorage 缓存：刷新后恢复播放状态 ──

  function _cacheState() {
    try {
      localStorage.setItem(PLAYER_CACHE_KEY, JSON.stringify({
        currentSong: currentSong.value,
        queue: queue.value,
        playUrl: playUrl.value,
        playReason: playReason.value,
        isPlaylistMode: isPlaylistMode.value,
        cachedAt: Date.now(),
      }))
    } catch { /* localStorage 满时静默忽略 */ }
  }

  /** 页面刷新后从 localStorage 恢复播放状态（URL 可能已过期，但界面不空白） */
  function restoreFromCache(): boolean {
    try {
      const raw = localStorage.getItem(PLAYER_CACHE_KEY)
      if (!raw) return false
      const data = JSON.parse(raw)
      if (Date.now() - data.cachedAt > PLAYER_CACHE_TTL_MS) return false
      currentSong.value = data.currentSong || null
      queue.value = data.queue || []
      playUrl.value = data.playUrl || ''
      playReason.value = data.playReason || ''
      isPlaylistMode.value = data.isPlaylistMode || false
      isPlaying.value = false  // 不自动播放（URL 可能已失效）
      isLoading.value = false
      return true
    } catch { return false }
  }

  function toggleLike() {
    if (!currentSong.value) return
    const id = currentSong.value.id
    const nowLiked = !likedSongIds.value.has(id)
    if (nowLiked) { likedSongIds.value.add(id) }
    else { likedSongIds.value.delete(id) }
    likedSongIds.value = new Set(likedSongIds.value)
    saveLikedSongs()
    // 通知后端：喜欢/取消喜欢
    sendFeedback({ song_id: id, action: nowLiked ? 'favorite' : 'like' }).catch(() => {})
  }

  /** 上报播放结束（自然结束 / 播放出错），通知后端推进队列 */
  function reportPlayEnd() {
    if (!currentSong.value) return
    wsSend?.('status', 'player_event', {
      event: 'play_end',
      song_id: currentSong.value.id,
      played_ms: Math.round(currentTime.value * 1000),
    })
  }

  /** 点踩：dislike */
  function dislike() {
    if (!currentSong.value) return
    const id = currentSong.value.id
    likedSongIds.value.delete(id)
    likedSongIds.value = new Set(likedSongIds.value)
    saveLikedSongs()
    sendFeedback({ song_id: id, action: 'dislike' }).catch(() => {})
    next() // 不喜欢就切歌
  }

  function formatTime(seconds: number): string {
    if (!isFinite(seconds)) return '00:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  return {
    currentSong, playUrl, playReason, queue, history, isPlaying, volume, currentTime, duration,
    playbackMode, isMuted, isLoading, currentExpression,
    progress, currentSongIndex, hasNext, hasPrevious, isLiked, formattedProgress, formattedDuration,
    isPlaylistMode, setPlaylistMode,
    initAudio, playSong, playPlaylist, togglePlay, next, prev, seekTo, setVolume, toggleMute,
    setPlaybackMode, addToQueue, removeFromQueue, clearQueue, toggleLike, dislike, reportPlayEnd, restoreFromCache,
    onSongEnded,
  }
})
