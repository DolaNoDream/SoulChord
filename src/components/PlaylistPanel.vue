<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePlaylistStore } from '@/stores/playlist'
import { useSettingsStore } from '@/stores/settings'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const playlistStore = usePlaylistStore()
const settingsStore = useSettingsStore()
const userStore = useUserStore()

const showImportDialog = ref(false)
const importUrl = ref('')
const editingId = ref<string | null>(null)
const editingName = ref('')
const editInputRef = ref<HTMLInputElement | null>(null)

onMounted(() => {
  playlistStore.loadPlaylists()
})

function openImportDialog() {
  if (!settingsStore.hasLlmKey) {
    ElMessage.warning('请先在设置中配置 LLM API Key')
    return
  }
  if (!settingsStore.neteaseApiKey) {
    ElMessage.warning('请先在设置中配置网易云 API Key')
    return
  }
  importUrl.value = ''
  showImportDialog.value = true
}

async function handleImport() {
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
        <button class="playlist-panel__import-btn" @click="openImportDialog">+ 导入歌单</button>
      </div>
    </div>

    <!-- 歌单列表 -->
    <div v-if="playlistStore.isLoading" class="playlist-panel__loading">加载中...</div>
    <div v-else-if="playlistStore.playlists.length === 0" class="playlist-panel__empty">
      <span class="playlist-panel__empty-icon">📭</span>
      <p>还没有导入歌单</p>
      <p class="playlist-panel__empty-hint">粘贴网易云歌单分享链接，让AI了解你的音乐品味</p>
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
          <button class="playlist-panel__action-btn playlist-panel__action-btn--del" title="删除" @click="handleDelete(pl.playlist_id, pl.name)">✕</button>
        </div>
      </div>
    </div>

    <!-- 歌单详情（歌曲列表） -->
    <div v-if="playlistStore.selectedPlaylist" class="playlist-panel__detail">
      <div class="playlist-panel__detail-header">
        <h4>{{ playlistStore.selectedPlaylist.name }}</h4>
        <button class="playlist-panel__back-btn" @click="playlistStore.selectedPlaylist = null; playlistStore.selectedSongs = []">关闭</button>
      </div>
      <div class="playlist-panel__songs">
        <div v-for="song in playlistStore.selectedSongs" :key="song.id" class="playlist-panel__song">
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
        <h4>导入网易云歌单</h4>
        <p class="import-dialog__hint">粘贴网易云歌单分享链接，一键导入全部歌曲</p>
        <input
          v-model="importUrl"
          class="settings-drawer__apikey-input"
          style="width: 100%;"
          placeholder="https://music.163.com/playlist?id=xxxxxx"
          @keydown.enter="handleImport"
        />
        <p v-if="playlistStore.errorMsg" class="playlist-panel__error">{{ playlistStore.errorMsg }}</p>
        <div class="import-dialog__actions">
          <button class="import-dialog__btn import-dialog__btn--cancel" @click="showImportDialog = false">取消</button>
          <button class="import-dialog__btn import-dialog__btn--confirm" :disabled="!importUrl.trim() || playlistStore.isImporting" @click="handleImport">
            {{ playlistStore.isImporting ? '导入中...' : '导入' }}
          </button>
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
  &__back-btn { background: none; border: 1px solid $border-subtle; border-radius: $radius-full;
    color: $text-secondary; font-size: 11px; cursor: pointer; padding: 3px 10px;
    &:hover { border-color: $border-default; color: $text-primary; }
  }
  &__songs { max-height: 200px; overflow-y: auto; }
  &__song { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: $radius-sm;
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
  border-radius: $radius-lg; padding: 24px; width: 400px; max-width: 90vw;
  h4 { margin: 0 0 8px; font-size: $font-size-base; color: $text-primary; }
  &__hint { font-size: $font-size-xs; color: $text-muted; margin: 0 0 12px; }
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
