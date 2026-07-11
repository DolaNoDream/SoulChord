import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { updateSettings } from '@/api/agent'

export type ThemeMode = 'dark' | 'auto'

export const useSettingsStore = defineStore('settings', () => {
  // ========== 状态 ==========
  const theme = ref<ThemeMode>('dark')
  const alwaysOnTop = ref(true)
  const language = ref<'zh-CN' | 'en-US'>('zh-CN')
  const deepseekApiKey = ref('')
  // 对齐 API 规范的三个 settings 字段
  const djVoice = ref<'male_gentle' | 'female_warm' | 'male_lively'>('male_gentle')
  const autoGreet = ref(true)
  const persona = ref<'night_dj' | 'warm_companion' | 'energetic_jockey'>('night_dj')

  const isDark = computed(() => theme.value === 'dark')

  /** 从后端 GET /api/init 的 settings 字段加载（优先级高于 localStorage） */
  function loadFromBackend(backendSettings: Record<string, unknown>) {
    if (backendSettings.dj_voice) djVoice.value = backendSettings.dj_voice as typeof djVoice.value
    if (typeof backendSettings.auto_greet === 'boolean') autoGreet.value = backendSettings.auto_greet
    if (backendSettings.persona) persona.value = backendSettings.persona as typeof persona.value
    if (backendSettings.language) language.value = backendSettings.language as typeof language.value
    persistToStorage() // 同步到本地
  }

  function loadFromStorage() {
    try {
      const stored = localStorage.getItem('soulchord-settings')
      if (stored) {
        const data = JSON.parse(stored)
        Object.assign({ theme, alwaysOnTop, language, deepseekApiKey, djVoice, autoGreet, persona }, data)
      }
    } catch { /* ignore */ }
  }

  function persistToStorage() {
    localStorage.setItem('soulchord-settings', JSON.stringify({
      theme: theme.value, alwaysOnTop: alwaysOnTop.value,
      language: language.value, deepseekApiKey: deepseekApiKey.value,
      djVoice: djVoice.value, autoGreet: autoGreet.value, persona: persona.value,
    }))
  }

  function syncAlwaysOnTop() {
    if (window.electronAPI) window.electronAPI.setAlwaysOnTop(alwaysOnTop.value)
  }

  /** 同步到后端 PUT /api/settings（增量更新） */
  async function syncToBackend() {
    try {
      await updateSettings({
        deepseek_api_key: deepseekApiKey.value,
        language: language.value,
        dj_voice: djVoice.value,
        auto_greet: autoGreet.value,
        persona: persona.value,
      })
    } catch { /* 后端不可用时忽略 */ }
  }

  watch([theme, alwaysOnTop, language, deepseekApiKey, djVoice, autoGreet, persona], () => persistToStorage())

  loadFromStorage()

  return {
    theme, alwaysOnTop, language, deepseekApiKey, djVoice, autoGreet, persona,
    isDark,
    syncAlwaysOnTop, syncToBackend, loadFromStorage, loadFromBackend,
    setTheme: (m: ThemeMode) => { theme.value = m },
  }
})
