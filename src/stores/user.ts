import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserProfile, MusicDNA, GenrePreference, ArtistPreference } from '@/types/user'
import type { Song } from '@/types/music'
import { getUserProfile, analyzeProfile, updateProfile } from '@/api/agent'

export const useUserStore = defineStore('user', () => {
  // ========== 状态 ==========
  const profile = ref<UserProfile | null>(null)
  const musicDNA = ref<MusicDNA | null>(null)
  const isOnboarded = ref(false)
  const isAnalyzing = ref(false)
  const favoriteSongs = ref<Song[]>([])
  const isProfileLoaded = ref(false)

  // ========== 计算属性 ==========
  const topGenres = computed<GenrePreference[]>(() => {
    if (!musicDNA.value) return []
    return [...musicDNA.value.genres].sort((a, b) => b.weight - a.weight).slice(0, 5)
  })

  const topArtists = computed<ArtistPreference[]>(() => {
    if (!musicDNA.value) return []
    return [...musicDNA.value.artists].sort((a, b) => b.playCount - a.playCount).slice(0, 5)
  })

  const musicDNASummary = computed(() => {
    return musicDNA.value?.summary ?? '等待音乐DNA分析...'
  })

  /** 从 localStorage 构建兜底 profile */
  function buildLocalProfile(): UserProfile {
    return {
      id: 'local_user',
      nickname: localStorage.getItem('soulchord-nickname') ?? '音乐探索者',
      avatarUrl: localStorage.getItem('soulchord-avatar') ?? '',
      createdAt: new Date().toISOString(),
      totalSongsPlayed: 0,
      totalHoursListened: 0,
      favoriteTimeOfDay: '',
    }
  }

  // ========== 方法 ==========

  /** 启动时调用：从后端加载用户画像，失败则用 localStorage 兜底 */
  async function fetchProfile(): Promise<void> {
    if (isProfileLoaded.value) return
    isAnalyzing.value = true
    try {
      const data = await getUserProfile()
      profile.value = data.profile
      musicDNA.value = data.musicDNA
      isOnboarded.value = true
      // 同步后端数据到 localStorage 作为离线兜底
      if (data.profile.nickname) localStorage.setItem('soulchord-nickname', data.profile.nickname)
      if (data.profile.avatarUrl) localStorage.setItem('soulchord-avatar', data.profile.avatarUrl)
    } catch {
      // 后端不可用，从 localStorage 恢复
      profile.value = buildLocalProfile()
    } finally {
      isAnalyzing.value = false
      isProfileLoaded.value = true
    }
  }

  /** 导入喜欢的歌曲 -> 后端分析生成 musicDNA */
  async function importFavoriteSongs(songs: Song[]): Promise<void> {
    favoriteSongs.value = songs
    isAnalyzing.value = true
    try {
      const data = await analyzeProfile(songs)
      musicDNA.value = data.musicDNA
      profile.value = data.profile
      isOnboarded.value = true
    } catch {
      // 后端不可用时静默失败
    } finally {
      isAnalyzing.value = false
    }
  }

  /** 更换头像：更新 store + localStorage + 后端 */
  async function updateAvatar(dataUrl: string): Promise<void> {
    if (!profile.value) {
      profile.value = buildLocalProfile()
    }
    profile.value.avatarUrl = dataUrl
    localStorage.setItem('soulchord-avatar', dataUrl)
    // 异步同步到后端，失败不影响本地
    updateProfile({ avatarUrl: dataUrl }).catch(() => {})
  }

  /** 修改昵称：更新 store + localStorage + 后端 */
  async function updateNickname(name: string): Promise<void> {
    if (!profile.value) {
      profile.value = buildLocalProfile()
    }
    profile.value.nickname = name
    localStorage.setItem('soulchord-nickname', name)
    // 异步同步到后端
    updateProfile({ nickname: name }).catch(() => {})
  }

  /** 标记引导完成 */
  function completeOnboarding() {
    isOnboarded.value = true
  }

  return {
    profile, musicDNA, isOnboarded, isAnalyzing, favoriteSongs, isProfileLoaded,
    topGenres, topArtists, musicDNASummary,
    fetchProfile, importFavoriteSongs, updateAvatar, updateNickname, completeOnboarding,
  }
})
