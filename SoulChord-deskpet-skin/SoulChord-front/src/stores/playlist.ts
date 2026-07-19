import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Playlist, Song } from '@/types/music'
import {
  importPlaylist, getPlaylists, getPlaylistDetail,
  updatePlaylist, deletePlaylist,
} from '@/api/agent'
import { useUserStore } from './user'

export const usePlaylistStore = defineStore('playlist', () => {
  // ========== 状态 ==========
  const playlists = ref<Playlist[]>([])
  const selectedPlaylist = ref<Playlist | null>(null)
  const selectedSongs = ref<Song[]>([])
  const isLoading = ref(false)
  const isImporting = ref(false)
  const errorMsg = ref('')

  // ========== 计算属性 ==========
  const playlistCount = computed(() => playlists.value.length)
  const totalSongs = computed(() => playlists.value.reduce((sum, p) => sum + p.song_count, 0))

  // ========== 方法 ==========

  /** 加载全部歌单列表 */
  async function loadPlaylists(): Promise<void> {
    isLoading.value = true
    errorMsg.value = ''
    try {
      playlists.value = await getPlaylists()
    } catch (e) {
      errorMsg.value = e instanceof Error ? e.message : '加载歌单失败'
    } finally {
      isLoading.value = false
    }
  }

  /** 导入歌单（通过网易云分享链接） */
  async function doImport(url: string): Promise<boolean> {
    if (!url.trim()) return false
    isImporting.value = true
    errorMsg.value = ''
    try {
      await importPlaylist(url.trim())
      // 导入成功后刷新歌单列表 + 自动触发AI画像分析
      await loadPlaylists()
      const userStore = useUserStore()
      userStore.requestAnalyze().catch(() => {})
      return true
    } catch (e) {
      errorMsg.value = e instanceof Error ? e.message : '导入失败，请检查链接是否有效'
      return false
    } finally {
      isImporting.value = false
    }
  }

  /** 查看歌单详情（歌曲列表） */
  async function viewPlaylist(playlistId: string): Promise<void> {
    isLoading.value = true
    try {
      const detail = await getPlaylistDetail(playlistId)
      selectedPlaylist.value = detail.playlist
      selectedSongs.value = detail.songs
    } catch {
      errorMsg.value = '加载歌单详情失败'
    } finally {
      isLoading.value = false
    }
  }

  /** 修改歌单名称 */
  async function renamePlaylist(playlistId: string, name: string): Promise<void> {
    try {
      await updatePlaylist(playlistId, { name })
      const p = playlists.value.find(pl => pl.playlist_id === playlistId)
      if (p) p.name = name
      if (selectedPlaylist.value?.playlist_id === playlistId) {
        selectedPlaylist.value.name = name
      }
    } catch {
      errorMsg.value = '修改歌单名称失败'
    }
  }

  /** 删除歌单（删除后自动触发AI画像分析） */
  async function removePlaylist(playlistId: string): Promise<boolean> {
    try {
      await deletePlaylist(playlistId)
      playlists.value = playlists.value.filter(p => p.playlist_id !== playlistId)
      if (selectedPlaylist.value?.playlist_id === playlistId) {
        selectedPlaylist.value = null
        selectedSongs.value = []
      }
      // 删除后自动触发AI画像分析
      const userStore = useUserStore()
      userStore.requestAnalyze().catch(() => {})
      return true
    } catch {
      errorMsg.value = '删除歌单失败'
      return false
    }
  }

  /** 设置初始数据（来自 /api/init） */
  function setFromInit(data: Playlist[]) {
    playlists.value = data
  }

  return {
    playlists, selectedPlaylist, selectedSongs, isLoading, isImporting, errorMsg,
    playlistCount, totalSongs,
    loadPlaylists, doImport, viewPlaylist, renamePlaylist, removePlaylist,
    setFromInit,
  }
})
