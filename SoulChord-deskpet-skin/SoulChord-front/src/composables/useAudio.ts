/**
 * 音频播放逻辑
 * 封装 HTMLAudioElement，与 Pinia playerStore 同步状态
 */
import { ref, onUnmounted } from 'vue'
import { usePlayerStore } from '@/stores/player'

export function useAudio() {
  const playerStore = usePlayerStore()
  const audio = ref<HTMLAudioElement | null>(null)
  const isReady = ref(false)

  /** 创建并初始化音频元素 */
  function createAudio(): HTMLAudioElement {
    if (audio.value) return audio.value

    const el = new Audio()
    el.preload = 'auto'
    el.crossOrigin = 'anonymous'
    el.volume = playerStore.volume

    // 事件绑定
    el.addEventListener('loadedmetadata', () => {
      playerStore.duration = el.duration
      isReady.value = true
    })

    el.addEventListener('timeupdate', () => {
      playerStore.currentTime = el.currentTime
    })

    el.addEventListener('ended', () => {
      playerStore.onSongEnded()
    })

    el.addEventListener('waiting', () => {
      playerStore.isLoading = true
    })

    el.addEventListener('canplay', () => {
      playerStore.isLoading = false
    })

    el.addEventListener('play', () => {
      playerStore.isPlaying = true
    })

    el.addEventListener('pause', () => {
      playerStore.isPlaying = false
    })

    el.addEventListener('error', (e) => {
      console.error('Audio playback error, skipping to next:', e)
      playerStore.isLoading = false
      playerStore.isPlaying = false
      // 音频加载失败（CDN 返回 HTML / URL 过期）→ 自动切到下一首
      // 不发 WS skip（不是用户行为），改发 play_end 通知后端推进队列
      const failedId = playerStore.currentSong?.id
      if (failedId) {
        playerStore.queue = playerStore.queue.filter(s => s.id !== failedId)
      }
      // 先通知后端此歌结束，再本地推进（play_end → 后端消费队列）
      playerStore.reportPlayEnd()
      playerStore.next(true)  // fromEnded=true → 本地推进，不发 skip 反馈
    })

    audio.value = el
    playerStore.initAudio(el)
    return el
  }

  /** 加载音频源 */
  function load(url: string) {
    const el = audio.value ?? createAudio()
    el.src = url
    el.load()
  }

  /** 播放 */
  function play() {
    const el = audio.value ?? createAudio()
    el.play().catch(err => {
      console.warn('Playback prevented:', err)
    })
  }

  /** 暂停 */
  function pause() {
    audio.value?.pause()
  }

  /** 跳转 */
  function seek(time: number) {
    if (audio.value) {
      audio.value.currentTime = time
    }
  }

  /** 设置音量 */
  function setVolume(vol: number) {
    if (audio.value) {
      audio.value.volume = Math.max(0, Math.min(1, vol))
    }
  }

  /** 销毁 */
  function destroy() {
    if (audio.value) {
      audio.value.pause()
      audio.value.src = ''
      audio.value.load()
      audio.value = null
    }
    isReady.value = false
  }

  // 组件卸载时自动清理
  onUnmounted(() => {
    destroy()
  })

  // 创建初始音频元素
  createAudio()

  return {
    audio,
    isReady,
    load,
    play,
    pause,
    seek,
    setVolume,
    destroy,
  }
}
