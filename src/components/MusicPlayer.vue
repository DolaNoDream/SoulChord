<script setup lang="ts">
import { ref, computed } from 'vue'
import { usePlayerStore } from '@/stores/player'
import { useElectron } from '@/composables/useElectron'

const playerStore = usePlayerStore()
const { updateMediaMetadata } = useElectron()

const isDragging = ref(false)
const progressBarRef = ref<HTMLElement | null>(null)

/** 播放模式图标和下一个模式 */
const playModeIcon = computed(() => {
  switch (playerStore.playbackMode) {
    case 'random': return '🔀'
    case 'singleLoop': return '🔂'
    default: return '🔁'
  }
})

function togglePlayMode() {
  const modes: Array<'sequential' | 'random' | 'singleLoop'> = ['sequential', 'random', 'singleLoop']
  const currentIndex = modes.indexOf(playerStore.playbackMode)
  const nextMode = modes[(currentIndex + 1) % modes.length]
  playerStore.setPlaybackMode(nextMode)
}

/** 进度条点击 */
function handleProgressClick(e: MouseEvent) {
  const bar = progressBarRef.value ?? (e.currentTarget as HTMLElement)
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  playerStore.seekTo(ratio * playerStore.duration)
}

/** 进度条拖拽 */
function handleProgressMouseDown(e: MouseEvent) {
  isDragging.value = true
  const bar = progressBarRef.value ?? (e.currentTarget as HTMLElement)

  function onMove(ev: MouseEvent) {
    const rect = bar.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width))
    playerStore.seekTo(ratio * playerStore.duration)
  }

  function onUp() {
    isDragging.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

/** 格式化时间 */
function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 监听当前歌曲变化，更新 OS 媒体控件
import { watch } from 'vue'
watch(() => playerStore.currentSong, (song) => {
  if (song) {
    updateMediaMetadata({
      title: song.title,
      artist: song.artist,
      album: song.album,
      artwork: song.coverUrl || undefined,
    })
  }
})
</script>

<template>
  <div class="music-player">
    <!-- 封面区域 -->
    <div class="music-player__cover">
      <img
        v-if="playerStore.currentSong?.coverUrl"
        :src="playerStore.currentSong.coverUrl"
        :alt="playerStore.currentSong?.title"
        class="music-player__cover-img"
        :class="{ 'music-player__cover-img--playing': playerStore.isPlaying }"
      />
      <div v-else class="music-player__cover-placeholder">
        <span>🎵</span>
      </div>
    </div>

    <!-- 歌曲信息 -->
    <div class="music-player__info">
      <h2 class="music-player__title">
        {{ playerStore.currentSong?.title ?? '未在播放' }}
      </h2>
      <p class="music-player__artist">
        {{ playerStore.currentSong?.artist ?? '选择一首歌开始吧' }}
      </p>
      <p v-if="playerStore.currentSong?.reason" class="music-player__reason">
        💬 {{ playerStore.currentSong.reason }}
      </p>
    </div>

    <!-- 进度条 -->
    <div class="music-player__progress">
      <span class="music-player__time">{{ formatTime(playerStore.currentTime) }}</span>
      <div
        ref="progressBarRef"
        class="music-player__progress-bar"
        @click="handleProgressClick"
        @mousedown="handleProgressMouseDown"
      >
        <div class="music-player__progress-track"></div>
        <div
          class="music-player__progress-fill"
          :style="{ width: playerStore.progress + '%' }"
        ></div>
        <div
          class="music-player__progress-thumb"
          :class="{ 'music-player__progress-thumb--dragging': isDragging }"
          :style="{ left: playerStore.progress + '%' }"
        ></div>
      </div>
      <span class="music-player__time">{{ formatTime(playerStore.duration) }}</span>
    </div>

    <!-- 喜欢/踩 -->
    <div class="music-player__feedback">
      <button
        class="music-player__feedback-btn"
        :class="{ 'music-player__feedback-btn--active': playerStore.isLiked }"
        title="喜欢"
        :disabled="!playerStore.currentSong"
        @click="playerStore.toggleLike()"
      >
        {{ playerStore.isLiked ? '❤️' : '🤍' }}
      </button>
      <button
        class="music-player__feedback-btn"
        :class="{ 'music-player__feedback-btn--active': playerStore.isDisliked }"
        title="不喜欢"
        :disabled="!playerStore.currentSong"
        @click="playerStore.toggleDislike()"
      >
        {{ playerStore.isDisliked ? '👎' : '👎' }}
      </button>
    </div>

    <!-- 控制按钮 -->
    <div class="music-player__controls">
      <button class="music-player__btn" title="播放模式" @click="togglePlayMode">
        {{ playModeIcon }}
      </button>
      <button
        class="music-player__btn"
        title="上一首"
        :disabled="!playerStore.hasPrevious"
        @click="playerStore.prev()"
      >
        ⏮
      </button>
      <button
        class="music-player__btn music-player__btn--play"
        title="播放/暂停"
        :disabled="!playerStore.currentSong"
        @click="playerStore.togglePlay()"
      >
        <span v-if="playerStore.isLoading">⏳</span>
        <span v-else-if="playerStore.isPlaying">⏸</span>
        <span v-else>▶</span>
      </button>
      <button
        class="music-player__btn"
        title="下一首"
        :disabled="!playerStore.hasNext"
        @click="playerStore.next()"
      >
        ⏭
      </button>
      <button
        class="music-player__btn"
        title="音量"
        @click="playerStore.toggleMute()"
      >
        {{ playerStore.isMuted || playerStore.volume === 0 ? '🔇' : playerStore.volume > 0.5 ? '🔊' : '🔉' }}
      </button>
    </div>

    <!-- 音量滑块 -->
    <div class="music-player__volume">
      <input
        type="range"
        min="0"
        max="100"
        :value="playerStore.isMuted ? 0 : Math.round(playerStore.volume * 100)"
        class="music-player__volume-slider"
        @input="playerStore.setVolume(Number(($event.target as HTMLInputElement).value) / 100)"
      />
    </div>
  </div>
</template>

<style lang="scss">
.music-player {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 20px 16px;
  gap: 16px;

  &__cover {
    width: 180px;
    height: 180px;
    border-radius: $radius-lg;
    overflow: hidden;
    box-shadow: $shadow-lg;
    flex-shrink: 0;

    &-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.5s ease;

      &--playing {
        animation: coverSpin 20s linear infinite;
      }
    }

    &-placeholder {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, $bg-tertiary, $bg-secondary);
      font-size: 64px;
    }
  }

  &__info {
    text-align: center;
    min-width: 0;
    width: 100%;
  }

  &__title {
    font-size: $font-size-lg;
    font-weight: 700;
    color: $text-primary;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__artist {
    font-size: $font-size-sm;
    color: $text-secondary;
    margin: 4px 0 0;
  }

  &__reason {
    font-size: $font-size-xs;
    color: $accent-warm;
    font-style: italic;
    margin: 6px 0 0;
    line-height: 1.4;
  }

  &__progress {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
  }

  &__time {
    font-size: 11px;
    color: $text-muted;
    font-variant-numeric: tabular-nums;
    min-width: 40px;
    text-align: center;
  }

  &__progress-bar {
    flex: 1;
    height: 20px;
    position: relative;
    cursor: pointer;
    display: flex;
    align-items: center;
  }

  &__progress-track {
    width: 100%;
    height: 4px;
    background: $bg-tertiary;
    border-radius: 2px;
  }

  &__progress-fill {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    height: 4px;
    background: $accent-primary;
    border-radius: 2px;
    pointer-events: none;
    transition: width 0.1s linear;
  }

  &__progress-thumb {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 12px;
    height: 12px;
    background: $accent-primary;
    border-radius: 50%;
    box-shadow: 0 0 6px rgba($accent-primary, 0.5);
    pointer-events: none;
    transition: transform 0.1s;

    &--dragging {
      transform: translate(-50%, -50%) scale(1.3);
    }
  }

  &__feedback {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-bottom: 4px;

    &-btn {
      background: none;
      border: none;
      font-size: 22px;
      cursor: pointer;
      opacity: 0.5;
      transition: all 0.2s;
      padding: 4px;

      &:hover:not(:disabled) {
        opacity: 0.8;
        transform: scale(1.15);
      }

      &:disabled {
        opacity: 0.2;
        cursor: not-allowed;
      }

      &--active {
        opacity: 1;
        transform: scale(1.05);
      }
    }
  }

  &__controls {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  &__btn {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid $border-subtle;
    border-radius: 50%;
    font-size: 18px;
    cursor: pointer;
    color: $text-primary;
    transition: all 0.2s;

    &:hover:not(:disabled) {
      background: $bg-glass-hover;
      border-color: $accent-primary;
    }

    &:disabled {
      opacity: 0.3;
      cursor: not-allowed;
    }

    &--play {
      width: 56px;
      height: 56px;
      font-size: 24px;
      border-color: $accent-primary;
      background: rgba($accent-primary, 0.15);

      &:hover:not(:disabled) {
        background: rgba($accent-primary, 0.3);
        transform: scale(1.05);
      }
    }
  }

  &__volume {
    width: 100%;
    max-width: 200px;

    &-slider {
      -webkit-appearance: none;
      appearance: none;
      width: 100%;
      height: 4px;
      background: $bg-tertiary;
      border-radius: 2px;
      outline: none;
      cursor: pointer;

      &::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 14px;
        height: 14px;
        background: $accent-primary;
        border-radius: 50%;
        cursor: pointer;
        box-shadow: 0 0 6px rgba($accent-primary, 0.5);
      }

      &::-moz-range-thumb {
        width: 14px;
        height: 14px;
        background: $accent-primary;
        border-radius: 50%;
        cursor: pointer;
        border: none;
      }
    }
  }
}

@keyframes coverSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
