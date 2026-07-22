import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { updateSettings } from '@/api/agent'

export type ThemeMode = 'dark' | 'auto'

export const useSettingsStore = defineStore('settings', () => {
  // ========== 状态 ==========
  const theme = ref<ThemeMode>('dark')
  const alwaysOnTop = ref(true)
  const language = ref<'zh-CN' | 'en-US'>('zh-CN')
  const llmApiKey = ref('')
  // 网易云登录状态
  const neteaseLoginStatus = ref(false)
  const neteaseNickname = ref('')

  const isDark = computed(() => theme.value === 'dark')
  /** 是否配置了 LLM APIKey（未配置时 AI 对话、歌单画像分析禁用） */
  const hasLlmKey = computed(() => llmApiKey.value.trim().length > 0)
  /** 是否登录了网易云（未登录时歌单导入、音乐播放禁用） */
  const hasNeteaseLogin = computed(() => neteaseLoginStatus.value)

  /** 从后端 GET /api/init 的 settings 字段加载 */
  function loadFromBackend(backendSettings: Record<string, unknown>) {
    if (typeof backendSettings.llm_apikey === 'string') llmApiKey.value = backendSettings.llm_apikey
    if (backendSettings.language) language.value = backendSettings.language as typeof language.value
    persistToStorage()
  }

  /** 加载网易云登录状态（来自 init/neteasestatus 接口） */
  function setNeteaseStatus(status: boolean, nickname?: string) {
    neteaseLoginStatus.value = status
    if (nickname !== undefined) neteaseNickname.value = nickname
    persistToStorage()
  }

  function loadFromStorage() {
    try {
      const stored = localStorage.getItem('soulchord-settings')
      if (stored) {
        const data = JSON.parse(stored)
        if (data.llmApiKey) llmApiKey.value = data.llmApiKey
        if (data.theme) theme.value = data.theme
        if (data.alwaysOnTop !== undefined) alwaysOnTop.value = data.alwaysOnTop
        if (data.language) language.value = data.language
        if (data.neteaseLoginStatus !== undefined) neteaseLoginStatus.value = data.neteaseLoginStatus
        if (data.neteaseNickname) neteaseNickname.value = data.neteaseNickname
      }
    } catch { /* ignore */ }
  }

  function persistToStorage() {
    localStorage.setItem('soulchord-settings', JSON.stringify({
      theme: theme.value, alwaysOnTop: alwaysOnTop.value,
      language: language.value, llmApiKey: llmApiKey.value,
      neteaseLoginStatus: neteaseLoginStatus.value,
      neteaseNickname: neteaseNickname.value,
    }))
  }

  function syncAlwaysOnTop() {
    if (window.electronAPI) window.electronAPI.setAlwaysOnTop(alwaysOnTop.value)
  }

  /** 同步到后端 PUT /api/settings（增量更新） */
  async function syncToBackend() {
    try {
      await updateSettings({
        llm_apikey: llmApiKey.value,
      })
    } catch { /* 后端不可用时忽略 */ }
  }

  watch([theme, alwaysOnTop, language, llmApiKey], () => persistToStorage())

  loadFromStorage()

  return {
    theme, alwaysOnTop, language, llmApiKey,
    neteaseLoginStatus, neteaseNickname,
    isDark, hasLlmKey, hasNeteaseLogin,
    syncAlwaysOnTop, syncToBackend, loadFromStorage, loadFromBackend,
    setNeteaseStatus,
    setTheme: (m: ThemeMode) => { theme.value = m },
  }
})
