import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Song, PlaybackMode } from '@/types/music'
import { sendFeedback } from '@/api/agent'

/** WS 发送函数的全局引用（由 useWebSocket 注入） */
let wsSend: ((type: string, subtype: string, payload: unknown) => void) | null = null
export function setWsSend(fn: ((type: string, subtype: string, payload: unknown) => void) | null) { wsSend = fn }

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
    audio.volume = volume.value
    audio.addEventListener('timeupdate', () => { currentTime.value = audio.currentTime })
    audio.addEventListener('loadedmetadata', () => { duration.value = audio.duration })
    audio.addEventListener('ended', () => {
      wsSend?.('status', 'player_event', { event: 'play_end', song_id: currentSong.value?.id, played_ms: Math.round(currentTime.value * 1000) })
      next()
    })
    audio.addEventListener('waiting', () => { isLoading.value = true })
    audio.addEventListener('canplay', () => { isLoading.value = false })
  }

  /** 播放歌曲（新版：Song + play_url 分开） */
  function playSong(song: Song, url: string, reason?: string) {
    const prevId = currentSong.value?.id
    if (currentSong.value && currentSong.value.id !== song.id) {
      history.value.push(currentSong.value)
    }
    currentSong.value = song
    playUrl.value = url
    playReason.value = reason || ''
    isPlaying.value = true
    isLoading.value = true
    if (audioElement.value) {
      audioElement.value.src = url
      audioElement.value.play().catch(() => {})
    }
    // 上报：新歌开始
    wsSend?.('status', 'player_event', { event: 'play_start', song_id: song.id, prev_song_id: prevId })
  }

  function playPlaylist(songs: Song[], startIndex = 0) {
    queue.value = songs
    if (songs.length > 0 && startIndex < songs.length) {
      // playSong needs url — use first song and fetch URL
      // In WS flow, music.play comes with play_url already
    }
  }

  function togglePlay() {
    if (!audioElement.value) return
    if (isPlaying.value) {
      audioElement.value.pause(); isPlaying.value = false
      wsSend?.('status', 'player_event', { event: 'pause', song_id: currentSong.value?.id })
    } else {
      audioElement.value.play().then(() => { isPlaying.value = true }).catch(() => {})
      wsSend?.('status', 'player_event', { event: 'resume', song_id: currentSong.value?.id })
    }
  }

  function next() {
    if (!currentSong.value || queue.value.length === 0) return
    if (playbackMode.value === 'singleLoop') {
      if (audioElement.value) { audioElement.value.currentTime = 0; audioElement.value.play() }
      return
    }
    let nextIndex: number
    if (playbackMode.value === 'random') { nextIndex = Math.floor(Math.random() * queue.value.length) }
    else { nextIndex = (currentSongIndex.value + 1) % queue.value.length }
    if (currentSong.value) {
      sendFeedback({ song_id: currentSong.value.id, action: 'skip' }).catch(() => {})
      wsSend?.('status', 'player_event', { event: 'skip', song_id: currentSong.value.id, reason: 'user_next' })
      history.value.push(currentSong.value)
    }
  }

  function prev() {
    if (currentTime.value > 3 && audioElement.value) { audioElement.value.currentTime = 0; return }
    const prevSong = history.value.pop()
    if (prevSong) {
      if (currentSong.value) { queue.value.unshift(currentSong.value) }
      currentSong.value = prevSong
      isPlaying.value = true
    }
  }

  function seekTo(time: number) { if (audioElement.value) audioElement.value.currentTime = time }
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
  function removeFromQueue(index: number) { queue.value.splice(index, 1) }
  function clearQueue() { queue.value = []; history.value = [] }

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
    initAudio, playSong, playPlaylist, togglePlay, next, prev, seekTo, setVolume, toggleMute,
    setPlaybackMode, addToQueue, removeFromQueue, clearQueue, toggleLike, dislike,
  }
})
