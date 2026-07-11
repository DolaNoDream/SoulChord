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
    syncAlwaysOnTop, syncToBackend, loadFromStorage,
    setTheme: (m: ThemeMode) => { theme.value = m },
  }
})
