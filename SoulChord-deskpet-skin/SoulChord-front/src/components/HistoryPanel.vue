<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { fetchCurrentPlaylist } from '@/api/agent'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

interface PlayedItem {
  song_id: string
  song_name: string
  artist: string
  played_at: number
}

interface QueueItem {
  song_id: string
  name: string
  artist: string
  cover_url: string
}

interface CurrentSong {
  id: string
  name: string
  artists: Array<{ id: string; name: string }>
  cover_url: string
}

const currentSong = ref<CurrentSong | null>(null)
const queue = ref<QueueItem[]>([])
const played = ref<PlayedItem[]>([])
const isLoading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadData() {
  if (!props.visible) return
  isLoading.value = true
  try {
    const data = await fetchCurrentPlaylist()
    currentSong.value = data.current_song
    queue.value = data.queue || []
    played.value = data.played || []
  } catch {
    // offline
  }
  isLoading.value = false
}

watch(() => props.visible, (v) => {
  if (v) {
    loadData()
    // 每 5 秒自动刷新（队列/当前歌会变化）
    pollTimer = setInterval(loadData, 5000)
  } else {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

function artistName(song: CurrentSong | QueueItem): string {
  if ('artists' in song && Array.isArray(song.artists) && song.artists.length > 0) {
    return song.artists[0].name
  }
  return (song as any).artist || ''
}

function formatDate(ts: number): string {
  const d = new Date(ts)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

const isEmpty = () => !currentSong.value && queue.value.length === 0 && played.value.length === 0
</script>

<template>
  <Transition name="hpanel-slide">
    <div v-if="visible" class="hpanel">
      <div class="hpanel__header">
        <h4 class="hpanel__title">📋 播放列表</h4>
        <button class="hpanel__close" @click="emit('close')">✕</button>
      </div>

      <div v-if="isLoading" class="hpanel__loading">加载中...</div>
      <div v-else-if="isEmpty()" class="hpanel__empty">还没有播放记录</div>

      <div v-else class="hpanel__body">
        <!-- 正在播放 -->
        <div v-if="currentSong" class="hpanel__section">
          <div class="hpanel__section-label hpanel__section-label--now">▶ 正在播放</div>
          <div class="hpanel__now-item">
            <span class="hpanel__now-name">{{ currentSong.name }}</span>
            <span v-if="artistName(currentSong)" class="hpanel__now-artist">{{ artistName(currentSong) }}</span>
          </div>
        </div>

        <!-- 接下来 -->
        <div v-if="queue.length > 0" class="hpanel__section">
          <div class="hpanel__section-label">接下来</div>
          <div v-for="(item, i) in queue" :key="item.song_id + i" class="hpanel__q-item">
            <span class="hpanel__q-idx">{{ i + 1 }}</span>
            <span class="hpanel__q-name">{{ item.name }}</span>
            <span v-if="item.artist" class="hpanel__q-artist">{{ item.artist }}</span>
          </div>
        </div>

        <!-- 已播放 -->
        <div v-if="played.length > 0" class="hpanel__section">
          <div class="hpanel__section-label">已播放</div>
          <div v-for="item in played" :key="item.song_id" class="hpanel__p-item">
            <span class="hpanel__p-name">{{ item.song_name }}</span>
            <span v-if="item.artist" class="hpanel__p-artist">{{ item.artist }}</span>
            <span class="hpanel__p-time">{{ formatDate(item.played_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style lang="scss">
.hpanel {
  position: absolute;
  top: 32px;
  left: 0;
  width: 280px;
  max-height: 420px;
  background: $bg-secondary;
  border-right: 1px solid $border-subtle;
  border-bottom: 1px solid $border-subtle;
  border-radius: 0 0 $radius-md 0;
  z-index: 50;
  overflow-y: auto;
  display: flex;
  flex-direction: column;

  &__header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border-bottom: 1px solid $border-subtle;
    position: sticky;
    top: 0;
    background: $bg-secondary;
    z-index: 1;
  }

  &__title { font-size: $font-size-sm; color: $text-primary; margin: 0; flex: 1; }

  &__close {
    width: 22px; height: 22px; display: flex; align-items: center; justify-content: center;
    background: none; border: 1px solid $border-subtle; border-radius: 50%;
    color: $text-muted; cursor: pointer; font-size: 11px;
    &:hover { color: $text-primary; border-color: $border-default; }
  }

  &__loading, &__empty {
    padding: 24px; text-align: center; color: $text-muted; font-size: $font-size-sm;
  }

  &__body { padding: 6px 0; }

  &__section { padding: 4px 12px 8px; }
  &__section + &__section { border-top: 1px solid $border-subtle; padding-top: 8px; }

  &__section-label {
    font-size: 10px;
    color: $text-muted;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;

    &--now { color: $accent-primary; font-weight: 600; }
  }

  // 正在播放
  &__now-item {
    display: flex; align-items: center; gap: 6px; padding: 6px 8px;
    background: $bg-tertiary; border-radius: $radius-sm;
  }
  &__now-name { font-size: 12px; color: $accent-primary; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &__now-artist { font-size: 10px; color: $text-muted; flex-shrink: 0; }

  // 接下来
  &__q-item {
    display: flex; align-items: center; gap: 6px; padding: 4px 8px; font-size: 11px;
    &:hover { background: $bg-glass; border-radius: $radius-sm; }
  }
  &__q-idx { color: $text-muted; font-size: 10px; min-width: 14px; text-align: right; font-variant-numeric: tabular-nums; }
  &__q-name { flex: 1; color: $text-primary; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &__q-artist { color: $text-muted; font-size: 10px; flex-shrink: 0; }

  // 已播放
  &__p-item {
    display: flex; align-items: center; gap: 6px; padding: 4px 8px; font-size: 11px; color: $text-secondary;
    &:hover { background: $bg-glass; border-radius: $radius-sm; }
  }
  &__p-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &__p-artist { color: $text-muted; font-size: 10px; flex-shrink: 0; }
  &__p-time { color: $text-muted; font-size: 10px; flex-shrink: 0; }
}

.hpanel-slide-enter-active, .hpanel-slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.hpanel-slide-enter-from, .hpanel-slide-leave-to { transform: translateX(-20px); opacity: 0; }
</style>
