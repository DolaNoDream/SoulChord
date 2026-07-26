<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePlaylistStore } from '@/stores/playlist'
import { useSettingsStore } from '@/stores/settings'
import { useUserStore } from '@/stores/user'
import { usePlayerStore } from '@/stores/player'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getNeteasePlaylists, getQqPlaylists, playPlaylistSong } from '@/api/agent'

const playlistStore = usePlaylistStore()
const settingsStore = useSettingsStore()
const userStore = useUserStore()

const showImportDialog = ref(false)
const importTab = ref<'account' | 'qq' | 'link'>('account')
const importUrl = ref('')
const qqIdInput = ref('')
const editingId = ref<string | null>(null)
const editingName = ref('')
const editInputRef = ref<HTMLInputElement | null>(null)
const showCreateDialog = ref(false)
const newPlaylistName = ref('')

// 网易云账号歌单列表
const neteasePlaylists = ref<Array<{
  netease_id: number
  name: string
  song_count: number
  cover_url: string
  description: string
  creator: string
}>>([])
const loadingNetease = ref(false)
const importingIds = ref<Set<number>>(new Set())

// QQ 歌单列表
const qqPlaylists = ref<Array<{
  id: number
  title: string
  picurl: string
  songnum: number
  desc: string
  nick: string
}>>([])
const loadingQq = ref(false)
const importingQqIds = ref<Set<number>>(new Set())

onMounted(() => {
  playlistStore.loadPlaylists()
})

async function openImportDialog() {
  if (!settingsStore.hasLlmKey) {
    ElMessage.warning('请先在设置中配置 LLM API Key')
    return
  }
  if (!settingsStore.hasNeteaseLogin && !settingsStore.hasQqLogin) {
    ElMessage.warning('请先登录网易云或 QQ 音乐账号')
    return
  }
  showImportDialog.value = true
  importTab.value = settingsStore.hasNeteaseLogin ? 'account' : 'qq'
  importUrl.value = ''
  qqIdInput.value = ''
  if (settingsStore.hasNeteaseLogin) {
    await loadNeteasePlaylists()
  }
  if (settingsStore.hasQqLogin) {
    await loadQqPlaylists()
  }
}

async function handleImportFromQq() {
  const qqId = qqIdInput.value.trim()
  if (!qqId) {
    ElMessage.warning('请输入 QQ 歌单 ID')
    return
  }
  const success = await playlistStore.doImportFromQq(qqId)
  if (success) {
    showImportDialog.value = false
    ElMessage.success('QQ 歌单导入成功，AI 正在分析你的音乐偏好...')
  } else {
    ElMessage.error(playlistStore.errorMsg || '导入失败，请检查歌单 ID 是否有效')
  }
}

async function handleImportFromQqList(qqId: number) {
  if (importingQqIds.value.has(qqId)) return
  importingQqIds.value.add(qqId)
  try {
    const success = await playlistStore.doImportFromQq(String(qqId))
    if (success) {
      ElMessage.success('QQ 歌单导入成功！')
    } else {
      ElMessage.error(playlistStore.errorMsg || '导入失败')
    }
  } finally {
    importingQqIds.value.delete(qqId)
  }
}

async function loadNeteasePlaylists() {
  loadingNetease.value = true
  try {
    const data = await getNeteasePlaylists()
    neteasePlaylists.value = data.playlists || []
  } catch {
    neteasePlaylists.value = []
  } finally {
    loadingNetease.value = false
  }
}

async function loadQqPlaylists() {
  loadingQq.value = true
  try {
    const data = await getQqPlaylists()
    qqPlaylists.value = data.playlists || []
  } catch {
    qqPlaylists.value = []
  } finally {
    loadingQq.value = false
  }
}

async function handleImportFromAccount(neteaseId: number) {
  if (importingIds.value.has(neteaseId)) return
  importingIds.value.add(neteaseId)
  try {
    const success = await playlistStore.doImportFromNetease(neteaseId)
    if (success) {
      ElMessage.success('歌单导入成功！')
    } else {
      ElMessage.error(playlistStore.errorMsg || '导入失败')
    }
  } finally {
    importingIds.value.delete(neteaseId)
  }
}

async function handleImportByUrl() {
  const success = await playlistStore.doImport(importUrl.value)
  if (success) {
    showImportDialog.value = false
    ElMessage.success('歌单导入成功，AI 正在分析你的音乐偏好...')
  } else {
    ElMessage.error(playlistStore.errorMsg || '导入失败，请检查链接是否有效')
  }
}

function handleViewPlaylist(id: string) {
  playlistStore.viewPlaylist(id)
}

/** 点击歌单中的歌曲立即播放 */
async function handlePlaySong(song: any) {
  const playerStore = usePlayerStore()
  // ★ 先设歌单模式，即使此歌不可播，队列也正确显示
  if (playlistStore.selectedSongs.length > 0) {
    await playerStore.setPlaylistMode(playlistStore.selectedSongs as any)
  }
  // 尝试播放指定歌曲，失败则跳过
  if (!await _tryPlaySong(song)) {
    ElMessage.warning(`「${song.name}」无法播放，已跳过`)
    // 继续试下一首
    while (playerStore.queue.length > 0) {
      const nextSong = playerStore.queue[0]
      if (await _tryPlaySong(nextSong)) return
      playerStore.removeFromQueue(0)
    }
    ElMessage.error('歌单内没有可播放的歌曲')
  }
}

/** 尝试播放一首歌，成功返回 true */
async function _tryPlaySong(song: any): Promise<boolean> {
  try {
    const result = await playPlaylistSong(song)
    const playerStore = usePlayerStore()
    playerStore.playSong(result.song, result.play_url)
    return true
  } catch {
    return false
  }
}

/** 播放歌单全部歌曲（跳过无音源的歌） */
async function handlePlayAll() {
  const songs = playlistStore.selectedSongs
  if (songs.length === 0) {
    ElMessage.warning('这个歌单还没有歌曲')
    return
  }
  const playerStore = usePlayerStore()
  // ★ 先设歌单模式，即使第一首不可播也不影响队列
  await playerStore.setPlaylistMode(songs as any)

  // ★ 顺序尝试播放，跳过无音源的歌
  for (const song of songs) {
    if (await _tryPlaySong(song)) return
    console.warn(`[Playlist] song ${song.name} unplayable, skipping`)
    const idx = playerStore.queue.findIndex(s => s.id === song.id)
    if (idx !== -1) playerStore.removeFromQueue(0)
  }
  ElMessage.error('歌单内所有歌曲都无法播放')
}

function startRename(id: string, currentName: string) {
  editingId.value = id
  editingName.value = currentName
  setTimeout(() => editInputRef.value?.focus(), 100)
}

async function confirmRename() {
  if (editingId.value && editingName.value.trim()) {
    await playlistStore.renamePlaylist(editingId.value, editingName.value.trim())
  }
  editingId.value = null
}

function handleRenameKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') confirmRename()
  else if (e.key === 'Escape') editingId.value = null
}

async function handleDelete(id: string, name: string) {
  try {
    await ElMessageBox.confirm(`确定要删除歌单「${name}」吗？删除后将自动更新你的音乐画像。`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await playlistStore.removePlaylist(id)
    ElMessage.success('已删除，AI 正在重新分析你的音乐偏好...')
  } catch { /* 取消 */ }
}

async function handleCreatePlaylist() {
  if (!newPlaylistName.value.trim()) {
    ElMessage.warning('请输入歌单名称')
    return
  }
  const ok = await playlistStore.createPlaylist(newPlaylistName.value.trim())
  if (ok) {
    ElMessage.success('歌单创建成功')
    showCreateDialog.value = false
    newPlaylistName.value = ''
  } else {
    ElMessage.error(playlistStore.errorMsg || '创建失败')
  }
}

function formatDate(ts: number): string {
  return new Date(ts).toLocaleDateString('zh-CN')
}
</script>

<template>
  <div class="playlist-panel">
    <div class="playlist-panel__header">
      <h3>📋 我的歌单</h3>
      <div class="playlist-panel__header-right">
        <span class="playlist-panel__stats">{{ playlistStore.playlistCount }} 个歌单 · {{ playlistStore.totalSongs }} 首歌曲</span>
        <button class="playlist-panel__import-btn playlist-panel__create-btn" @click="showCreateDialog = true">✚ 新建</button>
        <button class="playlist-panel__import-btn" @click="openImportDialog">+ 导入歌单</button>
      </div>
    </div>

    <!-- 歌单列表 -->
    <div v-if="playlistStore.isLoading" class="playlist-panel__loading">加载中...</div>
    <div v-else-if="playlistStore.playlists.length === 0" class="playlist-panel__empty">
      <span class="playlist-panel__empty-icon">📭</span>
      <p>还没有导入歌单</p>
      <p class="playlist-panel__empty-hint">从网易云或 QQ 音乐账号一键导入你的歌单</p>
    </div>
    <div v-else class="playlist-panel__list">
      <div
        v-for="pl in playlistStore.playlists"
        :key="pl.playlist_id"
        class="playlist-panel__item"
        :class="{ 'playlist-panel__item--selected': playlistStore.selectedPlaylist?.playlist_id === pl.playlist_id }"
        @click="handleViewPlaylist(pl.playlist_id)"
      >
        <div class="playlist-panel__item-info">
          <template v-if="editingId === pl.playlist_id">
            <input
              ref="editInputRef"
              v-model="editingName"
              class="playlist-panel__rename-input"
              @keydown="handleRenameKeydown"
              @blur="confirmRename"
              @click.stop
            />
          </template>
          <template v-else>
            <span class="playlist-panel__item-name">{{ pl.name }}</span>
            <span class="playlist-panel__item-count">{{ pl.song_count }} 首</span>
            <span class="playlist-panel__item-date">{{ formatDate(pl.created_at) }}</span>
          </template>
        </div>
        <div class="playlist-panel__item-actions" @click.stop>
          <button class="playlist-panel__action-btn" title="重命名" @click="startRename(pl.playlist_id, pl.name)">✎</button>
          <button
            class="playlist-panel__action-btn playlist-panel__action-btn--del"
            title="删除"
            @click="handleDelete(pl.playlist_id, pl.name)"
          >✕</button>
        </div>
      </div>
    </div>

    <!-- 歌单详情（歌曲列表） -->
    <div v-if="playlistStore.selectedPlaylist" class="playlist-panel__detail">
      <div class="playlist-panel__detail-header">
        <h4>{{ playlistStore.selectedPlaylist.name }}</h4>
        <div class="playlist-panel__detail-actions">
          <button class="playlist-panel__playall-btn" @click="handlePlayAll">▶ 播放全部</button>
          <button class="playlist-panel__back-btn" @click="playlistStore.selectedPlaylist = null; playlistStore.selectedSongs = []">关闭</button>
        </div>
      </div>
      <div class="playlist-panel__songs">
        <div v-for="song in playlistStore.selectedSongs" :key="song.id" class="playlist-panel__song" @click="handlePlaySong(song)">
          <img v-if="song.cover_url" :src="song.cover_url" class="playlist-panel__song-cover" />
          <div v-else class="playlist-panel__song-cover-placeholder">🎵</div>
          <div class="playlist-panel__song-info">
            <span class="playlist-panel__song-name">{{ song.name }}</span>
            <span class="playlist-panel__song-artist">{{ song.artists.map(a => a.name).join(' / ') }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 导入弹窗 -->
    <div v-if="showImportDialog" class="import-dialog-overlay" @click.self="showImportDialog = false">
      <div class="import-dialog">
        <h4>导入歌单</h4>

        <!-- Tab 切换 -->
        <div class="import-dialog__tabs">
          <button
            v-if="settingsStore.hasNeteaseLogin"
            class="import-dialog__tab"
            :class="{ 'import-dialog__tab--active': importTab === 'account' }"
            @click="importTab = 'account'"
          >从网易云导入</button>
          <button
            v-if="settingsStore.hasQqLogin"
            class="import-dialog__tab"
            :class="{ 'import-dialog__tab--active': importTab === 'qq' }"
            @click="importTab = 'qq'; loadQqPlaylists()"
          >从 QQ 导入</button>
          <button
            class="import-dialog__tab"
            :class="{ 'import-dialog__tab--active': importTab === 'link' }"
            @click="importTab = 'link'"
          >链接导入</button>
        </div>

        <!-- 从账号导入 -->
        <div v-if="importTab === 'account'">
          <p class="import-dialog__hint">选择要从网易云账号导入的歌单</p>
          <div v-if="loadingNetease" class="playlist-panel__loading">加载歌单列表...</div>
          <div v-else-if="neteasePlaylists.length === 0" class="import-dialog__empty">
            <p>没有找到歌单</p>
          </div>
          <div v-else class="import-dialog__netease-list">
            <div
              v-for="pl in neteasePlaylists"
              :key="pl.netease_id"
              class="import-dialog__netease-item"
            >
              <img
                v-if="pl.cover_url"
                :src="pl.cover_url"
                class="import-dialog__netease-cover"
              />
              <div v-else class="import-dialog__netease-cover-placeholder">🎵</div>
              <div class="import-dialog__netease-info">
                <span class="import-dialog__netease-name">{{ pl.name }}</span>
                <span class="import-dialog__netease-count">{{ pl.song_count }} 首</span>
              </div>
              <button
                class="import-dialog__netease-import-btn"
                :disabled="importingIds.has(pl.netease_id)"
                @click="handleImportFromAccount(pl.netease_id)"
              >
                {{ importingIds.has(pl.netease_id) ? '导入中...' : '导入' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 从 QQ 导入 -->
        <div v-if="importTab === 'qq'">
          <p class="import-dialog__hint">选择要从 QQ 音乐账号导入的歌单</p>
          <div v-if="loadingQq" class="playlist-panel__loading">加载歌单列表...</div>
          <div v-else-if="qqPlaylists.length === 0" class="import-dialog__empty">
            <p>没有找到歌单</p>
          </div>
          <div v-else class="import-dialog__netease-list">
            <div
              v-for="pl in qqPlaylists"
              :key="pl.id"
              class="import-dialog__netease-item"
            >
              <img
                v-if="pl.picurl"
                :src="pl.picurl"
                class="import-dialog__netease-cover"
              />
              <div v-else class="import-dialog__netease-cover-placeholder">🎵</div>
              <div class="import-dialog__netease-info">
                <span class="import-dialog__netease-name">{{ pl.title }}</span>
                <span class="import-dialog__netease-count">{{ pl.songnum }} 首</span>
              </div>
              <button
                class="import-dialog__netease-import-btn"
                :disabled="importingQqIds.has(pl.id)"
                @click="handleImportFromQqList(pl.id)"
              >
                {{ importingQqIds.has(pl.id) ? '导入中...' : '导入' }}
              </button>
            </div>
          </div>
          <!-- 手动输入补充 -->
          <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-subtle);">
            <p class="import-dialog__hint" style="margin-bottom: 8px;">或手动输入 QQ 歌单 ID</p>
            <p class="import-dialog__hint" style="font-size: 10px; color: var(--text-muted); margin-bottom: 8px;">
              歌单 ID 可在 QQ 音乐歌单页 URL 中找到：y.qq.com/n/ryqq/playlist/<strong>123456789</strong>
            </p>
            <div style="display: flex; gap: 8px;">
              <input
                v-model="qqIdInput"
                class="settings-drawer__apikey-input"
                style="flex: 1;"
                placeholder="输入 QQ 歌单数字 ID"
                @keydown.enter="handleImportFromQq"
              />
              <button
                class="import-dialog__btn import-dialog__btn--confirm"
                style="white-space: nowrap;"
                :disabled="!qqIdInput.trim() || playlistStore.isImporting"
                @click="handleImportFromQq"
              >
                {{ playlistStore.isImporting ? '导入中...' : '导入' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 链接导入 -->
        <div v-if="importTab === 'link'">
          <p class="import-dialog__hint">粘贴网易云歌单分享链接，一键导入全部歌曲</p>
          <input
            v-model="importUrl"
            class="settings-drawer__apikey-input"
            style="width: 100%;"
            placeholder="https://music.163.com/playlist?id=xxxxxx"
            @keydown.enter="handleImportByUrl"
          />
        </div>

        <p v-if="playlistStore.errorMsg" class="playlist-panel__error">{{ playlistStore.errorMsg }}</p>
        <div class="import-dialog__actions">
          <button class="import-dialog__btn import-dialog__btn--cancel" @click="showImportDialog = false">取消</button>
          <button
            v-if="importTab === 'link'"
            class="import-dialog__btn import-dialog__btn--confirm"
            :disabled="!importUrl.trim() || playlistStore.isImporting"
            @click="handleImportByUrl"
          >
            {{ playlistStore.isImporting ? '导入中...' : '导入' }}
          </button>
        </div>
      </div>
    </div>
    <!-- 新建歌单弹窗 -->
    <div v-if="showCreateDialog" class="import-dialog-overlay" @click.self="showCreateDialog = false">
      <div class="import-dialog" style="width: 360px;">
        <h4>新建歌单</h4>
        <input
          v-model="newPlaylistName"
          class="settings-drawer__apikey-input"
          style="width: 100%; margin: 12px 0;"
          placeholder="输入歌单名称"
          @keydown.enter="handleCreatePlaylist"
          @keydown.escape="showCreateDialog = false"
          autofocus
        />
        <div class="import-dialog__actions">
          <button class="import-dialog__btn import-dialog__btn--cancel" @click="showCreateDialog = false">取消</button>
          <button
            class="import-dialog__btn import-dialog__btn--confirm"
            :disabled="!newPlaylistName.trim()"
            @click="handleCreatePlaylist"
          >创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss">
.playlist-panel {
  display: flex; flex-direction: column; height: 100%; padding: 12px;

  &__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
    h3 { font-size: $font-size-lg; color: $text-primary; margin: 0; font-weight: 700; }
    &-right { display: flex; align-items: center; gap: 10px; }
  }
  &__stats { font-size: 11px; color: $text-muted; }
  &__import-btn { padding: 6px 14px; background: $accent-primary; border: none; border-radius: $radius-full;
    color: #fff; font-size: $font-size-xs; font-weight: 600; cursor: pointer;
    &:hover { background: $accent-secondary; }
  }
  &__create-btn { background: $bg-glass; color: $text-primary; border: 1px solid $border-subtle;
    &:hover { background: $bg-glass-hover; border-color: $accent-primary; }
  }

  &__loading { padding: 24px; text-align: center; color: $text-muted; }
  &__empty { display: flex; flex-direction: column; align-items: center; padding: 40px 20px; text-align: center;
    &-icon { font-size: 40px; margin-bottom: 8px; }
    p { color: $text-secondary; margin: 0; }
    &-hint { font-size: $font-size-xs; color: $text-muted; margin-top: 4px !important; }
  }

  &__list { flex: 1; overflow-y: auto; }
  &__item { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px;
    margin-bottom: 4px; background: $bg-glass; border: 1px solid $border-subtle;
    border-radius: $radius-sm; cursor: pointer; transition: all 0.15s;
    &:hover { background: $bg-glass-hover; border-color: $border-default; }
    &--selected { border-color: $accent-primary; background: rgba($accent-primary, 0.08); }
    &-info { display: flex; align-items: center; gap: 10px; min-width: 0; }
    &-name { font-size: $font-size-sm; color: $text-primary; font-weight: 600;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 160px; }
    &-count { font-size: 11px; color: $text-muted; flex-shrink: 0; }
    &-date { font-size: 10px; color: $text-muted; flex-shrink: 0; }
    &-actions { display: flex; gap: 4px; flex-shrink: 0; }
  }
  &__action-btn { width: 22px; height: 22px; display: flex; align-items: center;
    justify-content: center; background: none; border: 1px solid transparent;
    border-radius: 50%; color: $text-muted; cursor: pointer; font-size: 11px;
    &:hover { color: $text-primary; border-color: $border-default; }
    &--del:hover { color: #ef4444; border-color: rgba(#ef4444, 0.3); }
  }
  &__rename-input { padding: 2px 8px; background: $bg-tertiary; border: 1px solid $accent-primary;
    border-radius: 4px; color: $text-primary; font-size: $font-size-sm; outline: none; width: 140px; }

  &__detail { margin-top: 12px; border-top: 1px solid $border-subtle; padding-top: 12px; }
  &__detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
    h4 { font-size: $font-size-base; color: $text-primary; margin: 0; }
  }
  &__detail-actions { display: flex; gap: 6px; }
  &__playall-btn { padding: 4px 12px; background: $accent-primary; border: none; border-radius: $radius-full;
    color: #fff; font-size: 11px; font-weight: 600; cursor: pointer; white-space: nowrap;
    &:hover { background: $accent-secondary; } }
  &__back-btn { background: none; border: 1px solid $border-subtle; border-radius: $radius-full;
    color: $text-secondary; font-size: 11px; cursor: pointer; padding: 3px 10px;
    &:hover { border-color: $border-default; color: $text-primary; }
  }
  &__songs { max-height: 200px; overflow-y: auto; }
  &__song { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: $radius-sm; cursor: pointer;
    &:hover { background: $bg-glass; }
    &-cover { width: 32px; height: 32px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
    &-cover-placeholder { width: 32px; height: 32px; border-radius: 4px; background: $bg-tertiary;
      display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
    &-info { display: flex; flex-direction: column; min-width: 0; }
    &-name { font-size: $font-size-xs; color: $text-primary;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    &-artist { font-size: 10px; color: $text-muted; }
  }

  &__error { font-size: 11px; color: #ef4444; margin: 6px 0 0; }
}

.import-dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 200; }
.import-dialog { background: $bg-secondary; border: 1px solid $border-subtle;
  border-radius: $radius-lg; padding: 24px; width: 480px; max-width: 90vw;
  max-height: 80vh; display: flex; flex-direction: column;
  h4 { margin: 0 0 8px; font-size: $font-size-base; color: $text-primary; }
  &__hint { font-size: $font-size-xs; color: $text-muted; margin: 0 0 12px; }

  &__tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid $border-subtle; }
  &__tab { padding: 8px 16px; background: none; border: none; border-bottom: 2px solid transparent;
    color: $text-muted; font-size: $font-size-sm; cursor: pointer; transition: all 0.15s;
    &--active { color: $accent-primary; border-bottom-color: $accent-primary; font-weight: 600; }
    &:hover:not(&--active) { color: $text-secondary; }
  }

  &__empty { padding: 20px; text-align: center; color: $text-muted; font-size: $font-size-sm; }

  &__netease-list { max-height: 300px; overflow-y: auto; margin-bottom: 8px; }
  &__netease-item { display: flex; align-items: center; gap: 10px; padding: 8px 8px;
    border-radius: $radius-sm; transition: background 0.15s;
    &:hover { background: $bg-glass; }
  }
  &__netease-cover { width: 40px; height: 40px; border-radius: 6px; object-fit: cover; flex-shrink: 0; }
  &__netease-cover-placeholder { width: 40px; height: 40px; border-radius: 6px;
    background: $bg-tertiary; display: flex; align-items: center; justify-content: center;
    font-size: 16px; flex-shrink: 0; }
  &__netease-info { display: flex; flex-direction: column; min-width: 0; flex: 1; }
  &__netease-name { font-size: $font-size-sm; color: $text-primary;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &__netease-count { font-size: 10px; color: $text-muted; }
  &__netease-import-btn { padding: 4px 12px; background: $accent-primary; border: none;
    border-radius: $radius-full; color: #fff; font-size: 11px; cursor: pointer; white-space: nowrap;
    flex-shrink: 0;
    &:hover:not(:disabled) { background: $accent-secondary; }
    &:disabled { opacity: 0.4; cursor: not-allowed; }
  }

  &__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
  &__btn { padding: 8px 20px; border-radius: $radius-full; font-size: $font-size-sm; cursor: pointer; border: none;
    &--cancel { background: $bg-glass; color: $text-secondary;
      &:hover { color: $text-primary; } }
    &--confirm { background: $accent-primary; color: #fff;
      &:hover:not(:disabled) { background: $accent-secondary; }
      &:disabled { opacity: 0.4; cursor: not-allowed; }
    }
  }
}
</style>
