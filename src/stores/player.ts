import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Song, PlaybackMode, EmotionType } from '@/types/music'
import { sendSongFeedback } from '@/api/agent'

export const usePlayerStore = defineStore('player', () => {
  // ========== 状态 ==========
  const currentSong = ref<Song | null>(null)
  const queue = ref<Song[]>([])
  const history = ref<Song[]>([])
  const isPlaying = ref(false)
  const volume = ref(0.7)
  const currentTime = ref(0)
  const duration = ref(0)
  const playbackMode = ref<PlaybackMode>('sequential')
  const isMuted = ref(false)
  const isLoading = ref(false)
  const audioElement = ref<HTMLAudioElement | null>(null)
  // 喜欢的歌曲 ID 集合（持久化到 localStorage）
  const likedSongIds = ref<Set<string>>(loadLikedSongs())
  const dislikedSongIds = ref<Set<string>>(new Set())

  /** 从 localStorage 加载喜欢列表 */
  function loadLikedSongs(): Set<string> {
    try {
      const data = localStorage.getItem('soulchord-liked')
      return data ? new Set(JSON.parse(data)) : new Set()
    } catch { return new Set() }
  }

  /** 持久化喜欢列表 */
  function saveLikedSongs() {
    localStorage.setItem('soulchord-liked', JSON.stringify([...likedSongIds.value]))
  }

  // ========== 计算属性 ==========
  const progress = computed(() => {
    if (duration.value === 0) return 0
    return (currentTime.value / duration.value) * 100
  })

  const currentSongIndex = computed(() => {
    if (!currentSong.value) return -1
    return queue.value.findIndex(s => s.id === currentSong.value!.id)
  })

  const hasNext = computed(() => {
    if (playbackMode.value === 'singleLoop') return true
    return currentSongIndex.value < queue.value.length - 1
  })

  const hasPrevious = computed(() => {
    return history.value.length > 0 || currentTime.value > 3
  })

  const currentEmotion = computed<EmotionType>(() => {
    return currentSong.value?.emotion ?? 'neutral'
  })

  const formattedProgress = computed(() => {
    return formatTime(currentTime.value)
  })

  const formattedDuration = computed(() => {
    return formatTime(duration.value)
  })

  // ========== 方法 ==========

  /** 初始化音频元素 */
  function initAudio(audio: HTMLAudioElement) {
    audioElement.value = audio
    audio.volume = volume.value

    audio.addEventListener('timeupdate', () => {
      currentTime.value = audio.currentTime
    })
    audio.addEventListener('loadedmetadata', () => {
      duration.value = audio.duration
    })
    audio.addEventListener('ended', () => {
      next()
    })
    audio.addEventListener('waiting', () => {
      isLoading.value = true
    })
    audio.addEventListener('canplay', () => {
      isLoading.value = false
    })
  }

  /** 播放指定歌曲 */
  function playSong(song: Song) {
    if (currentSong.value && currentSong.value.id !== song.id) {
      history.value.push(currentSong.value)
    }
    currentSong.value = song
    isPlaying.value = true
    isLoading.value = true

    if (audioElement.value) {
      audioElement.value.src = song.audioUrl
      audioElement.value.play().catch(() => {
        // 浏览器自动播放策略可能阻止
      })
    }
  }

  /** 播放整个歌单 */
  function playPlaylist(songs: Song[], startIndex = 0) {
    queue.value = songs
    if (songs.length > 0 && startIndex < songs.length) {
      playSong(songs[startIndex])
    }
  }

  /** 播放/暂停切换 */
  function togglePlay() {
    if (!audioElement.value) return

    if (isPlaying.value) {
      audioElement.value.pause()
      isPlaying.value = false
    } else {
      audioElement.value.play().then(() => {
        isPlaying.value = true
      }).catch(() => {
        // 自动播放被阻止
      })
    }
  }

  /** 下一首 */
  function next() {
    if (!currentSong.value || queue.value.length === 0) return

    if (playbackMode.value === 'singleLoop') {
      if (audioElement.value) {
        audioElement.value.currentTime = 0
        audioElement.value.play()
      }
      return
    }

    let nextIndex: number
    if (playbackMode.value === 'random') {
      nextIndex = Math.floor(Math.random() * queue.value.length)
    } else {
      nextIndex = (currentSongIndex.value + 1) % queue.value.length
    }

    if (currentSong.value) {
      history.value.push(currentSong.value)
    }
    playSong(queue.value[nextIndex])
  }

  /** 上一首 */
  function prev() {
    // 播放超过3秒，重播当前歌曲
    if (currentTime.value > 3 && audioElement.value) {
      audioElement.value.currentTime = 0
      return
    }

    // 从历史记录恢复
    const prevSong = history.value.pop()
    if (prevSong) {
      if (currentSong.value) {
        queue.value.unshift(currentSong.value)
      }
      currentSong.value = prevSong
      isPlaying.value = true
      if (audioElement.value) {
        audioElement.value.src = prevSong.audioUrl
        audioElement.value.play().catch(() => {})
      }
    }
  }

  /** 跳转到指定时间 */
  function seekTo(time: number) {
    if (audioElement.value) {
      audioElement.value.currentTime = time
    }
  }

  /** 设置音量 */
  function setVolume(vol: number) {
    volume.value = Math.max(0, Math.min(1, vol))
    if (audioElement.value) {
      audioElement.value.volume = volume.value
    }
    if (volume.value === 0) {
      isMuted.value = true
    }
  }

  /** 静音切换 */
  function toggleMute() {
    isMuted.value = !isMuted.value
    if (audioElement.value) {
      audioElement.value.volume = isMuted.value ? 0 : volume.value
    }
  }

  /** 设置播放模式 */
  function setPlaybackMode(mode: PlaybackMode) {
    playbackMode.value = mode
  }

  /** 添加到队列 */
  function addToQueue(song: Song) {
    queue.value.push(song)
  }

  /** 从队列移除 */
  function removeFromQueue(index: number) {
    queue.value.splice(index, 1)
  }

  /** 清空队列 */
  function clearQueue() {
    queue.value = []
    history.value = []
  }

  /** 当前歌曲是否已喜欢 */
  const isLiked = computed(() => {
    return currentSong.value ? likedSongIds.value.has(currentSong.value.id) : false
  })

  /** 当前歌曲是否已踩 */
  const isDisliked = computed(() => {
    return currentSong.value ? dislikedSongIds.value.has(currentSong.value.id) : false
  })

  /** 切换喜欢/取消喜欢 */
  function toggleLike() {
    if (!currentSong.value) return
    const id = currentSong.value.id
    if (likedSongIds.value.has(id)) {
      likedSongIds.value.delete(id)
    } else {
      likedSongIds.value.add(id)
      dislikedSongIds.value.delete(id) // 喜欢时取消踩
    }
    likedSongIds.value = new Set(likedSongIds.value) // 触发响应式
    saveLikedSongs()
    sendSongFeedback(id, 'like').catch(() => {})
  }

  /** 切换踩/取消踩 */
  function toggleDislike() {
    if (!currentSong.value) return
    const id = currentSong.value.id
    if (dislikedSongIds.value.has(id)) {
      dislikedSongIds.value.delete(id)
    } else {
      dislikedSongIds.value.add(id)
      likedSongIds.value.delete(id) // 踩时取消喜欢
    }
    dislikedSongIds.value = new Set(dislikedSongIds.value)
    sendSongFeedback(id, 'dislike').catch(() => {})
  }

  /** 格式化时间 */
  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  return {
    // state
    currentSong,
    queue,
    history,
    isPlaying,
    volume,
    currentTime,
    duration,
    playbackMode,
    isMuted,
    isLoading,
    // computed
    progress,
    currentSongIndex,
    hasNext,
    hasPrevious,
    currentEmotion,
    formattedProgress,
    formattedDuration,
    // actions
    initAudio,
    playSong,
    playPlaylist,
    togglePlay,
    next,
    prev,
    seekTo,
    setVolume,
    toggleMute,
    setPlaybackMode,
    addToQueue,
    removeFromQueue,
    clearQueue,
    isLiked,
    isDisliked,
    toggleLike,
    toggleDislike,
  }
})
