<script setup lang="ts">
import { ref, watch } from 'vue'
import { useUserStore } from '@/stores/user'
import { useSettingsStore } from '@/stores/settings'
import { getSettings, postNeteaseLogin } from '@/api/agent'
import { ElMessage } from 'element-plus'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const userStore = useUserStore()
const settingsStore = useSettingsStore()

// ===== 头像/昵称 =====
const avatarInputRef = ref<HTMLInputElement | null>(null)
const isEditingName = ref(false)
const editingName = ref('')
const nameInputRef = ref<HTMLInputElement | null>(null)

// ===== API Key 显示切换 =====
const showLlmKey = ref(false)
const showNeteaseKey = ref(false)

// ===== 网易云登录 =====
const loginDialogVisible = ref(false)
const loginType = ref<'qr' | 'sms'>('qr')
const loginToken = ref('')
const isLoggingIn = ref(false)

// 打开设置面板时从后端拉取最新设置
watch(() => props.visible, async (v) => {
  if (v) {
    try {
      const settings = await getSettings()
      if (settings) settingsStore.loadFromBackend(settings as Record<string, unknown>)
    } catch { /* 后端离线时用本地数据 */ }
  }
})

// ===== 头像 =====
function handleAvatarClick() { avatarInputRef.value?.click() }
function handleAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !file.type.startsWith('image/') || file.size > 5 * 1024 * 1024) return
  const reader = new FileReader()
  reader.onload = () => { userStore.updateAvatar(reader.result as string) }
  reader.readAsDataURL(file)
  input.value = ''
}

// ===== 昵称 =====
function startEditName() {
  editingName.value = userStore.nickname
  isEditingName.value = true
  setTimeout(() => nameInputRef.value?.focus(), 100)
}
function confirmEditName() {
  const n = editingName.value.trim()
  if (n) userStore.updateNickname(n)
  isEditingName.value = false
}
function handleNameKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') confirmEditName()
  else if (e.key === 'Escape') isEditingName.value = false
}

// ===== API Key 保存 =====
function handleLlmKeyBlur() {
  if (settingsStore.llmApiKey) settingsStore.syncToBackend()
}
function handleNeteaseKeyBlur() {
  if (settingsStore.neteaseApiKey) settingsStore.syncToBackend()
}

function openDeepSeekPage() {
  const url = 'https://platform.deepseek.com/api_keys'
  if (window.electronAPI?.openExternal) window.electronAPI.openExternal(url)
  else window.open(url, '_blank')
}

// ===== 网易云登录 =====
function openLoginDialog() {
  loginToken.value = ''
  loginType.value = 'qr'
  loginDialogVisible.value = true
}

async function handleLogin() {
  if (!loginToken.value.trim()) return
  isLoggingIn.value = true
  try {
    const result = await postNeteaseLogin({
      type: loginType.value,
      token: loginToken.value.trim(),
    })
    settingsStore.setNeteaseStatus(result.login_status, result.nickname)
    loginDialogVisible.value = false
    ElMessage.success(`已登录：${result.nickname}`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '登录失败')
  } finally {
    isLoggingIn.value = false
  }
}

</script>

<template>
  <Transition name="drawer-fade"><div v-if="visible" class="drawer-overlay" @click="emit('close')" /></Transition>
  <Transition name="drawer-slide">
    <div v-if="visible" class="settings-drawer">
      <div class="settings-drawer__header">
        <h3>个人设置</h3>
        <button class="settings-drawer__close" @click="emit('close')">✕</button>
      </div>

      <!-- 用户信息 -->
      <div class="settings-drawer__user">
        <div class="settings-drawer__avatar" @click="handleAvatarClick" title="点击更换头像">
          <img v-if="userStore.getLocalAvatar()" :src="userStore.getLocalAvatar()" class="settings-drawer__avatar-img" />
          <span v-else>👤</span>
          <div class="settings-drawer__avatar-overlay">📷</div>
        </div>
        <input ref="avatarInputRef" type="file" accept="image/*" class="settings-drawer__file-input" @change="handleAvatarChange" />
        <div class="settings-drawer__user-info">
          <div v-if="isEditingName" class="settings-drawer__name-edit">
            <input ref="nameInputRef" v-model="editingName" class="settings-drawer__name-input" maxlength="20" @keydown="handleNameKeydown" @blur="confirmEditName" />
          </div>
          <div v-else class="settings-drawer__name-display" @click="startEditName" title="点击修改昵称">
            <span class="settings-drawer__nickname">{{ userStore.nickname }}</span>
            <span class="settings-drawer__edit-icon">✎</span>
          </div>
        </div>
      </div>

      <!-- 窗口设置 -->
      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">⚙️ 基本设置</h4>
        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info"><span>🔝 窗口始终置顶</span></div>
          <el-switch v-model="settingsStore.alwaysOnTop" @change="settingsStore.syncAlwaysOnTop()" size="small" />
        </div>
      </div>

      <!-- LLM API Key -->
      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">🤖 LLM API Key</h4>
        <p class="settings-drawer__item-desc" style="margin-bottom: 8px;">
          配置大模型密钥以启用AI对话与歌单画像分析
          <a href="#" class="settings-drawer__apikey-link" @click.prevent="openDeepSeekPage">获取 Key →</a>
        </p>
        <div class="settings-drawer__apikey-row">
          <input
            :value="settingsStore.llmApiKey"
            :type="showLlmKey ? 'text' : 'password'"
            class="settings-drawer__apikey-input"
            placeholder="sk-xxxxxxxxxxxxxxxx"
            @input="settingsStore.llmApiKey = ($event.target as HTMLInputElement).value"
            @blur="handleLlmKeyBlur"
          />
          <button class="settings-drawer__apikey-toggle" @click="showLlmKey = !showLlmKey">{{ showLlmKey ? '🙈' : '👁' }}</button>
        </div>
        <p v-if="!settingsStore.hasLlmKey" class="settings-drawer__warn">⚠️ 未配置LLM APIKey，AI对话与歌单画像分析将不可用</p>
      </div>

      <!-- 网易云 API Key -->
      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">🎵 网易云 API Key</h4>
        <p class="settings-drawer__item-desc" style="margin-bottom: 8px;">
          配置网易云第三方服务密钥以启用歌单导入与音乐播放
        </p>
        <div class="settings-drawer__apikey-row">
          <input
            :value="settingsStore.neteaseApiKey"
            :type="showNeteaseKey ? 'text' : 'password'"
            class="settings-drawer__apikey-input"
            placeholder="输入网易云API密钥"
            @input="settingsStore.neteaseApiKey = ($event.target as HTMLInputElement).value"
            @blur="handleNeteaseKeyBlur"
          />
          <button class="settings-drawer__apikey-toggle" @click="showNeteaseKey = !showNeteaseKey">{{ showNeteaseKey ? '🙈' : '👁' }}</button>
        </div>
      </div>

      <!-- 网易云账号登录 -->
      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">🔗 网易云账号</h4>
        <div class="settings-drawer__netease-status">
          <span v-if="settingsStore.neteaseLoginStatus" class="settings-drawer__netease-loggedin">
            ✅ 已登录：{{ settingsStore.neteaseNickname || '网易云用户' }}
          </span>
          <span v-else class="settings-drawer__netease-notlogin">
            ⚠️ 未登录 — 歌单导入与音乐播放功能将不可用
          </span>
        </div>
        <button class="settings-drawer__login-btn" @click="openLoginDialog">
          {{ settingsStore.neteaseLoginStatus ? '切换账号' : '登录网易云账号' }}
        </button>
      </div>

      <!-- 网易云登录弹窗 -->
      <div v-if="loginDialogVisible" class="import-dialog-overlay" @click.self="loginDialogVisible = false">
        <div class="import-dialog">
          <h4>网易云账号登录</h4>
          <p class="import-dialog__hint">输入扫码获取的临时Token或验证码完成授权登录</p>
          <div class="settings-drawer__login-type">
            <label><input type="radio" v-model="loginType" value="qr" /> 扫码登录</label>
            <label><input type="radio" v-model="loginType" value="sms" /> 验证码登录</label>
          </div>
          <input v-model="loginToken" class="settings-drawer__apikey-input" :placeholder="loginType === 'qr' ? '请输入扫码Token' : '请输入手机验证码'" style="width: 100%; margin-top: 8px;" />
          <div class="import-dialog__actions">
            <button class="import-dialog__btn import-dialog__btn--cancel" @click="loginDialogVisible = false">取消</button>
            <button class="import-dialog__btn import-dialog__btn--confirm" :disabled="!loginToken.trim() || isLoggingIn" @click="handleLogin">{{ isLoggingIn ? '登录中...' : '登录' }}</button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style lang="scss">
.drawer-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 100; backdrop-filter: blur(2px); }
.settings-drawer {
  position: fixed; top: 0; right: 0; width: 320px; height: 100%; background: $bg-secondary;
  border-left: 1px solid $border-subtle; z-index: 101; overflow-y: auto; padding: 20px 18px;

  &__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    h3 { font-size: $font-size-lg; color: $text-primary; margin: 0; }
  }
  &__close { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
    background: none; border: 1px solid $border-subtle; border-radius: 50%; color: $text-secondary;
    cursor: pointer; font-size: 14px;
    &:hover { color: $text-primary; border-color: $border-default; }
  }
  &__user { display: flex; align-items: center; gap: 12px; padding-bottom: 20px;
    border-bottom: 1px solid $border-subtle; margin-bottom: 20px; }
  &__avatar { width: 52px; height: 52px; border-radius: 50%;
    background: linear-gradient(135deg, $accent-primary, $accent-secondary);
    display: flex; align-items: center; justify-content: center; font-size: 24px;
    cursor: pointer; position: relative; overflow: hidden; flex-shrink: 0;
    &:hover &-overlay { opacity: 1; }
    &-img { width: 100%; height: 100%; object-fit: cover; }
    &-overlay { position: absolute; inset: 0; border-radius: 50%; background: rgba(0,0,0,0.4);
      display: flex; align-items: center; justify-content: center; opacity: 0;
      transition: opacity 0.2s; font-size: 14px; }
  }
  &__file-input { display: none; }
  &__user-info { display: flex; flex-direction: column; gap: 2px; }
  &__nickname { font-size: $font-size-base; color: $text-primary; font-weight: 600; }
  &__name-display { display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 2px 4px;
    border-radius: 4px;
    &:hover { background: rgba($accent-primary, 0.1);
      .settings-drawer__edit-icon { opacity: 1; } }
  }
  &__edit-icon { font-size: 11px; color: $text-muted; opacity: 0; transition: opacity 0.15s; }
  &__name-edit { margin-bottom: 2px; }
  &__name-input { width: 100%; padding: 4px 8px; background: $bg-tertiary;
    border: 1px solid $accent-primary; border-radius: 4px; color: $text-primary;
    font-size: $font-size-base; font-weight: 600; outline: none; }

  &__section { padding-bottom: 20px; border-bottom: 1px solid $border-subtle; margin-bottom: 20px;
    &:last-child { border-bottom: none; margin-bottom: 0; } }
  &__section-title { font-size: $font-size-sm; color: $text-secondary; margin: 0 0 12px; font-weight: 600; }
  &__item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0;
    &-info { font-size: $font-size-sm; color: $text-primary; }
    &-desc { font-size: 11px; color: $text-muted; display: block; }
  }

  &__apikey-row { display: flex; gap: 6px; align-items: center; }
  &__apikey-input { flex: 1; padding: 7px 10px; background: $bg-tertiary;
    border: 1px solid $border-subtle; border-radius: $radius-sm; color: $text-primary;
    font-size: $font-size-xs; font-family: 'Consolas', monospace; outline: none;
    &::placeholder { color: $text-muted; }
    &:focus { border-color: $accent-primary; }
  }
  &__apikey-toggle { width: 32px; height: 32px; display: flex; align-items: center;
    justify-content: center; background: $bg-glass; border: 1px solid $border-subtle;
    border-radius: $radius-sm; cursor: pointer; font-size: 14px; flex-shrink: 0;
    &:hover { border-color: $border-default; }
  }
  &__apikey-link { color: $accent-primary; font-size: 11px; text-decoration: none;
    &:hover { text-decoration: underline; }
  }
  &__warn { font-size: 11px; color: $accent-warm; margin: 6px 0 0; }

  &__netease-status { padding: 8px 0; font-size: $font-size-sm; }
  &__netease-loggedin { color: $accent-success; }
  &__netease-notlogin { color: $accent-warm; }
  &__login-btn { width: 100%; padding: 10px; background: rgba($accent-primary, 0.1);
    border: 1px solid rgba($accent-primary, 0.3); border-radius: $radius-md;
    color: $accent-primary; font-size: $font-size-sm; cursor: pointer;
    &:hover { background: rgba($accent-primary, 0.2); }
  }
  &__login-type { display: flex; gap: 16px; margin: 8px 0; font-size: $font-size-sm; color: $text-secondary;
    label { cursor: pointer; display: flex; align-items: center; gap: 4px; }
  }
}

.drawer-fade-enter-active, .drawer-fade-leave-active { transition: opacity 0.25s ease; }
.drawer-fade-enter-from, .drawer-fade-leave-to { opacity: 0; }
.drawer-slide-enter-active, .drawer-slide-leave-active { transition: transform 0.25s ease; }
.drawer-slide-enter-from, .drawer-slide-leave-to { transform: translateX(100%); }

.import-dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 200; }
.import-dialog { background: $bg-secondary; border: 1px solid $border-subtle;
  border-radius: $radius-lg; padding: 24px; width: 360px; max-width: 90vw;
  h4 { margin: 0 0 8px; font-size: $font-size-base; color: $text-primary; }
  &__hint { font-size: $font-size-xs; color: $text-muted; margin: 0 0 12px; }
  &__textarea { width: 100%; padding: 10px 12px; background: $bg-tertiary;
    border: 1px solid $border-subtle; border-radius: $radius-sm; color: $text-primary;
    font-size: $font-size-sm; font-family: $font-family; resize: vertical; outline: none;
    &::placeholder { color: $text-muted; }
    &:focus { border-color: $accent-primary; }
  }
  &__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
  &__btn { padding: 8px 20px; border-radius: $radius-full; font-size: $font-size-sm; cursor: pointer; border: none;
    &--cancel { background: $bg-glass; color: $text-secondary;
      &:hover { color: $text-primary; } }
    &--confirm { background: $accent-primary; color: #fff;
      &:hover:not(:disabled) { background: $accent-secondary; }
      &:disabled { opacity: 0.4; cursor: not-allowed; }
    }
  }
}

</style>
