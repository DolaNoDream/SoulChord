<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { useSettingsStore } from '@/stores/settings'
import { getSettings, postNeteasePhoneLogin, getNeteaseQrKey, getNeteaseQrCreate, postNeteaseQrCheck } from '@/api/agent'
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

// ===== 网易云登录 =====
const loginDialogVisible = ref(false)
const loginTab = ref<'phone' | 'qr'>('phone')

// Phone login
const loginPhone = ref('')
const loginPassword = ref('')
const showPassword = ref(false)

// QR login
const qrKey = ref('')
const qrImg = ref('')
const qrStatus = ref<'idle' | 'waiting' | 'scanning' | 'confirmed' | 'expired'>('idle')
const isGettingQr = ref(false)
let qrPollTimer: ReturnType<typeof setInterval> | null = null

const isLoggingIn = ref(false)

const qrStatusText: Record<string, string> = {
  idle: '点击获取二维码',
  waiting: '请使用网易云音乐扫码',
  scanning: '已扫码，请在手机上确认',
  confirmed: '登录成功！',
  expired: '二维码已过期，请重新获取',
}

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
function compressAvatar(file: File, maxW: number, quality: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        let w = img.width, h = img.height
        if (w > maxW) { h = h * maxW / w; w = maxW }
        if (h > maxW) { w = w * maxW / h; h = maxW }
        canvas.width = w; canvas.height = h
        const ctx = canvas.getContext('2d')!
        ctx.drawImage(img, 0, 0, w, h)
        resolve(canvas.toDataURL('image/jpeg', quality))
      }
      img.onerror = reject
      img.src = reader.result as string
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
function handleAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !file.type.startsWith('image/') || file.size > 5 * 1024 * 1024) return
  compressAvatar(file, 120, 0.7).then(dataUrl => {
    userStore.updateAvatar(dataUrl)
  }).catch(() => {})
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

// ===== DJ 头像/名字 =====
const djAvatarInputRef = ref<HTMLInputElement | null>(null)
const isEditingDjName = ref(false)
const editingDjName = ref('')
const djNameInputRef = ref<HTMLInputElement | null>(null)

function handleDjAvatarClick() { djAvatarInputRef.value?.click() }
function handleDjAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !file.type.startsWith('image/') || file.size > 5 * 1024 * 1024) return
  compressAvatar(file, 120, 0.7).then(dataUrl => {
    userStore.updateDjAvatar(dataUrl)
  }).catch(() => {})
  input.value = ''
}

function startEditDjName() {
  editingDjName.value = userStore.djName
  isEditingDjName.value = true
  setTimeout(() => djNameInputRef.value?.focus(), 100)
}
function confirmEditDjName() {
  const n = editingDjName.value.trim()
  if (n) userStore.updateDjName(n)
  isEditingDjName.value = false
}
function handleDjNameKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') confirmEditDjName()
  else if (e.key === 'Escape') isEditingDjName.value = false
}

// ===== API Key 保存 =====
function handleLlmKeyBlur() {
  if (settingsStore.llmApiKey) settingsStore.syncToBackend()
}
function openDeepSeekPage() {
  const url = 'https://platform.deepseek.com/api_keys'
  if (window.electronAPI?.openExternal) window.electronAPI.openExternal(url)
  else window.open(url, '_blank')
}

// ===== 网易云登录 =====
function openLoginDialog() {
  loginDialogVisible.value = true
  loginTab.value = 'phone'
  loginPhone.value = ''
  loginPassword.value = ''
  resetQrState()
}

function resetQrState() {
  qrKey.value = ''
  qrImg.value = ''
  qrStatus.value = 'idle'
  if (qrPollTimer) {
    clearInterval(qrPollTimer)
    qrPollTimer = null
  }
}

async function handlePhoneLogin() {
  if (!loginPhone.value.trim() || !loginPassword.value.trim()) return
  isLoggingIn.value = true
  try {
    const result = await postNeteasePhoneLogin({
      phone: loginPhone.value.trim(),
      password: loginPassword.value,
    })
    settingsStore.setNeteaseStatus(true, result.nickname)
    loginDialogVisible.value = false
    ElMessage.success(`已登录：${result.nickname}`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '登录失败')
  } finally {
    isLoggingIn.value = false
  }
}

async function handleGetQr() {
  if (isGettingQr.value) return
  isGettingQr.value = true
  try {
    const keyRes = await getNeteaseQrKey()
    qrKey.value = keyRes.key
    const imgRes = await getNeteaseQrCreate(qrKey.value)
    qrImg.value = imgRes.qr_img
    qrStatus.value = 'waiting'

    if (qrPollTimer) clearInterval(qrPollTimer)
    qrPollTimer = setInterval(async () => {
      try {
        const checkRes = await postNeteaseQrCheck(qrKey.value)
        qrStatus.value = checkRes.status as any
        if (checkRes.status === 'confirmed') {
          if (qrPollTimer) { clearInterval(qrPollTimer); qrPollTimer = null }
          settingsStore.setNeteaseStatus(true, checkRes.nickname || '网易云用户')
          loginDialogVisible.value = false
          ElMessage.success('扫码登录成功')
        } else if (checkRes.status === 'expired') {
          if (qrPollTimer) { clearInterval(qrPollTimer); qrPollTimer = null }
        }
      } catch { /* continue polling */ }
    }, 2000)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '获取二维码失败')
  } finally {
    isGettingQr.value = false
  }
}

onUnmounted(() => {
  if (qrPollTimer) clearInterval(qrPollTimer)
})

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
          <img v-if="userStore.localAvatar" :src="userStore.localAvatar" class="settings-drawer__avatar-img" />
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

      <!-- DJ 信息 -->
      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">🎙️ AI DJ 形象</h4>
        <div class="settings-drawer__dj-row">
          <div class="settings-drawer__avatar" @click="handleDjAvatarClick" title="点击更换 DJ 头像">
            <img v-if="userStore.djAvatar" :src="userStore.djAvatar" class="settings-drawer__avatar-img" />
            <span v-else>🎧</span>
            <div class="settings-drawer__avatar-overlay">📷</div>
          </div>
          <input ref="djAvatarInputRef" type="file" accept="image/*" class="settings-drawer__file-input" @change="handleDjAvatarChange" />
          <div class="settings-drawer__user-info">
            <div v-if="isEditingDjName" class="settings-drawer__name-edit">
              <input ref="djNameInputRef" v-model="editingDjName" class="settings-drawer__name-input" maxlength="20" @keydown="handleDjNameKeydown" @blur="confirmEditDjName" />
            </div>
            <div v-else class="settings-drawer__name-display" @click="startEditDjName" title="点击修改 DJ 名字">
              <span class="settings-drawer__nickname">{{ userStore.djName }}</span>
              <span class="settings-drawer__edit-icon">✎</span>
            </div>
          </div>
        </div>
        <p class="settings-drawer__item-desc" style="margin-top: 8px;">DJ 头像和名字会显示在对话气泡中</p>
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
          <p class="import-dialog__hint">登录后即可播放完整歌曲（不再 20 秒试听）</p>
          <!-- 切换标签 -->
          <div class="settings-drawer__login-tabs">
            <button :class="['settings-drawer__login-tab', { active: loginTab === 'phone' }]" @click="loginTab = 'phone'">手机号登录</button>
            <button :class="['settings-drawer__login-tab', { active: loginTab === 'qr' }]" @click="loginTab = 'qr'">扫码登录</button>
          </div>

          <!-- 手机号登录 -->
          <div v-if="loginTab === 'phone'" class="settings-drawer__login-form">
            <input v-model="loginPhone" class="settings-drawer__apikey-input" placeholder="手机号" type="tel" style="width: 100%; margin-bottom: 8px;" />
            <div class="settings-drawer__apikey-row">
              <input v-model="loginPassword" :type="showPassword ? 'text' : 'password'" class="settings-drawer__apikey-input" placeholder="密码" style="flex: 1;" @keydown.enter="handlePhoneLogin" />
              <button class="settings-drawer__apikey-toggle" @click="showPassword = !showPassword">{{ showPassword ? '🙈' : '👁' }}</button>
            </div>
            <div class="import-dialog__actions">
              <button class="import-dialog__btn import-dialog__btn--cancel" @click="loginDialogVisible = false">取消</button>
              <button class="import-dialog__btn import-dialog__btn--confirm" :disabled="!loginPhone.trim() || !loginPassword.trim() || isLoggingIn" @click="handlePhoneLogin">{{ isLoggingIn ? '登录中...' : '登录' }}</button>
            </div>
          </div>

          <!-- 扫码登录 -->
          <div v-else class="settings-drawer__login-form">
            <div v-if="qrStatus === 'idle' || qrStatus === 'expired'" class="settings-drawer__qr-placeholder">
              <button class="settings-drawer__qr-btn" :disabled="isGettingQr" @click="handleGetQr">{{ isGettingQr ? '获取中...' : '获取二维码' }}</button>
            </div>
            <div v-else class="settings-drawer__qr-display">
              <img :src="'data:image/png;base64,' + qrImg" class="settings-drawer__qr-img" alt="QR code" />
              <p class="settings-drawer__qr-status">{{ qrStatusText[qrStatus] }}</p>
              <button v-if="qrStatus === 'expired'" class="settings-drawer__qr-btn" @click="handleGetQr">重新获取</button>
            </div>
            <div class="import-dialog__actions">
              <button class="import-dialog__btn import-dialog__btn--cancel" @click="loginDialogVisible = false">取消</button>
            </div>
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
  &__dj-row { display: flex; align-items: center; gap: 12px; }
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

  // ── 登录弹窗 tabs ──
  &__login-tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid $border-subtle; }
  &__login-tab { flex: 1; padding: 8px 0; background: none; border: none; border-bottom: 2px solid transparent;
    color: $text-muted; font-size: $font-size-sm; cursor: pointer; transition: all 0.2s;
    &.active { color: $accent-primary; border-bottom-color: $accent-primary; }
    &:hover:not(.active) { color: $text-secondary; }
  }
  &__login-form { min-height: 140px; }

  // ── QR 扫码 ──
  &__qr-placeholder { display: flex; align-items: center; justify-content: center; min-height: 140px; }
  &__qr-btn { padding: 8px 24px; background: $accent-primary; color: #fff; border: none;
    border-radius: $radius-md; font-size: $font-size-sm; cursor: pointer;
    &:hover:not(:disabled) { background: $accent-secondary; }
    &:disabled { opacity: 0.5; cursor: not-allowed; }
  }
  &__qr-display { text-align: center; padding: 8px 0; }
  &__qr-img { width: 160px; height: 160px; border-radius: $radius-sm; background: #fff; padding: 8px; }
  &__qr-status { font-size: $font-size-sm; color: $text-secondary; margin: 8px 0; }
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
