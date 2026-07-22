<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { usePlayerStore } from '@/stores/player'
import { usePlaylistStore } from '@/stores/playlist'
import { useElectron } from '@/composables/useElectron'
import { ElMessage } from 'element-plus'

const playerStore = usePlayerStore()
const playlistStore = usePlaylistStore()
const { updateMediaMetadata } = useElectron()

onMounted(() => { playlistStore.loadPlaylists() })

/* ── 播放模式标识 ── */
const playModeLabel = computed(() => {
  switch (playerStore.playbackMode) {
    case 'random': return 'RND'
    case 'singleLoop': return '1'
    default: return 'SEQ'
  }
})

function togglePlayMode() {
  const modes: Array<'sequential' | 'random' | 'singleLoop'> = ['sequential', 'random', 'singleLoop']
  const currentIndex = modes.indexOf(playerStore.playbackMode)
  playerStore.setPlaybackMode(modes[(currentIndex + 1) % modes.length])
}

function handleProgressClick(e: MouseEvent) {
  const bar = e.currentTarget as HTMLElement
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  playerStore.seekTo(ratio * playerStore.duration)
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

/* ── 添加到歌单下拉 ── */
const showPlaylistPicker = ref(false)
const playlistPickerRef = ref<HTMLElement | null>(null)

function togglePlaylistPicker() {
  showPlaylistPicker.value = !showPlaylistPicker.value
  if (showPlaylistPicker.value) playlistStore.loadPlaylists()
}

function onClickOutside(e: MouseEvent) {
  if (playlistPickerRef.value && !playlistPickerRef.value.contains(e.target as Node)) {
    showPlaylistPicker.value = false
  }
}
onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))

async function handleAddToPlaylist(playlistId: string) {
  const song = playerStore.currentSong
  if (!song) return
  const pl = playlistStore.playlists.find(p => p.playlist_id === playlistId)
  const ok = await playlistStore.addSong(playlistId, song)
  if (ok) ElMessage.success(`已添加到「${pl?.name || '歌单'}」`)
  else ElMessage.error(playlistStore.errorMsg || '添加失败')
  showPlaylistPicker.value = false
}

async function handleCreateAndAdd() {
  const song = playerStore.currentSong
  if (!song) return
  const name = `我喜欢 (${song.name})`
  const ok = await playlistStore.createPlaylist(name)
  if (ok) {
    const newPl = playlistStore.playlists[playlistStore.playlists.length - 1]
    if (newPl) await handleAddToPlaylist(newPl.playlist_id)
  } else ElMessage.error(playlistStore.errorMsg || '创建歌单失败')
  showPlaylistPicker.value = false
}

watch(() => playerStore.currentSong, (song) => {
  if (song) {
    updateMediaMetadata({
      title: song.name,
      artist: song.artists?.[0]?.name ?? '',
      album: song.album?.name ?? '',
      artwork: song.cover_url || undefined,
    })
  }
})
</script>

<template>
  <div class="music-player">
    <!-- 2×2 网格：歌名+PLAYING | 控制按钮 -->
    <div v-if="playerStore.currentSong" class="music-player__grid">
      <!-- 左列 Row 1：歌曲信息 -->
      <div class="music-player__info">
        <span class="music-player__title">{{ playerStore.currentSong.name }}</span>
        <span class="music-player__sep">—</span>
        <span class="music-player__artist">{{ playerStore.currentSong.artists?.[0]?.name ?? '' }}</span>
      </div>

      <!-- 左列 Row 2：PLAYING 徽章 -->
      <div class="music-player__status-row">
        <span class="music-player__status-dot"></span>
        <span class="music-player__status-text">PLAYING</span>
      </div>

      <!-- 右列（跨 2 行）：控制按钮 -->
      <div class="music-player__controls">
        <button class="music-player__ctrl-btn" title="播放模式" @click="togglePlayMode">
          <span class="music-player__mode-pill">{{ playModeLabel }}</span>
        </button>

        <button class="music-player__ctrl-btn" title="上一首" :disabled="!playerStore.hasPrevious" @click="playerStore.prev()">◁</button>

        <button class="music-player__ctrl-btn music-player__ctrl-btn--play" title="播放/暂停" :disabled="!playerStore.currentSong" @click="playerStore.togglePlay()">
          <span v-if="playerStore.isLoading" class="music-player__loading">○</span>
          <span v-else-if="playerStore.isPlaying">❚❚</span>
          <span v-else>▶</span>
        </button>

        <button class="music-player__ctrl-btn" title="下一首" :disabled="!playerStore.hasNext" @click="playerStore.next()">▷</button>

        <div ref="playlistPickerRef" class="music-player__picker-wrap">
          <button class="music-player__ctrl-btn" title="添加到歌单" :disabled="!playerStore.currentSong" @click="togglePlaylistPicker()">
            {{ playerStore.isLiked ? '♥' : '♡' }}
          </button>
          <!-- 添加到歌单下拉 -->
          <div v-if="showPlaylistPicker" class="music-player__dropdown" @click.stop>
            <div class="music-player__dropdown-header">添加到歌单</div>
            <div class="music-player__dropdown-list">
              <div v-for="pl in playlistStore.userPlaylists" v-show="!playlistStore.isNeteaseImported(pl)" :key="pl.playlist_id" class="music-player__dropdown-item" @click="handleAddToPlaylist(pl.playlist_id)">
                <span class="music-player__dropdown-item-name">{{ pl.name }}</span>
                <span class="music-player__dropdown-item-count">{{ pl.song_count }} 首</span>
              </div>
              <div class="music-player__dropdown-item music-player__dropdown-item--new" @click="handleCreateAndAdd">
                ✚ 新建歌单并添加
              </div>
            </div>
          </div>
        </div>

        <button class="music-player__ctrl-btn" title="不喜欢" :disabled="!playerStore.currentSong" @click="playerStore.dislike()">−</button>

        <span class="music-player__divider"></span>

        <!-- 音量 -->
        <div class="music-player__volume-wrap">
          <input
            type="range"
            min="0"
            max="100"
            class="music-player__volume-slider"
            :value="playerStore.isMuted ? 0 : Math.round(playerStore.volume * 100)"
            @input="playerStore.setVolume(Number(($event.target as HTMLInputElement).value) / 100)"
          />
        </div>
      </div>
    </div>

    <!-- 无歌曲时 -->
    <div v-else class="music-player__empty">
      <span class="music-player__empty-text">选择一首歌开始吧</span>
    </div>

    <!-- 进度条 -->
    <div v-if="playerStore.currentSong" class="music-player__progress-row">
      <div class="music-player__progress-bar" @click="handleProgressClick">
        <div class="music-player__progress-track"></div>
        <div class="music-player__progress-fill" :style="{ width: playerStore.progress + '%' }"></div>
        <div class="music-player__progress-thumb" :style="{ left: playerStore.progress + '%' }"></div>
      </div>
      <span class="music-player__time">{{ formatTime(playerStore.currentTime) }} / {{ formatTime(playerStore.duration) }}</span>
    </div>

    <p v-if="playerStore.playReason" class="music-player__reason">{{ playerStore.playReason }}</p>
  </div>
</template>

<style lang="scss">
.music-player {
  padding: 4px 24px 10px;

  /* ── 2×2 网格 ── */
  &__grid {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    column-gap: 16px;
    align-items: start;
  }

  /* 左列 Row 1：歌曲信息 */
  &__info {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
    overflow: hidden;
  }

  &__title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }

  &__sep {
    color: var(--text-muted);
    font-size: $font-size-sm;
    flex-shrink: 0;
  }

  &__artist {
    font-size: $font-size-sm;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* 左列 Row 2：PLAYING 徽章 */
  &__status-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 2px;
  }

  &__status-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: $accent-primary;
    animation: pulse 2s infinite;
    flex-shrink: 0;
  }

  &__status-text {
    font-family: $font-mono;
    font-size: 9px;
    font-weight: 500;
    color: $accent-primary;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }

  /* 右列（跨 2 行）：控制按钮 */
  &__controls {
    grid-row: 1 / -1;
    align-self: center;
    display: flex;
    align-items: center;
    gap: 2px;
  }

  &__ctrl-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    border-radius: 50%;
    font-size: 20px;
    font-family: $font-mono;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;

    &:hover:not(:disabled) {
      color: $accent-primary;
      text-shadow: 0 0 8px rgba($accent-primary, 0.4);
    }

    &:disabled {
      opacity: 0.2;
      cursor: not-allowed;
    }

    &--play {
      font-size: 22px;
      color: var(--text-primary);
      &:hover:not(:disabled) {
        color: $accent-primary;
        transform: scale(1.08);
      }
    }
  }

  /* 播放模式 pill */
  &__mode-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 1px 5px;
    font-family: $font-mono;
    font-size: 9px;
    font-weight: 500;
    color: var(--text-muted);
    border: 1px solid var(--border-default);
    border-radius: 3px;
    letter-spacing: 0.5px;
    transition: all 0.15s;

    .music-player__ctrl-btn:hover & {
      color: $accent-primary;
      border-color: $accent-primary;
    }
  }

  &__loading {
    display: inline-block;
    animation: spin-slow 1s linear infinite;
    font-size: 18px;
  }

  /* ── 分隔 ── */
  &__divider {
    width: 1px;
    height: 18px;
    background: $border-subtle;
    margin: 0 4px;
    flex-shrink: 0;
  }

  /* ── 音量 ── */
  &__volume-wrap {
    display: flex;
    align-items: center;
  }

  &__volume-slider {
    -webkit-appearance: none;
    appearance: none;
    width: 56px;
    height: 2px;
    background: $bg-tertiary;
    border-radius: 2px;
    outline: none;
    cursor: pointer;

    &::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 10px;
      height: 10px;
      background: var(--text-secondary);
      border-radius: 50%;
      cursor: pointer;
      transition: all 0.15s;
    }

    &:hover::-webkit-slider-thumb {
      background: $accent-primary;
      box-shadow: 0 0 6px rgba($accent-primary, 0.4);
    }
  }

  /* ── 无歌曲 ── */
  &__empty {
    text-align: center;
    padding: 20px 0;
  }

  &__empty-text {
    font-size: $font-size-sm;
    color: var(--text-muted);
    font-style: italic;
  }

  /* ── 添加到歌单下拉 ── */
  &__picker-wrap { position: relative; }

  &__dropdown {
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: $radius-md;
    box-shadow: $shadow-lg;
    min-width: 200px;
    max-width: 260px;
    max-height: 260px;
    display: flex;
    flex-direction: column;
    z-index: 300;
    overflow: hidden;

    &-header {
      padding: 6px 12px;
      font-size: $font-size-xs;
      font-family: $font-mono;
      color: var(--text-muted);
      border-bottom: 1px solid $border-subtle;
      flex-shrink: 0;
      text-transform: uppercase;
      letter-spacing: 1px;
    }

    &-list { overflow-y: auto; flex: 1; }

    &-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: 6px 12px; cursor: pointer; transition: background 0.15s; gap: 8px;
      &:hover { background: $bg-glass-hover; }
      &-name { font-size: $font-size-xs; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
      &-count { font-size: 10px; color: var(--text-muted); flex-shrink: 0; }
      &--new { border-top: 1px solid $border-subtle; color: $accent-primary; font-size: $font-size-xs; font-weight: 500; }
    }
  }

  /* ── 进度条 ── */
  &__progress-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
  }

  &__progress-bar {
    flex: 1;
    height: 18px;
    position: relative;
    cursor: pointer;
    display: flex;
    align-items: center;
  }

  &__progress-track {
    width: 100%;
    height: 2px;
    background: $bg-tertiary;
    border-radius: 2px;
  }

  &__progress-fill {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    height: 2px;
    background: $accent-primary;
    border-radius: 2px;
    pointer-events: none;
    transition: width 0.2s linear;
  }

  &__progress-thumb {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 8px;
    height: 8px;
    background: $accent-primary;
    border-radius: 50%;
    box-shadow: 0 0 4px rgba($accent-primary, 0.4);
    pointer-events: none;
    transition: left 0.2s linear;
  }

  &__time {
    font-family: $font-mono;
    font-size: 9px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    min-width: 70px;
    text-align: right;
    flex-shrink: 0;
  }

  &__reason {
    margin: 6px 0 0;
    font-size: $font-size-xs;
    color: rgba($accent-warm, 0.8);
    font-style: italic;
    text-align: center;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>
