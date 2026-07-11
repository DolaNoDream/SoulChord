<script setup lang="ts">
import { ref, watch } from 'vue'
import { fetchSongHistory } from '@/api/agent'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

interface HistoryItem {
  song_id: string
  played_at: number
  feedback: string
  duration_played_ms: number
}

const items = ref<HistoryItem[]>([])
const total = ref(0)
const isLoading = ref(false)

const feedbackLabels: Record<string, string> = {
  like: '👍', dislike: '👎', skip: '⏭', favorite: '❤️',
}

watch(() => props.visible, async (v) => {
  if (v) {
    isLoading.value = true
    try {
      const data = await fetchSongHistory(50, 0)
      items.value = data.items
      total.value = data.total
    } catch { /* offline */ }
    isLoading.value = false
  }
})

function formatDate(ts: number): string {
  const d = new Date(ts)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function formatDuration(ms: number): string {
  const mins = Math.floor(ms / 60000)
  const secs = Math.floor((ms % 60000) / 1000)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<template>
  <Transition name="hpanel-slide">
    <div v-if="visible" class="history-panel">
      <div class="history-panel__header">
        <h4>📜 播放记录</h4>
        <span class="history-panel__count">共 {{ total }} 首</span>
        <button class="history-panel__close" @click="emit('close')">✕</button>
      </div>

      <div v-if="isLoading" class="history-panel__loading">加载中...</div>
      <div v-else-if="!items.length" class="history-panel__empty">还没有播放记录</div>

      <div v-else class="history-panel__list">
        <div v-for="item in items" :key="item.song_id + item.played_at" class="history-panel__item">
          <span class="history-panel__item-feedback">{{ feedbackLabels[item.feedback] || '🎵' }}</span>
          <span class="history-panel__item-song">{{ item.song_id }}</span>
          <span class="history-panel__item-time">{{ formatDate(item.played_at) }}</span>
          <span class="history-panel__item-duration">{{ formatDuration(item.duration_played_ms) }}</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style lang="scss">
.history-panel {
  position: absolute;
  top: 32px;
  left: 0;
  width: 280px;
  max-height: 360px;
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

    h4 { font-size: $font-size-sm; color: $text-primary; margin: 0; flex: 1; }
  }

  &__count { font-size: 11px; color: $text-muted; }

  &__close {
    width: 22px; height: 22px; display: flex; align-items: center; justify-content: center;
    background: none; border: 1px solid $border-subtle; border-radius: 50%;
    color: $text-muted; cursor: pointer; font-size: 11px;
    &:hover { color: $text-primary; border-color: $border-default; }
  }

  &__loading, &__empty {
    padding: 24px; text-align: center; color: $text-muted; font-size: $font-size-sm;
  }

  &__list { padding: 4px 0; }

  &__item {
    display: flex; align-items: center; gap: 6px; padding: 6px 12px;
    font-size: 11px;
    &:hover { background: $bg-glass; }
  }

  &__item-feedback { flex-shrink: 0; font-size: 12px; }
  &__item-song { flex: 1; color: $text-primary; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  &__item-time { color: $text-muted; flex-shrink: 0; }
  &__item-duration { color: $text-muted; flex-shrink: 0; font-variant-numeric: tabular-nums; min-width: 36px; text-align: right; }
}

.hpanel-slide-enter-active, .hpanel-slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.hpanel-slide-enter-from, .hpanel-slide-leave-to { transform: translateX(-20px); opacity: 0; }
</style>
