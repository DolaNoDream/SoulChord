import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

export type ThemeMode = 'dark' | 'auto'
export type WindowMode = 'full' | 'mini'

export const useSettingsStore = defineStore('settings', () => {
  // ========== 状态 ==========
  const theme = ref<ThemeMode>('dark')
  const windowMode = ref<WindowMode>('full')
  const alwaysOnTop = ref(true)
  const audioQuality = ref<'standard' | 'high'>('standard')
  const autoplayOnLaunch = ref(true)
  const showDJEmotion = ref(true)
  const language = ref<'zh-CN' | 'en-US'>('zh-CN')

  // ========== 计算属性 ==========
  const isDark = computed(() => {
    if (theme.value === 'auto') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    return theme.value === 'dark'
  })

  const isMiniMode = computed(() => windowMode.value === 'mini')

  // ========== 方法 ==========

  /** 切换迷你模式 */
  function toggleMiniMode() {
    windowMode.value = windowMode.value === 'mini' ? 'full' : 'mini'
    // 通过 Electron API 切换窗口尺寸
    window.electronAPI?.toggleMiniMode()
  }

  /** 切换始终置顶 */
  function toggleAlwaysOnTop() {
    alwaysOnTop.value = !alwaysOnTop.value
    window.electronAPI?.setAlwaysOnTop(alwaysOnTop.value)
  }

  /** 切换主题 */
  function setTheme(mode: ThemeMode) {
    theme.value = mode
  }

  /** 重置默认设置 */
  function resetToDefaults() {
    theme.value = 'dark'
    windowMode.value = 'full'
    alwaysOnTop.value = true
    audioQuality.value = 'standard'
    autoplayOnLaunch.value = true
    showDJEmotion.value = true
    language.value = 'zh-CN'
  }

  /** 从持久化存储加载 */
  function loadFromStorage() {
    try {
      const stored = localStorage.getItem('soulchord-settings')
      if (stored) {
        const data = JSON.parse(stored)
        Object.assign({ theme, windowMode, alwaysOnTop, audioQuality, autoplayOnLaunch, showDJEmotion, language }, data)
      }
    } catch {
      // 忽略解析错误，使用默认值
    }
  }

  /** 持久化到 localStorage */
  function persistToStorage() {
    const data = {
      theme: theme.value,
      alwaysOnTop: alwaysOnTop.value,
      audioQuality: audioQuality.value,
      autoplayOnLaunch: autoplayOnLaunch.value,
      showDJEmotion: showDJEmotion.value,
      language: language.value,
    }
    localStorage.setItem('soulchord-settings', JSON.stringify(data))
  }

  // 监听所有设置变化，自动保存
  watch(
    [theme, alwaysOnTop, audioQuality, autoplayOnLaunch, showDJEmotion, language],
    () => persistToStorage(),
    { deep: false }
  )

  // 启动时加载
  loadFromStorage()

  return {
    // state
    theme,
    windowMode,
    alwaysOnTop,
    audioQuality,
    autoplayOnLaunch,
    showDJEmotion,
    language,
    // computed
    isDark,
    isMiniMode,
    // actions
    toggleMiniMode,
    toggleAlwaysOnTop,
    setTheme,
    resetToDefaults,
    loadFromStorage,
    persistToStorage,
  }
})
