<script setup lang="ts">
import { usePlayerStore } from '@/stores/player'
import SongCard from './SongCard.vue'
import type { Song } from '@/types/music'

defineProps<{
  collapsed?: boolean
}>()

const playerStore = usePlayerStore()

function handlePlay(song: Song) {
  playerStore.playSong(song, '') // play_url will be fetched separately
}

function handleClearQueue() {
  playerStore.clearQueue()
}
</script>

<template>
  <div class="playlist" :class="{ 'playlist--collapsed': collapsed }">
    <div class="playlist__header">
      <h3 class="playlist__title">
        播放列表
        <span class="playlist__count">({{ playerStore.queue.length }})</span>
      </h3>
      <button
        v-if="playerStore.queue.length > 0"
        class="playlist__clear-btn"
        @click="handleClearQueue"
      >
        清空
      </button>
    </div>

    <!-- 当前播放 -->
    <div v-if="playerStore.currentSong" class="playlist__current">
      <div class="playlist__current-label">当前播放</div>
      <SongCard
        :song="playerStore.currentSong"
        :show-reason="true"
        @play="handlePlay"
      />
    </div>

    <!-- 播放队列 -->
    <div class="playlist__queue">
      <template v-if="playerStore.queue.length > 0">
        <div class="playlist__queue-label">
          接下来
          <span class="playlist__mode-badge">
            {{ playerStore.playbackMode === 'random' ? '🔀 随机' : playerStore.playbackMode === 'singleLoop' ? '🔂 单曲循环' : '🔁 顺序' }}
          </span>
        </div>
        <TransitionGroup name="queue-item" tag="div" class="playlist__list">
          <SongCard
            v-for="(song, index) in playerStore.queue"
            :key="song.id"
            :song="song"
            :compact="true"
            class="playlist__item"
            @play="handlePlay"
          />
        </TransitionGroup>
      </template>
      <div v-else class="playlist__empty">
        <div class="playlist__empty-icon">🎵</div>
        <p class="playlist__empty-text">播放列表为空</p>
        <p class="playlist__empty-hint">试试跟AI DJ说你现在的心情吧</p>
      </div>
    </div>
  </div>
</template>

<style lang="scss">
.playlist {
  display: flex;
  flex-direction: column;
  height: 100%;

  &--collapsed {
    .playlist__current,
    .playlist__queue {
      display: none;
    }
  }

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    flex-shrink: 0;
  }

  &__title {
    font-size: $font-size-lg;
    font-weight: 700;
    color: $text-primary;
    margin: 0;
  }

  &__count {
    font-size: $font-size-sm;
    color: $text-muted;
    font-weight: 400;
  }

  &__clear-btn {
    background: none;
    border: 1px solid $border-default;
    color: $text-secondary;
    padding: 4px 12px;
    border-radius: $radius-full;
    font-size: $font-size-xs;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      border-color: $accent-primary;
      color: $accent-primary;
    }
  }

  &__current {
    padding: 0 16px 12px;
    border-bottom: 1px solid $border-subtle;
  }

  &__current-label,
  &__queue-label {
    font-size: $font-size-xs;
    color: $text-muted;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__mode-badge {
    font-size: 10px;
    background: $bg-tertiary;
    padding: 2px 8px;
    border-radius: $radius-full;
    color: $text-secondary;
  }

  &__queue {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    text-align: center;

    &-icon {
      font-size: 48px;
      margin-bottom: 12px;
    }

    &-text {
      font-size: $font-size-base;
      color: $text-secondary;
      margin: 0 0 4px;
    }

    &-hint {
      font-size: $font-size-sm;
      color: $text-muted;
      margin: 0;
    }
  }
}

// 队列动画
.queue-item-enter-active {
  transition: all 0.3s ease;
}

.queue-item-leave-active {
  transition: all 0.2s ease;
}

.queue-item-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.queue-item-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
</style>
