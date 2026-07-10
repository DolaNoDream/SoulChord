<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { useSettingsStore } from '@/stores/settings'
import { getUserProfile } from '@/api/agent'
import type { Song } from '@/types/music'

const userStore = useUserStore()
const settingsStore = useSettingsStore()
const isLoading = ref(false)
const errorMsg = ref<string | null>(null)
const avatarInputRef = ref<HTMLInputElement | null>(null)

onMounted(async () => {
  isLoading.value = true
  errorMsg.value = null
  try {
    await userStore.fetchProfile()
    if (!userStore.musicDNA) {
      errorMsg.value = '尚未完成音乐DNA分析'
    }
  } catch {
    errorMsg.value = '无法连接到AI服务，请确认后端已启动'
  } finally {
    isLoading.value = false
  }
})

/** 点击头像触发文件选择 */
function handleAvatarClick() {
  avatarInputRef.value?.click()
}

/** 选择头像文件后读取并更新 */
function handleAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  // 校验文件类型和大小（限制 5MB）
  if (!file.type.startsWith('image/')) {
    errorMsg.value = '请选择图片文件'
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    errorMsg.value = '图片大小不能超过 5MB'
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    const dataUrl = reader.result as string
    userStore.updateAvatar(dataUrl)
    // 同时保存到 localStorage 持久化
    localStorage.setItem('soulchord-avatar', dataUrl)
  }
  reader.readAsDataURL(file)

  // 重置 input 以便重复选择同一文件
  input.value = ''
}

/** 开始导入分析 */
async function handleImport() {
  userStore.completeOnboarding()
}

/** 音乐DNA维度标签 */
const dnaDimensions = [
  { key: 'energyLevel', label: '能量水平', low: '纯氛围', high: '高能量' },
  { key: 'vocalsPreference', label: '人声偏好', low: '纯器乐', high: '人声为主' },
  { key: 'noveltyScore', label: '探索倾向', low: '熟悉金曲', high: '探索新歌' },
] as const
</script>

<template>
  <div class="profile-view">
    <!-- 头部 -->
    <header class="profile-view__header">
      <!-- 可更换头像 -->
      <div class="profile-view__avatar" @click="handleAvatarClick" title="点击更换头像">
        <img
          v-if="userStore.profile?.avatarUrl"
          :src="userStore.profile.avatarUrl"
          class="profile-view__avatar-img"
        />
        <span v-else class="profile-view__avatar-placeholder">👤</span>
        <div class="profile-view__avatar-overlay">
          <span>📷</span>
        </div>
      </div>
      <!-- 隐藏的文件选择器 -->
      <input
        ref="avatarInputRef"
        type="file"
        accept="image/*"
        class="profile-view__avatar-input"
        @change="handleAvatarChange"
      />
      <h2 class="profile-view__name">
        {{ userStore.profile?.nickname ?? '音乐探索者' }}
      </h2>
      <p class="profile-view__stats" v-if="userStore.profile">
        🎵 {{ userStore.profile.totalSongsPlayed }} 首 ·
        ⏱️ {{ userStore.profile.totalHoursListened }} 小时
      </p>
    </header>

    <!-- 加载状态 -->
    <div v-if="isLoading" class="profile-view__loading">
      <div class="profile-view__loading-spinner"></div>
      <p>AI 正在分析你的音乐DNA...</p>
    </div>

    <!-- 音乐DNA -->
    <section v-else-if="userStore.musicDNA" class="profile-view__dna">
      <h3 class="profile-view__section-title">🧬 你的音乐DNA</h3>
      <p class="profile-view__dna-summary">{{ userStore.musicDNASummary }}</p>

      <!-- DNA 维度条 -->
      <div class="profile-view__dimensions">
        <div
          v-for="dim in dnaDimensions"
          :key="dim.key"
          class="profile-view__dimension"
        >
          <div class="profile-view__dimension-header">
            <span class="profile-view__dimension-label">{{ dim.label }}</span>
          </div>
          <div class="profile-view__dimension-bar">
            <div class="profile-view__dimension-track">
              <div
                class="profile-view__dimension-fill"
                :style="{ width: (userStore.musicDNA?.[dim.key] ?? 50) + '%' }"
              ></div>
              <div
                class="profile-view__dimension-dot"
                :style="{ left: (userStore.musicDNA?.[dim.key] ?? 50) + '%' }"
              ></div>
            </div>
            <div class="profile-view__dimension-labels">
              <span>{{ dim.low }}</span>
              <span>{{ dim.high }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 偏好标签 -->
      <div class="profile-view__tags">
        <div v-if="userStore.topGenres.length > 0" class="profile-view__tag-group">
          <h4>🎼 最爱风格</h4>
          <div class="profile-view__tag-list">
            <span
              v-for="g in userStore.topGenres"
              :key="g.genre"
              class="profile-view__tag"
              :style="{ opacity: 0.5 + g.weight * 0.5 }"
            >
              {{ g.genre }}
              <template v-if="g.trend === 'rising'">↑</template>
              <template v-else-if="g.trend === 'declining'">↓</template>
            </span>
          </div>
        </div>

        <div v-if="userStore.topArtists.length > 0" class="profile-view__tag-group">
          <h4>🎤 最爱艺人</h4>
          <div class="profile-view__tag-list">
            <span
              v-for="a in userStore.topArtists"
              :key="a.artist"
              class="profile-view__tag"
            >
              {{ a.artist }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- 空状态 -->
    <section v-else class="profile-view__empty">
      <div class="profile-view__empty-icon">🎧</div>
      <h3>{{ errorMsg ?? '尚未完成音乐DNA分析' }}</h3>
      <p>导入你喜欢的歌曲列表，让 AI DJ 了解你的音乐品味</p>
      <button class="profile-view__import-btn" @click="handleImport">
        导入歌曲列表
      </button>
      <p class="profile-view__import-hint">
        支持网易云音乐、QQ音乐歌单导入
      </p>
    </section>

    <!-- 设置面板（加载完成后始终显示） -->
    <section v-if="!isLoading" class="profile-view__settings">
      <h3 class="profile-view__section-title">⚙️ 设置</h3>

      <div class="profile-view__setting-item">
        <div class="profile-view__setting-info">
          <span class="profile-view__setting-label">🔝 窗口始终置顶</span>
          <span class="profile-view__setting-desc">桌面模式下窗口保持在其他应用之上</span>
        </div>
        <el-switch v-model="settingsStore.alwaysOnTop" @change="settingsStore.toggleAlwaysOnTop" />
      </div>

      <div class="profile-view__setting-item">
        <div class="profile-view__setting-info">
          <span class="profile-view__setting-label">▶️ 启动时自动播放</span>
          <span class="profile-view__setting-desc">打开应用时自动继续上次的播放</span>
        </div>
        <el-switch v-model="settingsStore.autoplayOnLaunch" />
      </div>

      <div class="profile-view__setting-item">
        <div class="profile-view__setting-info">
          <span class="profile-view__setting-label">😊 显示 AI DJ 情绪</span>
          <span class="profile-view__setting-desc">根据当前歌曲显示 AI DJ 的情绪状态</span>
        </div>
        <el-switch v-model="settingsStore.showDJEmotion" />
      </div>
    </section>
  </div>
</template>

<style lang="scss">
.profile-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;

  &__header {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 32px 20px 24px;
    border-bottom: 1px solid $border-subtle;
  }

  &__avatar {
    width: 72px;
    height: 72px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, $accent-primary, $accent-secondary);
    border-radius: 50%;
    font-size: 32px;
    margin-bottom: 12px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s;

    &:hover {
      transform: scale(1.05);

      .profile-view__avatar-overlay {
        opacity: 1;
      }
    }

    &-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 50%;
    }

    &-placeholder {
      font-size: 32px;
    }

    &-overlay {
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: rgba(0, 0, 0, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      transition: opacity 0.2s;
      pointer-events: none;

      span {
        font-size: 20px;
      }
    }

    &-input {
      display: none;
    }
  }

  &__name {
    font-size: $font-size-xl;
    font-weight: 700;
    color: $text-primary;
    margin: 0;
  }

  &__stats {
    font-size: $font-size-sm;
    color: $text-secondary;
    margin: 6px 0 0;
  }

  &__loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 60px 20px;
    gap: 16px;
    color: $text-secondary;

    &-spinner {
      width: 40px;
      height: 40px;
      border: 3px solid $border-subtle;
      border-top-color: $accent-primary;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
  }

  &__section-title {
    font-size: $font-size-lg;
    color: $text-primary;
    margin: 0 0 12px;
  }

  &__settings {
    padding: 20px;
    border-top: 1px solid $border-subtle;
  }

  &__setting-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 0;
    border-bottom: 1px solid $border-subtle;

    &:last-child {
      border-bottom: none;
    }
  }

  &__setting-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  &__setting-label {
    font-size: $font-size-base;
    color: $text-primary;
    font-weight: 500;
  }

  &__setting-desc {
    font-size: $font-size-xs;
    color: $text-muted;
  }

  &__section-title {
    font-size: $font-size-lg;
    color: $text-primary;
    margin: 0 0 12px;
  }

  &__dna {
    padding: 20px;

    &-summary {
      font-size: $font-size-sm;
      color: $accent-warm;
      font-style: italic;
      margin: 0 0 24px;
      line-height: 1.5;
    }
  }

  &__dimensions {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-bottom: 24px;
  }

  &__dimension {
    &-header {
      margin-bottom: 6px;
    }

    &-label {
      font-size: $font-size-sm;
      color: $text-secondary;
      font-weight: 600;
    }

    &-bar {
      // container
    }

    &-track {
      position: relative;
      height: 6px;
      background: $bg-tertiary;
      border-radius: 3px;
      margin-bottom: 4px;
    }

    &-fill {
      position: absolute;
      left: 0;
      top: 0;
      height: 100%;
      background: linear-gradient(to right, $accent-cool, $accent-primary);
      border-radius: 3px;
      transition: width 0.6s ease;
    }

    &-dot {
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 14px;
      height: 14px;
      background: #fff;
      border: 2px solid $accent-primary;
      border-radius: 50%;
      transition: left 0.6s ease;
    }

    &-labels {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: $text-muted;
    }
  }

  &__tags {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  &__tag-group {
    h4 {
      font-size: $font-size-sm;
      color: $text-secondary;
      margin: 0 0 8px;
    }
  }

  &__tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  &__tag {
    padding: 4px 12px;
    background: $bg-glass;
    border: 1px solid $border-subtle;
    border-radius: $radius-full;
    font-size: $font-size-xs;
    color: $text-primary;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 60px 20px;
    text-align: center;

    &-icon {
      font-size: 56px;
      margin-bottom: 16px;
    }

    h3 {
      font-size: $font-size-lg;
      color: $text-primary;
      margin: 0 0 8px;
    }

    p {
      font-size: $font-size-sm;
      color: $text-secondary;
      margin: 0 0 20px;
    }
  }

  &__import-btn {
    padding: 10px 28px;
    background: $accent-primary;
    border: none;
    border-radius: $radius-full;
    color: #fff;
    font-size: $font-size-base;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: $accent-secondary;
      transform: translateY(-1px);
    }
  }

  &__import-hint {
    font-size: $font-size-xs;
    color: $text-muted;
    margin-top: 10px;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
