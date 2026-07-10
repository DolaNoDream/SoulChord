<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUserStore } from '@/stores/user'
import { useElectron } from '@/composables/useElectron'
import { healthCheck } from '@/api/agent'
import MiniWindow from '@/components/MiniWindow.vue'
import SettingsDrawer from '@/components/SettingsDrawer.vue'

const settingsStore = useSettingsStore()
const userStore = useUserStore()
const { minimize, maximize, close, isMaximized, isElectron: isInElectron } = useElectron()
const showDrawer = ref(false)

// 应用启动：检测后端 → 加载用户画像
onMounted(async () => {
  const isBackendOnline = await healthCheck()
  if (isBackendOnline) {
    console.log('[SoulChord] 后端已连接')
  } else {
    console.log('[SoulChord] 后端未启动，使用本地数据运行')
  }
  userStore.fetchProfile()
})
</script>

<template>
  <!-- 迷你悬浮窗模式 -->
  <MiniWindow v-if="settingsStore.isMiniMode" />

  <!-- 完整模式 -->
  <div v-else class="app" :class="{ 'app--dark': settingsStore.isDark }">
    <!-- 自定义标题栏 -->
    <header v-if="isInElectron" class="app__titlebar drag-region">
      <div class="app__titlebar-title">SoulChord</div>
      <div class="app__titlebar-controls no-drag">
        <button class="app__titlebar-btn" title="最小化" @click="minimize">─</button>
        <button
          class="app__titlebar-btn"
          :title="isMaximized ? '还原' : '最大化'"
          @click="maximize"
        >
          <span v-if="isMaximized" class="app__icon app__icon--restore"></span>
          <span v-else class="app__icon app__icon--maximize"></span>
        </button>
        <button class="app__titlebar-btn app__titlebar-btn--close" title="关闭" @click="close">✕</button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="app__main">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 右上角头像按钮 -->
    <button class="app__avatar-btn" @click="showDrawer = true" title="个人设置">
      <img
        v-if="userStore.profile?.avatarUrl"
        :src="userStore.profile.avatarUrl"
        class="app__avatar-btn-img"
      />
      <span v-else>👤</span>
    </button>

    <!-- 设置抽屉 -->
    <SettingsDrawer :visible="showDrawer" @close="showDrawer = false" />
  </div>
</template>

<style lang="scss">
.app {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: $bg-primary;
  color: $text-primary;
  position: relative;

  &--dark {
    // 暗色主题（默认）
  }

  // ---- 自定义标题栏 ----
  &__titlebar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 32px;
    padding: 0 8px;
    background: $bg-secondary;
    border-bottom: 1px solid $border-subtle;
    flex-shrink: 0;

    &-title {
      font-size: $font-size-xs;
      color: $text-muted;
      padding-left: 8px;
    }

    &-controls {
      display: flex;
      gap: 4px;
    }

    &-btn {
      width: 28px;
      height: 22px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: none;
      border: none;
      color: $text-secondary;
      font-size: 12px;
      cursor: pointer;
      border-radius: 4px;

      &:hover {
        background: $bg-glass-hover;
        color: $text-primary;
      }

      &--close:hover {
        background: #ef4444;
        color: #fff;
      }
    }
  }

  // 窗口按钮图标（CSS 绘制）
  &__icon {
    display: inline-block;
    width: 10px;
    height: 10px;
    position: relative;

    // 最大化图标：空心方框
    &--maximize {
      border: 1.5px solid currentColor;
      border-radius: 1px;
    }

    // 还原图标：两个重叠方框
    &--restore {
      &::before {
        content: '';
        position: absolute;
        top: 2px;
        left: 0;
        width: 6px;
        height: 6px;
        border: 1.5px solid currentColor;
        border-radius: 1px;
        background: $bg-secondary;
        z-index: 1;
      }
      &::after {
        content: '';
        position: absolute;
        top: 0;
        left: 2px;
        width: 6px;
        height: 6px;
        border: 1.5px solid currentColor;
        border-radius: 1px;
        background: $bg-secondary;
      }
    }
  }

  // ---- 主内容区 ----
  &__main {
    flex: 1;
    overflow: hidden;
  }

  // ---- 右上角头像按钮 ----
  &__avatar-btn {
    position: absolute;
    top: 40px;
    right: 12px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: $bg-glass;
    border: 1px solid $border-subtle;
    border-radius: 50%;
    cursor: pointer;
    font-size: 18px;
    z-index: 10;
    transition: all 0.2s;
    padding: 0;

    &:hover {
      border-color: $accent-primary;
      transform: scale(1.08);
      box-shadow: 0 0 12px rgba($accent-primary, 0.2);
    }

    &-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 50%;
    }
  }
}

// ---- 页面过渡动画 ----
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
