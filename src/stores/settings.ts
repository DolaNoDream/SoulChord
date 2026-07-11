import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { updateSettings } from '@/api/agent'

export type ThemeMode = 'dark' | 'auto'

export const useSettingsStore = defineStore('settings', () => {
  // ========== 状态 ==========
  const theme = ref<ThemeMode>('dark')
  const alwaysOnTop = ref(true)
  const autoplayOnLaunch = ref(true)
  const showDJEmotion = ref(true)
  const language = ref<'zh-CN' | 'en-US'>('zh-CN')
  const deepseekApiKey = ref('')

  const isDark = computed(() => theme.value === 'dark')

  // ========== 方法 ==========
  function loadFromStorage() {
    try {
      const stored = localStorage.getItem('soulchord-settings')
      if (stored) {
        const data = JSON.parse(stored)
        Object.assign({ theme, alwaysOnTop, autoplayOnLaunch, showDJEmotion, language, deepseekApiKey }, data)
      }
    } catch { /* ignore */ }
  }

  function persistToStorage() {
    localStorage.setItem('soulchord-settings', JSON.stringify({
      theme: theme.value, alwaysOnTop: alwaysOnTop.value, autoplayOnLaunch: autoplayOnLaunch.value,
      showDJEmotion: showDJEmotion.value, language: language.value, deepseekApiKey: deepseekApiKey.value,
    }))
  }

  /** 同步置顶到 Electron 窗口 */
  function syncAlwaysOnTop() {
    if (window.electronAPI) window.electronAPI.setAlwaysOnTop(alwaysOnTop.value)
  }

  /** 同步设置到后端 */
  async function syncToBackend() {
    try {
      await updateSettings({ deepseek_api_key: deepseekApiKey.value, language: language.value })
    } catch { /* 后端不可用时忽略 */ }
  }

  // 自动持久化
  watch([theme, alwaysOnTop, autoplayOnLaunch, showDJEmotion, language, deepseekApiKey], () => persistToStorage())

  // 启动时加载
  loadFromStorage()

  return {
    theme, alwaysOnTop, autoplayOnLaunch, showDJEmotion, language, deepseekApiKey,
    isDark,
    syncAlwaysOnTop, syncToBackend, loadFromStorage,
    setTheme: (m: ThemeMode) => { theme.value = m },
  }
})
