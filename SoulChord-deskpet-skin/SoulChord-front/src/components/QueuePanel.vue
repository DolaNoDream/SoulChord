<script setup lang="ts">
/**
 * QueuePanel — 播放列表面板（时间线版）
 *
 * 布局：播放历史（向上滚动） → 正在播放（居中） → 待播队列（向下滚动）
 * 数据源：playerStore（响应式，无需 HTTP 轮询）
 */
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { usePlayerStore } from '@/stores/player'

const playerStore = usePlayerStore()
const nowRef = ref<HTMLElement | null>(null)

// ── 数据 ──

/** 播放历史：正序（下标0=最早），上限 50 首 */
const playedSongs = computed(() => playerStore.history.slice(-50))

/** 待播放队列 */
const upcomingQueue = computed(() => playerStore.queue)

/** 当前歌曲 */
const currentSong = computed(() => playerStore.currentSong)

/** 是否有内容 */
const hasContent = computed(() =>
  playedSongs.value.length > 0 || currentSong.value !== null || upcomingQueue.value.length > 0
)

// ── 居中滚动 ──

function centerNow() {
  if (nowRef.value) {
    nowRef.value.scrollIntoView({ block: 'center', behavior: 'auto' })
  }
}

onMounted(() => nextTick(centerNow))
watch(() => playerStore.currentSong?.id, () => nextTick(centerNow))

// ── 工具 ──

function fmtArtists(s: { artists?: Array<{ name: string }> }): string {
  return s.artists?.map(a => a.name).join(', ') || ''
}
</script>

<template>
  <div class="queue-panel">
    <!-- 头部 -->
    <div class="queue-panel__hd">
      <h3>🎶 播放列表</h3>
    </div>

    <!-- 空态 -->
    <div v-if="!hasContent" class="queue-panel__empty">
      <div class="queue-panel__empty-icon">🎵</div>
      <p>还没有播放记录</p>
      <p class="queue-panel__empty-hint">和 AI DJ 聊聊天，让 TA 为你推荐音乐</p>
    </div>

    <!-- 时间线 -->
    <div v-else class="queue-panel__tl">
      <!-- ── 播放历史（向上滚动） ── -->
      <div class="queue-panel__tl-cluster">
        <div v-if="playedSongs.length" class="queue-panel__tl-label">
          <span>播放历史</span>
          <span class="queue-panel__tl-label-dir">↑</span>
        </div>
        <div
          v-for="(s, i) in playedSongs"
          :key="'h' + s.id + i"
          class="queue-panel__tl-item queue-panel__tl-item--past"
        >
          <span class="queue-panel__tl-dot" />
          <img
            v-if="s.cover_url"
            :src="s.cover_url"
            class="queue-panel__tl-cover"
            alt=""
          />
          <span v-else class="queue-panel__tl-cover queue-panel__tl-cover--ph">🎵</span>
          <span class="queue-panel__tl-name">{{ s.name }}</span>
          <span v-if="fmtArtists(s)" class="queue-panel__tl-artist">{{ fmtArtists(s) }}</span>
        </div>
      </div>

      <!-- ── 正在播放（居中） ── -->
      <div v-if="currentSong" ref="nowRef" class="queue-panel__tl-now">
        <span class="queue-panel__tl-dot queue-panel__tl-dot--now" />
        <div class="queue-panel__tl-now-card">
          <div class="queue-panel__tl-now-badge">▶ 正在播放</div>
          <div class="queue-panel__tl-now-body">
            <img
              v-if="currentSong.cover_url"
              :src="currentSong.cover_url"
              class="queue-panel__tl-now-cover"
              alt=""
            />
            <div v-else class="queue-panel__tl-now-cover queue-panel__tl-now-cover--ph">🎵</div>
            <div class="queue-panel__tl-now-info">
              <span class="queue-panel__tl-now-name">{{ currentSong.name }}</span>
              <span v-if="fmtArtists(currentSong)" class="queue-panel__tl-now-artist">{{ fmtArtists(currentSong) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 接下来播放（向下滚动） ── -->
      <div class="queue-panel__tl-cluster">
        <div v-if="upcomingQueue.length" class="queue-panel__tl-label">
          <span>接下来播放</span>
          <span class="queue-panel__tl-label-dir">↓</span>
        </div>
        <div
          v-for="(s, i) in upcomingQueue"
          :key="'q' + s.id + i"
          class="queue-panel__tl-item queue-panel__tl-item--next"
        >
          <span class="queue-panel__tl-dot" />
          <img
            v-if="s.cover_url"
            :src="s.cover_url"
            class="queue-panel__tl-cover"
            alt=""
          />
          <span v-else class="queue-panel__tl-cover queue-panel__tl-cover--ph">🎵</span>
          <span class="queue-panel__tl-name">{{ s.name }}</span>
          <span v-if="fmtArtists(s)" class="queue-panel__tl-artist">{{ fmtArtists(s) }}</span>
          <span class="queue-panel__tl-order">#{{ i + 1 }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss">
.queue-panel {
  display: flex; flex-direction: column; height: 100%;

  // ── 头部 ──
  &__hd {
    flex-shrink: 0; padding: 12px 16px 8px;
    h3 { margin: 0; font-size: $font-size-lg; color: var(--text-primary); font-weight: 700; }
  }

  // ── 空态 ──
  &__empty {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 4px; padding: 40px 20px; text-align: center;
    color: var(--text-secondary);
    &-icon { font-size: 40px; margin-bottom: 8px; }
    &-hint { font-size: $font-size-xs; color: var(--text-muted); }
  }

  // ── 时间线容器 ──
  &__tl {
    flex: 1; overflow-y: auto; position: relative;
    padding: 4px 16px 16px;

    // 纵向时间线
    &::before {
      content: ''; position: absolute;
      left: 24px; top: 0; bottom: 0;
      width: 2px; background: $border-subtle;
      z-index: 0;
    }

    &::-webkit-scrollbar { width: 4px; }
    &::-webkit-scrollbar-thumb { background: $border-subtle; border-radius: 2px; }
  }

  // ── 时间线段落 ──
  &__tl-cluster { position: relative; z-index: 1; }

  // ── 段落标签 ──
  &__tl-label {
    display: flex; align-items: center; gap: 6px;
    padding: 12px 0 4px 40px;
    font-size: 10px; font-weight: 700; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.5px;
    &-dir { font-size: 12px; opacity: 0.6; }
  }

  // ── 时间线条目（通用） ──
  &__tl-item {
    position: relative; display: flex; align-items: center;
    gap: 8px; padding: 6px 8px 6px 40px;
    border-radius: $radius-sm; transition: background 0.15s;
    z-index: 1;

    &:hover { background: $bg-glass; }

    &--past { opacity: 0.55; }
    &--next { opacity: 0.85; }
  }

  // ── 圆点 ──
  &__tl-dot {
    position: absolute;
    left: 18px; top: 50%;
    transform: translateY(-50%);
    width: 8px; height: 8px;
    border-radius: 50%;
    background: $bg-tertiary;
    border: 2px solid $border-subtle;
    z-index: 2;
    transition: all 0.2s;

    &--now {
      width: 16px; height: 16px;
      left: 14px;
      background: $accent-primary;
      border-color: $accent-primary;
      box-shadow: 0 0 10px rgba($accent-primary, 0.45);
    }
  }

  // ── 封面 ──
  &__tl-cover {
    width: 24px; height: 24px; border-radius: 4px;
    object-fit: cover; flex-shrink: 0;
    &--ph {
      background: $bg-tertiary; display: inline-flex;
      align-items: center; justify-content: center; font-size: 11px;
    }
  }

  // ── 歌曲信息 ──
  &__tl-name {
    font-size: $font-size-xs; color: var(--text-primary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    min-width: 0; flex-shrink: 1;
  }
  &__tl-artist {
    font-size: 10px; color: var(--text-muted); flex-shrink: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    max-width: 80px;
  }
  &__tl-order {
    font-size: 10px; color: var(--text-muted); flex-shrink: 0;
    margin-left: auto;
  }

  // ── 正在播放（居中卡片） ──
  &__tl-now {
    position: relative; z-index: 1;
    padding: 12px 8px 12px 40px;
  }

  &__tl-now-card {
    background: rgba($accent-primary, 0.06);
    border: 1px solid rgba($accent-primary, 0.2);
    border-radius: $radius-md; padding: 12px;
  }

  &__tl-now-badge {
    font-size: 10px; font-weight: 700; color: $accent-primary;
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
  }

  &__tl-now-body {
    display: flex; align-items: center; gap: 12px;
  }

  &__tl-now-cover {
    width: 44px; height: 44px; border-radius: 6px;
    object-fit: cover; flex-shrink: 0;
    &--ph {
      background: $bg-tertiary; display: flex;
      align-items: center; justify-content: center; font-size: 20px;
    }
  }

  &__tl-now-info {
    display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1;
  }

  &__tl-now-name {
    font-size: $font-size-sm; color: var(--text-primary); font-weight: 600;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  &__tl-now-artist {
    font-size: 11px; color: var(--text-muted);
  }
}
</style>
