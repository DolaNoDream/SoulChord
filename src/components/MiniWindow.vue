<script setup lang="ts">
import { usePlayerStore } from '@/stores/player'
import { useSettingsStore } from '@/stores/settings'

const playerStore = usePlayerStore()
const settingsStore = useSettingsStore()

function handleExpand() {
  settingsStore.toggleMiniMode()
}
</script>

<template>
  <div class="mini-window">
    <!-- 拖拽区域 -->
    <div class="mini-window__drag-area"></div>

    <!-- 封面 -->
    <div class="mini-window__cover">
      <img
        v-if="playerStore.currentSong?.coverUrl"
        :src="playerStore.currentSong.coverUrl"
        :alt="playerStore.currentSong?.title"
        class="mini-window__cover-img"
        :class="{ 'mini-window__cover-img--playing': playerStore.isPlaying }"
      />
      <div v-else class="mini-window__cover-placeholder">
        <span>🎵</span>
      </div>
    </div>

    <!-- 歌曲信息 -->
    <div class="mini-window__info">
      <p class="mini-window__title">
        {{ playerStore.currentSong?.title ?? 'SoulChord' }}
      </p>
      <p class="mini-window__artist">
        {{ playerStore.currentSong?.artist ?? 'AI 音乐电台' }}
      </p>
    </div>

    <!-- 播放控制 -->
    <button
      class="mini-window__play-btn"
      :disabled="!playerStore.currentSong"
      @click="playerStore.togglePlay()"
    >
      <span v-if="playerStore.isLoading">⏳</span>
      <span v-else-if="playerStore.isPlaying">⏸</span>
      <span v-else>▶</span>
    </button>

    <!-- 展开按钮 -->
    <button class="mini-window__expand-btn" title="展开" @click="handleExpand">
      ⬈
    </button>

    <!-- 迷你进度条 -->
    <div class="mini-window__progress">
      <div
        class="mini-window__progress-fill"
        :style="{ width: playerStore.progress + '%' }"
      ></div>
    </div>
  </div>
</template>

<style lang="scss">
.mini-window {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  height: 80px;
  border-radius: $radius-lg;
  background: rgba(13, 13, 18, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid $border-subtle;
  box-shadow: $shadow-lg;
  position: relative;
  overflow: hidden;
  user-select: none;

  &__drag-area {
    position: absolute;
    inset: 0;
    -webkit-app-region: drag;
    z-index: 0;
  }

  &__cover {
    width: 48px;
    height: 48px;
    border-radius: $radius-sm;
    overflow: hidden;
    flex-shrink: 0;
    z-index: 1;

    &-img {
      width: 100%;
      height: 100%;
      object-fit: cover;

      &--playing {
        animation: miniCoverSpin 12s linear infinite;
      }
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

  &__info {
    flex: 1;
    min-width: 0;
    z-index: 1;
  }

  &__title {
    font-size: $font-size-sm;
    font-weight: 600;
    color: $text-primary;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__artist {
    font-size: $font-size-xs;
    color: $text-muted;
    margin: 2px 0 0;
  }

  &__play-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba($accent-primary, 0.2);
    border: 1px solid rgba($accent-primary, 0.3);
    border-radius: 50%;
    font-size: 14px;
    cursor: pointer;
    color: $text-primary;
    z-index: 1;
    -webkit-app-region: no-drag;
    transition: all 0.2s;

    &:hover:not(:disabled) {
      background: rgba($accent-primary, 0.35);
    }

    &:disabled {
      opacity: 0.3;
      cursor: not-allowed;
    }
  }

  &__expand-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid $border-subtle;
    border-radius: 50%;
    font-size: 12px;
    cursor: pointer;
    color: $text-secondary;
    z-index: 1;
    -webkit-app-region: no-drag;
    transition: all 0.2s;

    &:hover {
      color: $text-primary;
      border-color: $border-default;
    }
  }

  &__progress {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: $bg-tertiary;
    z-index: 1;

    &-fill {
      height: 100%;
      background: $accent-primary;
      transition: width 0.3s ease;
    }
  }
}

@keyframes miniCoverSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
