<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { useSettingsStore } from '@/stores/settings'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const settingsStore = useSettingsStore()

onMounted(() => {
  if (!userStore.isProfileLoaded) {
    userStore.loadProfile()
  }
})

function formatDate(ts: number): string {
  if (!ts || ts === 0) return '暂无数据'
  return new Date(ts).toLocaleString('zh-CN')
}

async function handleAnalyze() {
  if (!settingsStore.hasLlmKey) {
    ElMessage.warning('请先在设置中配置 LLM API Key')
    return
  }
  const result = await userStore.requestAnalyze()
  if (result) {
    ElMessage.success('AI 画像分析完成！')
  } else {
    ElMessage.error('画像分析失败，请检查 LLM API Key 是否有效')
  }
}
</script>

<template>
  <div class="profile-panel">
    <div class="profile-panel__header">
      <h3>🧬 音乐画像</h3>
      <button
        class="profile-panel__analyze-btn"
        :disabled="userStore.isAnalyzing"
        @click="handleAnalyze"
      >
        {{ userStore.isAnalyzing ? '分析中...' : '🔄 重新分析画像' }}
      </button>
    </div>

    <div v-if="!userStore.isProfileLoaded && userStore.isAnalyzing" class="profile-panel__loading">
      加载中...
    </div>

    <div v-else class="profile-panel__content">
      <!-- AI 生成音乐偏好（只读） -->
      <div class="profile-panel__section">
        <h4 class="profile-panel__section-title">🎵 AI 音乐偏好画像 <span class="profile-panel__readonly-tag">AI 自动生成</span></h4>

        <div class="profile-panel__field">
          <span class="profile-panel__label">喜爱曲风</span>
          <div class="profile-panel__tags">
            <span v-if="userStore.topGenres.length === 0" class="profile-panel__nodata">暂无数据 — 导入歌单后自动分析</span>
            <span v-for="g in userStore.topGenres" :key="g" class="profile-panel__tag profile-panel__tag--genre">{{ g }}</span>
          </div>
        </div>

        <div class="profile-panel__field">
          <span class="profile-panel__label">喜爱歌手</span>
          <div class="profile-panel__tags">
            <span v-if="userStore.topArtists.length === 0" class="profile-panel__nodata">暂无数据 — 导入歌单后自动分析</span>
            <span v-for="a in userStore.topArtists" :key="a" class="profile-panel__tag profile-panel__tag--artist">{{ a }}</span>
          </div>
        </div>

        <div class="profile-panel__field">
          <span class="profile-panel__label">排斥曲风</span>
          <div class="profile-panel__tags">
            <span v-if="!userStore.profile?.disliked_genres?.length" class="profile-panel__nodata">暂无数据</span>
            <span v-for="g in userStore.profile?.disliked_genres ?? []" :key="g" class="profile-panel__tag profile-panel__tag--dislike">{{ g }}</span>
          </div>
        </div>

        <div class="profile-panel__field">
          <span class="profile-panel__label">音乐偏好描述</span>
          <p class="profile-panel__desc">{{ userStore.profile?.music_preference_desc || '暂无数据 — 导入歌单后自动分析' }}</p>
        </div>

        <div class="profile-panel__field">
          <span class="profile-panel__label">AI 一句话总结</span>
          <p class="profile-panel__desc profile-panel__desc--conclusion">
            {{ userStore.profile?.AI_conclusion || '暂无数据 — 导入歌单后自动分析' }}
          </p>
        </div>

        <div class="profile-panel__field">
          <span class="profile-panel__label">画像最后更新</span>
          <span class="profile-panel__value profile-panel__value--time">{{ formatDate(userStore.profile?.update_at ?? 0) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss">
.profile-panel {
  display: flex; flex-direction: column; height: 100%; padding: 12px; overflow-y: auto;

  &__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
    h3 { font-size: $font-size-lg; color: var(--text-primary); margin: 0; font-weight: 700; }
  }
  &__analyze-btn { padding: 6px 14px; background: rgba($accent-primary, 0.1);
    border: 1px solid rgba($accent-primary, 0.3); border-radius: $radius-full;
    color: $accent-primary; font-size: $font-size-xs; cursor: pointer;
    &:hover:not(:disabled) { background: rgba($accent-primary, 0.2); }
    &:disabled { opacity: 0.5; cursor: not-allowed; }
  }
  &__loading { padding: 24px; text-align: center; color: var(--text-muted); }
  &__content { display: flex; flex-direction: column; gap: 20px; }

  &__section { background: $bg-glass; border: 1px solid $border-subtle;
    border-radius: $radius-md; padding: 14px 16px; }
  &__section-title { font-size: $font-size-sm; color: var(--text-secondary); margin: 0 0 12px;
    font-weight: 600; display: flex; align-items: center; gap: 8px; }
  &__readonly-tag { font-size: 10px; padding: 1px 6px; background: rgba($accent-warm, 0.15);
    color: $accent-warm; border-radius: $radius-full; font-weight: 400; }

  &__field { margin-bottom: 12px; &:last-child { margin-bottom: 0; } }
  &__label { font-size: $font-size-xs; color: var(--text-muted); display: block; margin-bottom: 4px; }
  &__value { font-size: $font-size-sm; color: var(--text-primary);
    &--time { color: var(--text-muted); font-size: $font-size-xs; }
  }

  &__tags { display: flex; flex-wrap: wrap; gap: 6px; }
  &__tag { padding: 3px 10px; border-radius: $radius-full; font-size: 11px;
    &--genre { background: rgba($accent-primary, 0.12); color: $accent-primary;
      border: 1px solid rgba($accent-primary, 0.2); }
    &--artist { background: rgba($accent-warm, 0.12); color: $accent-warm;
      border: 1px solid rgba($accent-warm, 0.2); }
    &--dislike { background: rgba(#ef4444, 0.1); color: #f87171;
      border: 1px solid rgba(#ef4444, 0.15); }
  }
  &__nodata { font-size: 11px; color: var(--text-muted); font-style: italic; }
  &__desc { font-size: $font-size-sm; color: var(--text-secondary); line-height: 1.6; margin: 0;
    &--conclusion { color: $accent-warm; font-style: italic; font-size: $font-size-base; } }
}
</style>
