<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUserStore } from '@/stores/user'
import { useElectron } from '@/composables/useElectron'
import { fetchInit } from '@/api/agent'
import MiniWindow from '@/components/MiniWindow.vue'
import SettingsDrawer from '@/components/SettingsDrawer.vue'
import HistoryPanel from '@/components/HistoryPanel.vue'

const settingsStore = useSettingsStore()
const userStore = useUserStore()
const { minimize, maximize, close, isMaximized, isElectron: isInElectron } = useElectron()
const showDrawer = ref(false)
const showHistory = ref(false)

// 启动：连接后端 → 加载用户画像
onMounted(async () => {
  try {
    await fetchInit()
    await userStore.loadInit()
    console.log('[SoulChord] 后端已连接，persona:', userStore.agentInfo?.persona)
    settingsStore.syncToBackend()
  } catch {
    console.log('[SoulChord] 后端未启动，使用本地数据')
  }
})
</script>

<template>
  <MiniWindow v-if="isInElectron && false" />

  <div v-else class="app">
    <header v-if="isInElectron" class="app__titlebar drag-region">
      <button class="app__history-btn no-drag" @click="showHistory = !showHistory" title="播放记录">
        {{ showHistory ? '📜' : '📋' }}
      </button>
      <div class="app__titlebar-title">SoulChord</div>
      <div class="app__titlebar-controls no-drag">
        <button class="app__titlebar-btn" title="最小化" @click="minimize">─</button>
        <button class="app__titlebar-btn" :title="isMaximized ? '还原' : '最大化'" @click="maximize">
          <span v-if="isMaximized" class="app__icon app__icon--restore"></span>
          <span v-else class="app__icon app__icon--maximize"></span>
        </button>
        <button class="app__titlebar-btn app__titlebar-btn--close" title="关闭" @click="close">✕</button>
      </div>
    </header>

    <main class="app__main">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <button class="app__avatar-btn" @click="showDrawer = true" title="个人设置">
      <img v-if="userStore.getLocalAvatar()" :src="userStore.getLocalAvatar()" class="app__avatar-btn-img" />
      <span v-else>👤</span>
    </button>

    <SettingsDrawer :visible="showDrawer" @close="showDrawer = false" />
    <HistoryPanel :visible="showHistory" @close="showHistory = false" />
  </div>
</template>

<style lang="scss">
.app {
  display: flex; flex-direction: column; width: 100%; height: 100%; background: $bg-primary; color: $text-primary; position: relative;
  &__titlebar { display: flex; justify-content: space-between; align-items: center; height: 32px; padding: 0 8px; background: $bg-secondary; border-bottom: 1px solid $border-subtle; flex-shrink: 0;
    &-title { font-size: $font-size-xs; color: $text-muted; padding-left: 8px; }
    &-controls { display: flex; gap: 4px; }
    &-btn { width: 28px; height: 22px; display: flex; align-items: center; justify-content: center; background: none; border: none; color: $text-secondary; font-size: 12px; cursor: pointer; border-radius: 4px;
      &:hover { background: $bg-glass-hover; color: $text-primary; }
      &--close:hover { background: #ef4444; color: #fff; }
    }
  }
  &__main { flex: 1; overflow: hidden; }
  &__avatar-btn { position: absolute; top: 40px; right: 12px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: $bg-glass; border: 1px solid $border-subtle; border-radius: 50%; cursor: pointer; font-size: 18px; z-index: 10; transition: all 0.2s; padding: 0;
    &:hover { border-color: $accent-primary; transform: scale(1.08); box-shadow: 0 0 12px rgba($accent-primary, 0.2); }
    &-img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
  }
  &__icon { display: inline-block; width: 10px; height: 10px; position: relative;
    &--maximize { border: 1.5px solid currentColor; border-radius: 1px; }
    &--restore { &::before { content: ''; position: absolute; top: 2px; left: 0; width: 6px; height: 6px; border: 1.5px solid currentColor; border-radius: 1px; background: $bg-secondary; z-index: 1; }
      &::after { content: ''; position: absolute; top: 0; left: 2px; width: 6px; height: 6px; border: 1.5px solid currentColor; border-radius: 1px; background: $bg-secondary; } }
  }
}
.page-fade-enter-active, .page-fade-leave-active { transition: opacity 0.2s ease; }
.page-fade-enter-from, .page-fade-leave-to { opacity: 0; }
</style>
