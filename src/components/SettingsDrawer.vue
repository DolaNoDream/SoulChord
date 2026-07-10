<script setup lang="ts">
import { ref, watch } from 'vue'
import { useUserStore } from '@/stores/user'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const userStore = useUserStore()
const settingsStore = useSettingsStore()
const avatarInputRef = ref<HTMLInputElement | null>(null)
const isEditingName = ref(false)
const editingName = ref('')
const nameInputRef = ref<HTMLInputElement | null>(null)
const showImportDialog = ref(false)
const importText = ref('')
const isImporting = ref(false)

// 每次打开设置面板时，从后端拉取最新的用户画像
watch(() => props.visible, (v) => {
  if (v) userStore.fetchProfile()
})

/** 点击头像触发文件选择 */
function handleAvatarClick() {
  avatarInputRef.value?.click()
}

/** 选择头像文件 */
function handleAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) return
  if (file.size > 5 * 1024 * 1024) return

  const reader = new FileReader()
  reader.onload = () => {
    userStore.updateAvatar(reader.result as string)
    localStorage.setItem('soulchord-avatar', reader.result as string)
  }
  reader.readAsDataURL(file)
  input.value = ''
}

/** 开始编辑昵称 */
function startEditName() {
  editingName.value = userStore.profile?.nickname ?? '音乐探索者'
  isEditingName.value = true
  // 等 DOM 更新后聚焦输入框
  setTimeout(() => nameInputRef.value?.focus(), 100)
}

/** 确认修改昵称 */
function confirmEditName() {
  const name = editingName.value.trim()
  if (name) {
    userStore.updateNickname(name)
  }
  isEditingName.value = false
}

/** 键盘事件：回车确认，Esc 取消 */
function handleNameKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    confirmEditName()
  } else if (e.key === 'Escape') {
    isEditingName.value = false
  }
}

/** 打开导入歌单对话框 */
function openImportDialog() {
  importText.value = ''
  showImportDialog.value = true
}

/** 解析并导入歌单 */
async function handleImport() {
  const text = importText.value.trim()
  if (!text) return

  isImporting.value = true
  // 解析 "歌名 - 歌手" 格式，每行一首
  const lines = text.split('\n').filter(l => l.trim())
  const songs = lines.map((line, i) => {
    const parts = line.split('-').map(s => s.trim())
    return {
      id: `import_${i}`,
      title: parts[0] || line,
      artist: parts[1] || '未知歌手',
      album: '',
      coverUrl: '',
      audioUrl: '',
      duration: 0,
      genres: [],
      emotion: 'neutral' as const,
      bpm: null,
      year: null,
      source: 'local' as const,
      externalId: null,
    }
  })

  try {
    await userStore.importFavoriteSongs(songs)
  } finally {
    isImporting.value = false
    showImportDialog.value = false
  }
}
</script>

<template>
  <!-- 遮罩层 -->
  <Transition name="drawer-fade">
    <div v-if="visible" class="drawer-overlay" @click="emit('close')" />
  </Transition>

  <!-- 抽屉面板 -->
  <Transition name="drawer-slide">
    <div v-if="visible" class="settings-drawer">
      <!-- 头部 -->
      <div class="settings-drawer__header">
        <h3>个人设置</h3>
        <button class="settings-drawer__close" @click="emit('close')">✕</button>
      </div>

      <!-- 用户信息 -->
      <div class="settings-drawer__user">
        <div class="settings-drawer__avatar" @click="handleAvatarClick" title="点击更换头像">
          <img
            v-if="userStore.profile?.avatarUrl"
            :src="userStore.profile.avatarUrl"
            class="settings-drawer__avatar-img"
          />
          <span v-else>👤</span>
          <div class="settings-drawer__avatar-overlay">📷</div>
        </div>
        <input
          ref="avatarInputRef"
          type="file"
          accept="image/*"
          class="settings-drawer__file-input"
          @change="handleAvatarChange"
        />
        <div class="settings-drawer__user-info">
          <!-- 编辑模式 -->
          <div v-if="isEditingName" class="settings-drawer__name-edit">
            <input
              ref="nameInputRef"
              v-model="editingName"
              class="settings-drawer__name-input"
              maxlength="20"
              @keydown="handleNameKeydown"
              @blur="confirmEditName"
            />
          </div>
          <!-- 显示模式 -->
          <div v-else class="settings-drawer__name-display" @click="startEditName" title="点击修改昵称">
            <span class="settings-drawer__nickname">{{ userStore.profile?.nickname ?? '音乐探索者' }}</span>
            <span class="settings-drawer__edit-icon">✎</span>
          </div>
          <span v-if="userStore.profile" class="settings-drawer__stats">
            🎵 {{ userStore.profile.totalSongsPlayed }} 首 · ⏱️ {{ userStore.profile.totalHoursListened }}h
          </span>
        </div>
      </div>

      <!-- 导入歌单按钮 -->
      <button class="settings-drawer__import-btn" @click="openImportDialog">
        📥 导入歌单
      </button>
      <p class="settings-drawer__import-hint">支持网易云、QQ音乐歌单，让 AI 了解你的品味</p>

      <!-- 导入歌单对话框 -->
      <div v-if="showImportDialog" class="import-dialog-overlay" @click.self="showImportDialog = false">
        <div class="import-dialog">
          <h4>导入喜欢的歌曲</h4>
          <p class="import-dialog__hint">每行一首，格式：歌名 - 歌手</p>
          <textarea
            v-model="importText"
            class="import-dialog__textarea"
            rows="8"
            placeholder="晴天 - 周杰伦&#10;River Flows In You - Yiruma&#10;Lose Yourself - Eminem"
          ></textarea>
          <div class="import-dialog__actions">
            <button class="import-dialog__btn import-dialog__btn--cancel" @click="showImportDialog = false">取消</button>
            <button
              class="import-dialog__btn import-dialog__btn--confirm"
              :disabled="!importText.trim() || isImporting"
              @click="handleImport"
            >
              {{ isImporting ? '分析中...' : '提交分析' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 设置项 -->
      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">⚙️ 设置</h4>

        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info">
            <span>🔝 窗口始终置顶</span>
            <span class="settings-drawer__item-desc">桌面模式下窗口保持在其他应用之上</span>
          </div>
          <el-switch v-model="settingsStore.alwaysOnTop" @change="settingsStore.toggleAlwaysOnTop" size="small" />
        </div>

        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info">
            <span>▶️ 启动时自动播放</span>
            <span class="settings-drawer__item-desc">打开应用后自动继续上次播放</span>
          </div>
          <el-switch v-model="settingsStore.autoplayOnLaunch" size="small" />
        </div>

        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info">
            <span>😊 显示 AI DJ 情绪</span>
            <span class="settings-drawer__item-desc">根据歌曲显示 AI DJ 情绪状态</span>
          </div>
          <el-switch v-model="settingsStore.showDJEmotion" size="small" />
        </div>
      </div>

      <!-- 音乐DNA -->
      <div v-if="userStore.musicDNA" class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">🧬 音乐DNA</h4>
        <p class="settings-drawer__dna-summary">{{ userStore.musicDNASummary }}</p>

        <div v-if="userStore.topGenres.length" class="settings-drawer__tags">
          <span v-for="g in userStore.topGenres" :key="g.genre" class="settings-drawer__tag">
            {{ g.genre }}
          </span>
        </div>

        <div v-if="userStore.topArtists.length" class="settings-drawer__tags" style="margin-top: 8px;">
          <span v-for="a in userStore.topArtists" :key="a.artist" class="settings-drawer__tag settings-drawer__tag--artist">
            🎤 {{ a.artist }}
          </span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style lang="scss">
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 100;
  backdrop-filter: blur(2px);
}

.settings-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 300px;
  height: 100%;
  background: $bg-secondary;
  border-left: 1px solid $border-subtle;
  z-index: 101;
  overflow-y: auto;
  padding: 20px 16px;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    h3 {
      font-size: $font-size-lg;
      color: $text-primary;
      margin: 0;
    }
  }

  &__close {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid $border-subtle;
    border-radius: 50%;
    color: $text-secondary;
    cursor: pointer;
    font-size: 14px;

    &:hover {
      color: $text-primary;
      border-color: $border-default;
    }
  }

  &__user {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 20px;
    border-bottom: 1px solid $border-subtle;
    margin-bottom: 20px;
  }

  &__avatar {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: linear-gradient(135deg, $accent-primary, $accent-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    flex-shrink: 0;

    &:hover &-overlay {
      opacity: 1;
    }

    &-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
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
      font-size: 14px;
    }
  }

  &__file-input {
    display: none;
  }

  &__user-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  &__nickname {
    font-size: $font-size-base;
    color: $text-primary;
    font-weight: 600;
  }

  &__name-display {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
    transition: background 0.15s;

    &:hover {
      background: rgba($accent-primary, 0.1);

      .settings-drawer__edit-icon {
        opacity: 1;
      }
    }
  }

  &__edit-icon {
    font-size: 11px;
    color: $text-muted;
    opacity: 0;
    transition: opacity 0.15s;
  }

  &__name-edit {
    margin-bottom: 2px;
  }

  &__name-input {
    width: 100%;
    padding: 4px 8px;
    background: $bg-tertiary;
    border: 1px solid $accent-primary;
    border-radius: 4px;
    color: $text-primary;
    font-size: $font-size-base;
    font-weight: 600;
    outline: none;
  }

  &__stats {
    font-size: 11px;
    color: $text-muted;
  }

  &__section {
    padding-bottom: 20px;
    border-bottom: 1px solid $border-subtle;
    margin-bottom: 20px;

    &:last-child {
      border-bottom: none;
      margin-bottom: 0;
    }
  }

  &__import-btn {
    width: 100%;
    padding: 10px;
    margin-top: 12px;
    background: rgba($accent-primary, 0.1);
    border: 1px dashed rgba($accent-primary, 0.3);
    border-radius: $radius-md;
    color: $accent-primary;
    font-size: $font-size-sm;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: rgba($accent-primary, 0.2);
      border-style: solid;
    }
  }

  &__import-hint {
    font-size: 11px;
    color: $text-muted;
    margin: 6px 0 0;
  }

  &__section-title {
    font-size: $font-size-sm;
    color: $text-secondary;
    margin: 0 0 12px;
    font-weight: 600;
  }

  &__item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;

    &-info {
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: $font-size-sm;
      color: $text-primary;
    }

    &-desc {
      font-size: 11px;
      color: $text-muted;
    }
  }

  &__dna-summary {
    font-size: $font-size-sm;
    color: $accent-warm;
    font-style: italic;
    margin: 0 0 10px;
    line-height: 1.5;
  }

  &__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  &__tag {
    padding: 3px 10px;
    background: $bg-glass;
    border: 1px solid $border-subtle;
    border-radius: $radius-full;
    font-size: 11px;
    color: $text-secondary;

    &--artist {
      background: rgba($accent-primary, 0.1);
      border-color: rgba($accent-primary, 0.2);
    }
  }
}

// 过渡动画
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.25s ease;
}
.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.25s ease;
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
}

// 导入歌单对话框
.import-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.import-dialog {
  background: $bg-secondary;
  border: 1px solid $border-subtle;
  border-radius: $radius-lg;
  padding: 24px;
  width: 320px;
  max-width: 90vw;

  h4 {
    margin: 0 0 8px;
    font-size: $font-size-base;
    color: $text-primary;
  }

  &__hint {
    font-size: $font-size-xs;
    color: $text-muted;
    margin: 0 0 12px;
  }

  &__textarea {
    width: 100%;
    padding: 10px 12px;
    background: $bg-tertiary;
    border: 1px solid $border-subtle;
    border-radius: $radius-sm;
    color: $text-primary;
    font-size: $font-size-sm;
    font-family: $font-family;
    resize: vertical;
    outline: none;

    &::placeholder { color: $text-muted; }
    &:focus { border-color: $accent-primary; }
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }

  &__btn {
    padding: 8px 20px;
    border-radius: $radius-full;
    font-size: $font-size-sm;
    cursor: pointer;
    border: none;

    &--cancel {
      background: $bg-glass;
      color: $text-secondary;
      &:hover { color: $text-primary; }
    }

    &--confirm {
      background: $accent-primary;
      color: #fff;
      &:hover:not(:disabled) { background: $accent-secondary; }
      &:disabled { opacity: 0.4; cursor: not-allowed; }
    }
  }
}
</style>
