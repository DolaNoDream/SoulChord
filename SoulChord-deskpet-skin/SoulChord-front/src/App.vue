<script setup lang="ts">
import { ref, onMounted, provide, readonly } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUserStore } from '@/stores/user'
import { usePlaylistStore } from '@/stores/playlist'
import { usePlayerStore } from '@/stores/player'
import { useElectron } from '@/composables/useElectron'
import { fetchInit } from '@/api/agent'
import SettingsDrawer from '@/components/SettingsDrawer.vue'
import DotGrid from '@/components/DotGrid.vue'

const settingsStore = useSettingsStore()
const userStore = useUserStore()
const playlistStore = usePlaylistStore()
const playerStore = usePlayerStore()
const { minimize, maximize, close, isMaximized, isElectron: isInElectron } = useElectron()
const showDrawer = ref(false)
const initDone = ref(false)
provide('initDone', readonly(initDone))

// ── 日夜主题 ──
const isDark = ref(true)

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('theme-light', !isDark.value)
  localStorage.setItem('soulchord-theme', isDark.value ? 'dark' : 'light')
}

// 启动时恢复主题偏好
function restoreTheme() {
  const saved = localStorage.getItem('soulchord-theme')
  if (saved === 'light') {
    isDark.value = false
    document.documentElement.classList.add('theme-light')
  }
}
restoreTheme()

// 启动：连接后端 → 加载用户画像 + 拉取后端设置 + 歌单列表
onMounted(async () => {
  try {
    const initData = await fetchInit()
    // 直接设置数据（避免 userStore.loadInit 再次调 fetchInit）
    if (initData.user_profile) userStore.profile = initData.user_profile
    if (initData.agent) userStore.agentInfo = initData.agent
    userStore.isProfileLoaded = true
    // 从后端 settings 恢复设置
    if (initData.settings) {
      settingsStore.loadFromBackend(initData.settings as Record<string, unknown>)
    }
    // 加载网易云登录状态
    if (initData.netease_status) {
      settingsStore.setNeteaseStatus(
        initData.netease_status.login_status,
        initData.netease_status.nickname,
      )
    }
    // 加载本地歌单列表
    if (initData.playlists) {
      playlistStore.setFromInit(initData.playlists)
    }
    console.log('[SoulChord] 后端已连接，persona:', userStore.agentInfo?.persona)
    settingsStore.syncToBackend()
    initDone.value = true  // 通知 DashboardView 可以建立 WS 连接
    // 刷新后从缓存恢复播放状态（界面不空白）
    playerStore.restoreFromCache()
  } catch {
    console.log('[SoulChord] 后端未启动，使用本地数据')
    initDone.value = true  // 即使后端不可用也允许进入界面
    playerStore.restoreFromCache()
  }
})
</script>

<template>
  <DotGrid />
  <div class="app">
    <header class="app__titlebar" :class="{ 'drag-region': isInElectron }">
      <div class="app__titlebar-left">
        <span class="app__status-dot"></span>
        <span class="app__titlebar-title">SoulChord</span>
      </div>
      <div class="app__titlebar-right">
        <div class="app__onair">
          <span class="app__onair-dot"></span>
          <span class="app__onair-text">ON AIR</span>
        </div>
        <button class="app__titlebar-btn app__theme-btn no-drag" :title="isDark ? '切换到白天' : '切换到黑夜'" @click="toggleTheme">{{ isDark ? '☾' : '☀' }}</button>
        <button class="app__titlebar-btn app__settings-btn no-drag" title="个人设置" @click="showDrawer = true">⚙</button>
        <div v-if="isInElectron" class="app__titlebar-controls no-drag">
          <button class="app__titlebar-btn" title="最小化" @click="minimize">─</button>
          <button class="app__titlebar-btn" :title="isMaximized ? '还原' : '最大化'" @click="maximize">
            <span v-if="isMaximized" class="app__icon app__icon--restore"></span>
            <span v-else class="app__icon app__icon--maximize"></span>
          </button>
          <button class="app__titlebar-btn app__titlebar-btn--close" title="关闭" @click="close">✕</button>
        </div>
      </div>
    </header>

    <main class="app__main">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <SettingsDrawer :visible="showDrawer" @close="showDrawer = false" />
  </div>
</template>

<style lang="scss">
.app {
  display: flex; flex-direction: column; width: 100%; height: 100%; background: transparent; color: var(--text-primary); position: relative; z-index: 1; transition: color 0.3s ease;

  &__titlebar { display: flex; justify-content: space-between; align-items: center; height: 32px; padding: 0 10px; background: var(--bg-glass); border-bottom: 1px solid var(--border-subtle); flex-shrink: 0;
    &-left, &-right { display: flex; align-items: center; gap: 8px; }
    &-right { gap: 4px; }
    &-title { font-family: $font-mono; font-size: $font-size-sm; font-weight: 500; color: var(--text-primary); letter-spacing: 0.5px; padding-left: 4px; }
    &-btn { width: 28px; height: 22px; display: flex; align-items: center; justify-content: center; background: none; border: none; color: var(--text-secondary); font-size: 12px; cursor: pointer; border-radius: 4px;
      &:hover { background: var(--bg-glass-hover); color: var(--text-primary); }
      &--close:hover { background: #ef4444; color: #fff; }
    }
  }

  /* ── 状态圆点 ── */
  &__status-dot { width: 6px; height: 6px; border-radius: 50%; background: $accent-primary; box-shadow: 0 0 6px rgba($accent-primary, 0.6); animation: pulse 2s infinite; flex-shrink: 0; }

  /* ── ON AIR ── */
  &__onair { display: flex; align-items: center; gap: 5px; padding: 2px 8px; border: 1px solid rgba($accent-primary, 0.3); border-radius: $radius-full;
    &-dot { width: 5px; height: 5px; border-radius: 50%; background: $accent-primary; animation: pulse 2s infinite; flex-shrink: 0; }
    &-text { font-family: $font-mono; font-size: 9px; font-weight: 500; color: $accent-primary; letter-spacing: 1.5px; text-transform: uppercase; }
  }

  /* ── 设置齿轮 ── */
  &__settings-btn { font-size: 14px; padding: 0 4px; opacity: 0.5;
    &:hover { opacity: 1; }
  }

  /* ── 主题切换 ── */
  &__theme-btn { font-size: 13px; padding: 0 4px; opacity: 0.5;
    &:hover { opacity: 1; }
  }

  &__main { flex: 1; overflow: hidden; }

  &__icon { display: inline-block; width: 10px; height: 10px; position: relative;
    &--maximize { border: 1.5px solid currentColor; border-radius: 1px; }
    &--restore { &::before { content: ''; position: absolute; top: 2px; left: 0; width: 6px; height: 6px; border: 1.5px solid currentColor; border-radius: 1px; background: $bg-secondary; z-index: 1; }
      &::after { content: ''; position: absolute; top: 0; left: 2px; width: 6px; height: 6px; border: 1.5px solid currentColor; border-radius: 1px; background: $bg-secondary; } }
  }
}
.page-fade-enter-active, .page-fade-leave-active { transition: opacity 0.2s ease; }
.page-fade-enter-from, .page-fade-leave-to { opacity: 0; }
</style>
