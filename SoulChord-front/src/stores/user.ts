import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserProfits, AgentInfo } from '@/types/user'
import { fetchInit, getUserProfile, updateUserBaseInfo, triggerAnalyze } from '@/api/agent'

export const useUserStore = defineStore('user', () => {
  // ========== 状态 ==========
  const profile = ref<UserProfits | null>(null)
  const agentInfo = ref<AgentInfo | null>(null)
  const isProfileLoaded = ref(false)
  const isAnalyzing = ref(false)

  // ========== 计算属性 ==========
  const topGenres = computed(() => profile.value?.favorite_genres?.slice(0, 5) ?? [])
  const topArtists = computed(() => profile.value?.favorite_artists?.slice(0, 5) ?? [])
  const nickname = computed(() => profile.value?.nickname ?? '音乐探索者')
  const avatarUrl = computed(() => profile.value?.avatar_url ?? '')

  // ========== 方法 ==========

  /** 启动时调用：拉取 init 数据 */
  async function loadInit(): Promise<void> {
    isAnalyzing.value = true
    try {
      const data = await fetchInit()
      profile.value = data.user_profile
      agentInfo.value = data.agent
      isProfileLoaded.value = true
    } catch {
      // 后端不可用，静默失败
    } finally {
      isAnalyzing.value = false
    }
  }

  /** 加载用户完整画像（GET /api/user/profile） */
  async function loadProfile(): Promise<void> {
    try {
      const p = await getUserProfile()
      profile.value = p
      isProfileLoaded.value = true
    } catch { /* 静默失败 */ }
  }

  /** 手动触发AI画像分析（POST /api/user/analyze） */
  async function requestAnalyze(): Promise<{ update_at: number } | null> {
    isAnalyzing.value = true
    try {
      const result = await triggerAnalyze()
      // 分析完成后自动刷新画像
      await loadProfile()
      return result
    } catch {
      return null
    } finally {
      isAnalyzing.value = false
    }
  }

  /** 修改昵称/头像（PUT /api/user/baseinfo） */
  async function updateBaseInfo(nickname?: string, avatarUrl?: string): Promise<void> {
    try {
      await updateUserBaseInfo({ nickname, avatar_url: avatarUrl })
      if (profile.value) {
        if (nickname) profile.value.nickname = nickname
        if (avatarUrl) profile.value.avatar_url = avatarUrl
      }
    } catch { /* 静默失败 */ }
  }

  /** 更新本地昵称 */
  async function updateNickname(name: string): Promise<void> {
    if (!profile.value) {
      profile.value = {
        nickname: name, avatar_url: '',
        favorite_genres: [], favorite_artists: [], disliked_genres: [],
        music_preference_desc: '', AI_conclusion: '', update_at: 0,  // 0 表示尚未进行 AI 分析
      }
    } else {
      profile.value.nickname = name
    }
    localStorage.setItem('soulchord-nickname', name)
    try { await updateUserBaseInfo({ nickname: name }) } catch { /* 离线时忽略 */ }
  }

  /** 更换头像（本地持久化） */
  function updateAvatar(dataUrl: string) {
    localStorage.setItem('soulchord-avatar', dataUrl)
    // 同步到后端
    updateUserBaseInfo({ avatar_url: dataUrl }).catch(() => {})
  }

  /** 本地缓存的头像 */
  function getLocalAvatar(): string {
    return localStorage.getItem('soulchord-avatar') ?? ''
  }

  /** 本地缓存的昵称 */
  function getLocalNickname(): string {
    return localStorage.getItem('soulchord-nickname') ?? '音乐探索者'
  }

  return {
    profile, agentInfo, isProfileLoaded, isAnalyzing,
    topGenres, topArtists, nickname, avatarUrl,
    loadInit, loadProfile, requestAnalyze, updateBaseInfo,
    updateNickname, updateAvatar, getLocalAvatar, getLocalNickname,
  }
})
