import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserProfile, Memory, AgentInfo } from '@/types/user'
import { fetchInit, updateUserProfile, queryMemory } from '@/api/agent'

export const useUserStore = defineStore('user', () => {
  // ========== 状态 ==========
  const profile = ref<UserProfile | null>(null)
  const memories = ref<Memory[]>([])
  const agentInfo = ref<AgentInfo | null>(null)
  const isProfileLoaded = ref(false)
  const isAnalyzing = ref(false)

  // ========== 计算属性 ==========
  const topGenres = computed(() => profile.value?.favorite_genres?.slice(0, 5) ?? [])
  const topArtists = computed(() => profile.value?.favorite_artists?.slice(0, 5) ?? [])
  const nickname = computed(() => profile.value?.name ?? '音乐探索者')

  // ========== 方法 ==========

  /** 启动时调用：拉取 init 数据（用户画像 + Agent 信息） */
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

  /** 更新用户偏好 */
  async function updatePreferences(prefs: {
    favorite_genres?: string[]
    favorite_artists?: string[]
    disliked_genres?: string[]
  }): Promise<void> {
    await updateUserProfile(prefs)
    if (profile.value) {
      if (prefs.favorite_genres) profile.value.favorite_genres = prefs.favorite_genres
      if (prefs.favorite_artists) profile.value.favorite_artists = prefs.favorite_artists
      if (prefs.disliked_genres) profile.value.disliked_genres = prefs.disliked_genres
    }
  }

  /** 加载 Memory */
  async function loadMemories(): Promise<void> {
    try {
      const data = await queryMemory()
      memories.value = data.memories
    } catch { /* 静默失败 */ }
  }

  /** 修改昵称 */
  async function updateNickname(name: string): Promise<void> {
    if (!profile.value) {
      profile.value = { name, favorite_genres: [], favorite_artists: [], disliked_genres: [], created_at: Date.now() }
    } else {
      profile.value.name = name
    }
    localStorage.setItem('soulchord-nickname', name)
    try { await updateUserProfile({}) } catch { /* 离线时忽略 */ }
  }

  /** 更换头像（本地持久化） */
  function updateAvatar(dataUrl: string) {
    localStorage.setItem('soulchord-avatar', dataUrl)
    // 头像仅本地存储，后端不管理
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
    profile, memories, agentInfo, isProfileLoaded, isAnalyzing,
    topGenres, topArtists, nickname,
    loadInit, updatePreferences, loadMemories, updateNickname, updateAvatar,
    getLocalAvatar, getLocalNickname,
  }
})
