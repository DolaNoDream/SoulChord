<script setup lang="ts">
import { computed } from 'vue'
import type { Song } from '@/types/music'
import { usePlayerStore } from '@/stores/player'

const props = withDefaults(defineProps<{
  song: Song
  showReason?: boolean
  compact?: boolean
}>(), {
  showReason: false,
  compact: false,
})

const emit = defineEmits<{
  play: [song: Song]
  addToQueue: [song: Song]
}>()

const playerStore = usePlayerStore()

const isCurrentSong = computed(() => playerStore.currentSong?.id === props.song.id)

function handlePlay() {
  if (isCurrentSong.value) {
    playerStore.togglePlay()
  } else {
    emit('play', props.song)
  }
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function emotionLabel(emotion: string): string {
  const map: Record<string, string> = {
    energetic: '⚡ 活力',
    calm: '🌙 平静',
    melancholic: '🍂 忧伤',
    happy: '☀️ 开心',
    romantic: '💕 浪漫',
    dark: '🖤 暗黑',
    neutral: '🎶 中性',
  }
  return map[emotion] ?? emotion
}
</script>

<template>
  <div
    class="song-card"
    :class="{
      'song-card--active': isCurrentSong,
      'song-card--compact': compact,
    }"
    @click="handlePlay"
  >
    <div class="song-card__cover">
      <img
        v-if="song.cover_url"
        :src="song.cover_url"
        :alt="song.name"
        class="song-card__cover-img"
      />
      <div v-else class="song-card__cover-placeholder">
        <span>🎵</span>
      </div>
      <button class="song-card__play-btn" :title="isCurrentSong && playerStore.isPlaying ? '暂停' : '播放'">
        <span v-if="isCurrentSong && playerStore.isPlaying">⏸</span>
        <span v-else>▶</span>
      </button>
    </div>

    <div class="song-card__info">
      <h4 class="song-card__title">{{ song.name }}</h4>
      <p class="song-card__artist">{{ song.artists.map(a => a.name).join(' / ') }}</p>
      <p v-if="showReason && playerStore.playReason" class="song-card__reason">
        💬 {{ playerStore.playReason }}
      </p>
    </div>

    <div v-if="!compact" class="song-card__meta">
      <span class="song-card__duration">{{ formatDuration(song.duration_ms) }}</span>
      <!-- emotion not in Song v0.3 -->
    </div>
  </div>
</template>

<style lang="scss">
.song-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: $radius-md;
  background: $bg-glass;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;

  &:hover {
    background: $bg-glass-hover;
    transform: translateX(2px);
  }

  &--active {
    background: rgba($accent-primary, 0.12);
    border: 1px solid rgba($accent-primary, 0.25);
  }

  &--compact {
    padding: 6px 10px;

    .song-card__title {
      font-size: $font-size-sm;
    }

    .song-card__artist {
      font-size: $font-size-xs;
    }
  }

  &__cover {
    position: relative;
    width: 48px;
    height: 48px;
    border-radius: $radius-sm;
    overflow: hidden;
    flex-shrink: 0;

    &-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    &-placeholder {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, $bg-tertiary, $bg-secondary);
      font-size: 20px;
    }
  }

  &__play-btn {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.5);
    opacity: 0;
    border: none;
    color: #fff;
    font-size: 16px;
    cursor: pointer;
    transition: opacity 0.2s;

    .song-card:hover &,
    .song-card--active & {
      opacity: 1;
    }
  }

  &__info {
    flex: 1;
    min-width: 0;
  }

  &__title {
    font-size: $font-size-base;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin: 0;
  }

  &__artist {
    font-size: $font-size-sm;
    color: var(--text-secondary);
    margin: 2px 0 0;
  }

  &__reason {
    font-size: $font-size-xs;
    color: var(--accent-warm);
    margin: 4px 0 0;
    font-style: italic;
  }

  &__meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    flex-shrink: 0;
  }

  &__duration {
    font-size: $font-size-xs;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  &__emotion {
    font-size: 10px;
    color: var(--text-muted);
  }
}
</style>
