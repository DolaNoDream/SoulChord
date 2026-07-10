/**
 * Electron API 封装
 * 在浏览器环境下优雅降级
 */
import { ref, onMounted, onUnmounted } from 'vue'

/** 是否在 Electron 环境中运行 */
export const isElectron = ref(typeof window !== 'undefined' && !!window.electronAPI)

export function useElectron() {
  const isMaximized = ref(false)
  const isFocused = ref(true)

  /** 最小化窗口 */
  function minimize() {
    window.electronAPI?.minimizeWindow()
  }

  /** 最大化/还原窗口 */
  async function maximize() {
    const result = await window.electronAPI?.maximizeWindow()
    if (typeof result === 'boolean') {
      isMaximized.value = result
    } else {
      isMaximized.value = !isMaximized.value
    }
  }

  /** 关闭窗口 */
  function close() {
    window.electronAPI?.closeWindow()
  }

  /** 切换迷你模式 */
  function toggleMiniMode() {
    window.electronAPI?.toggleMiniMode()
  }

  /** 设置始终置顶 */
  function setAlwaysOnTop(flag: boolean) {
    window.electronAPI?.setAlwaysOnTop(flag)
  }

  /** 更新媒体会话元数据（OS 媒体控件） */
  function updateMediaMetadata(metadata: {
    title: string
    artist: string
    album?: string
    artwork?: string
  }) {
    // 浏览器 Media Session API
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: metadata.title,
        artist: metadata.artist,
        album: metadata.album ?? '',
        artwork: metadata.artwork
          ? [{ src: metadata.artwork, sizes: '300x300', type: 'image/jpeg' }]
          : [],
      })

      // 设置媒体会话操作处理器
      navigator.mediaSession.setActionHandler('play', () => {
        // 由 playerStore 处理
      })
      navigator.mediaSession.setActionHandler('pause', () => {
        // 由 playerStore 处理
      })
      navigator.mediaSession.setActionHandler('previoustrack', () => {
        // 由 playerStore 处理
      })
      navigator.mediaSession.setActionHandler('nexttrack', () => {
        // 由 playerStore 处理
      })
    }

    // Electron IPC
    window.electronAPI?.setMediaMetadata({
      title: metadata.title,
      artist: metadata.artist,
      album: metadata.album,
      artwork: metadata.artwork
        ? [{ src: metadata.artwork, sizes: '300x300', type: 'image/jpeg' }]
        : [],
    })
  }

  // 窗口焦点事件
  onMounted(() => {
    window.electronAPI?.onWindowBlur(() => {
      isFocused.value = false
    })
    window.electronAPI?.onWindowFocus(() => {
      isFocused.value = true
    })
  })

  return {
    isElectron,
    isMaximized,
    isFocused,
    minimize,
    maximize,
    close,
    toggleMiniMode,
    setAlwaysOnTop,
    updateMediaMetadata,
  }
}
