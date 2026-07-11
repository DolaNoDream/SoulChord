<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { useSettingsStore } from '@/stores/settings'
import { updateMemory, deleteMemory, getSettings } from '@/api/agent'
import type { Memory } from '@/types/user'
const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const userStore = useUserStore()
const settingsStore = useSettingsStore()
const avatarInputRef = ref<HTMLInputElement | null>(null)
const isEditingName = ref(false)
const editingName = ref('')
const nameInputRef = ref<HTMLInputElement | null>(null)
const showApiKey = ref(false)
const showImportDialog = ref(false)
const importText = ref('')
const isImporting = ref(false)

function openImportDialog() { importText.value = ''; showImportDialog.value = true }

// ===== Memory 编辑 =====
const editingMemKey = ref<string | null>(null)
const editingMemValue = ref('')
const editingMemValueRef = ref<HTMLInputElement | null>(null)

/** 四个 category 的中文标签 */
const categoryLabels: Record<string, string> = {
  profile: '📋 个人档案',
  preference: '🎵 音乐偏好',
  context: '📍 当前状态',
  feedback: '💬 反馈记录',
}

/** 按 category 分组的 memories */
const groupedMemories = computed(() => {
  const groups: Record<string, Memory[]> = { profile: [], preference: [], context: [], feedback: [] }
  for (const m of userStore.memories) {
    if (groups[m.category]) groups[m.category].push(m)
  }
  return groups
})

/** 开始编辑一条 Memory */
function startEditMem(key: string, value: unknown) {
  editingMemKey.value = key
  editingMemValue.value = typeof value === 'string' ? value : JSON.stringify(value)
  setTimeout(() => editingMemValueRef.value?.focus(), 100)
}

/** 确认编辑 → POST /memory/update */
async function confirmEditMem() {
  const key = editingMemKey.value
  if (!key) return
  let value: unknown = editingMemValue.value.trim()
  // 尝试解析为 JSON（数组/对象），失败则存字符串
  try { value = JSON.parse(value as string) } catch { /* keep as string */ }
  try { await updateMemory({ key, category: 'preference', value }) }
  catch { /* offline */ }
  // 更新本地
  const mem = userStore.memories.find(m => m.key === key)
  if (mem) { mem.value = value; mem.updated_at = Date.now() }
  userStore.loadMemories() // 从后端刷新
  editingMemKey.value = null
}

/** 删除 Memory → DELETE /memory/:key */
async function handleDeleteMem(key: string) {
  try { await deleteMemory(key) }
  catch { /* offline */ }
  userStore.memories = userStore.memories.filter(m => m.key !== key)
}

function handleMemKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') confirmEditMem()
  else if (e.key === 'Escape') editingMemKey.value = null
}

/** 新增一条 Memory → POST /memory/update */
const newMemCategory = ref<Memory['category']>('preference')
const newMemKey = ref('')
const newMemValue = ref('')
const showAddMem = ref(false)

async function handleAddMem() {
  const key = newMemKey.value.trim()
  const val = newMemValue.value.trim()
  if (!key || !val) return
  let value: unknown = val
  try { value = JSON.parse(val) } catch { /* string */ }
  try { await updateMemory({ key, category: newMemCategory.value, value, source: 'user_input' }) }
  catch { /* offline */ }
  await userStore.loadMemories()
  newMemKey.value = ''; newMemValue.value = ''; showAddMem.value = false
}

/** 置信度指示点 */
function confidenceDot(confidence: number): string {
  if (confidence >= 0.8) return '🟢'
  if (confidence >= 0.5) return '🟡'
  return '🔴'
}

watch(() => props.visible, async (v) => {
  if (v) {
    userStore.loadMemories()
    // 每次打开设置面板时从后端拉取最新设置
    try {
      const settings = await getSettings()
      if (settings) settingsStore.loadFromBackend(settings as Record<string, unknown>)
    } catch { /* 后端离线时用本地数据 */ }
  }
})

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

function startEditName() { editingName.value = userStore.nickname; isEditingName.value = true; setTimeout(() => nameInputRef.value?.focus(), 100) }
function confirmEditName() { const n = editingName.value.trim(); if (n) userStore.updateNickname(n); isEditingName.value = false }
function handleNameKeydown(e: KeyboardEvent) { if (e.key === 'Enter') confirmEditName(); else if (e.key === 'Escape') isEditingName.value = false }

function handleApiKeyBlur() {
  if (settingsStore.deepseekApiKey) settingsStore.syncToBackend()
}

function openDeepSeekPage() {
  const url = 'https://platform.deepseek.com/api_keys'
  if (window.electronAPI?.openExternal) window.electronAPI.openExternal(url)
  else window.open(url, '_blank')
}

async function handleImport() {
  const text = importText.value.trim()
  if (!text) return
  isImporting.value = true
  const lines = text.split('\n').filter(l => l.trim())
  const genres = [...new Set(lines.map(l => l.split('-')[0]?.trim()).filter(Boolean))]
  const artists = [...new Set(lines.map(l => l.split('-')[1]?.trim()).filter(Boolean))]
  try { await userStore.updatePreferences({ favorite_genres: genres, favorite_artists: artists }) }
  finally { isImporting.value = false; showImportDialog.value = false }
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

      <button class="settings-drawer__import-btn" @click="openImportDialog">📥 导入歌单（设置偏好）</button>
      <p class="settings-drawer__import-hint">支持网易云、QQ音乐，让 AI 了解你的品味</p>

      <div v-if="showImportDialog" class="import-dialog-overlay" @click.self="showImportDialog = false">
        <div class="import-dialog">
          <h4>导入喜欢的歌曲</h4>
          <p class="import-dialog__hint">每行一首，格式：曲风 - 艺人</p>
          <textarea v-model="importText" class="import-dialog__textarea" rows="8" placeholder="pop - 周杰伦&#10;piano - Yiruma&#10;hip-hop - Eminem"></textarea>
          <div class="import-dialog__actions">
            <button class="import-dialog__btn import-dialog__btn--cancel" @click="showImportDialog = false">取消</button>
            <button class="import-dialog__btn import-dialog__btn--confirm" :disabled="!importText.trim() || isImporting" @click="handleImport">{{ isImporting ? '提交中...' : '提交' }}</button>
          </div>
        </div>
      </div>

      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">⚙️ 设置</h4>
        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info"><span>🔝 窗口始终置顶</span></div>
          <el-switch v-model="settingsStore.alwaysOnTop" @change="settingsStore.syncAlwaysOnTop()" size="small" />
        </div>
        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info">
            <span>🎙️ DJ 音色</span>
            <span class="settings-drawer__item-desc">选择 AI DJ 的语音风格</span>
          </div>
          <select v-model="settingsStore.djVoice" @change="settingsStore.syncToBackend()" class="settings-drawer__select">
            <option value="male_gentle">温柔男声</option>
            <option value="female_warm">温暖女声</option>
            <option value="male_lively">活泼男声</option>
          </select>
        </div>
        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info"><span>👋 主动问候</span><span class="settings-drawer__item-desc">长时间静默后 AI DJ 主动打招呼</span></div>
          <el-switch v-model="settingsStore.autoGreet" @change="settingsStore.syncToBackend()" size="small" />
        </div>
        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info">
            <span>🎭 DJ 人格</span>
            <span class="settings-drawer__item-desc">切换 AI DJ 的对话风格</span>
          </div>
          <select v-model="settingsStore.persona" @change="settingsStore.syncToBackend()" class="settings-drawer__select">
            <option value="night_dj">深夜主播（温柔不打扰）</option>
            <option value="warm_companion">温暖陪伴（关怀型）</option>
            <option value="energetic_jockey">动感节奏（鼓励型）</option>
          </select>
        </div>
        <div class="settings-drawer__item">
          <div class="settings-drawer__item-info">
            <span>🌐 语言</span>
            <span class="settings-drawer__item-desc">切换界面显示语言</span>
          </div>
          <select v-model="settingsStore.language" @change="settingsStore.syncToBackend()" class="settings-drawer__select">
            <option value="zh-CN">中文</option>
            <option value="en-US">English</option>
          </select>
        </div>
      </div>

      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">🔑 DeepSeek API Key</h4>
        <p class="settings-drawer__item-desc" style="margin-bottom: 8px;">
          输入你的 DeepSeek API Key <a href="#" class="settings-drawer__apikey-link" @click.prevent="openDeepSeekPage">获取 Key →</a>
        </p>
        <div class="settings-drawer__apikey-row">
          <input :value="settingsStore.deepseekApiKey" :type="showApiKey ? 'text' : 'password'" class="settings-drawer__apikey-input" placeholder="sk-xxxxxxxxxxxxxxxx" @input="settingsStore.deepseekApiKey = ($event.target as HTMLInputElement).value" @blur="handleApiKeyBlur" />
          <button class="settings-drawer__apikey-toggle" @click="showApiKey = !showApiKey">{{ showApiKey ? '🙈' : '👁' }}</button>
        </div>
      </div>

      <!-- Memory / AI 记忆 -->
      <div class="settings-drawer__section">
        <h4 class="settings-drawer__section-title">🧠 AI 的记忆</h4>
        <p v-if="!userStore.memories.length" class="settings-drawer__item-desc">AI 还没有记住什么，多和 AI DJ 聊天吧</p>

        <div v-for="(memories, cat) in groupedMemories" :key="cat" class="settings-drawer__mem-group">
          <h5 class="settings-drawer__mem-cat">{{ categoryLabels[cat as string] || cat }}</h5>
          <div v-if="!memories.length" class="settings-drawer__mem-empty">暂无</div>
          <div v-for="mem in memories" :key="mem.key" class="settings-drawer__mem-item">
            <!-- 编辑模式 -->
            <template v-if="editingMemKey === mem.key">
              <div class="settings-drawer__mem-edit-row">
                <span class="settings-drawer__mem-key">{{ mem.key }}</span>
                <input
                  ref="editingMemValueRef"
                  v-model="editingMemValue"
                  class="settings-drawer__mem-input"
                  @keydown="handleMemKeydown"
                  @blur="confirmEditMem"
                />
              </div>
            </template>
            <!-- 显示模式 -->
            <template v-else>
              <div class="settings-drawer__mem-row">
                <span class="settings-drawer__mem-key">{{ mem.key }}</span>
                <span class="settings-drawer__mem-val" @click="startEditMem(mem.key, mem.value)" title="点击编辑">
                  {{ typeof mem.value === 'string' ? mem.value : JSON.stringify(mem.value) }}
                </span>
                <span class="settings-drawer__mem-confidence" :title="'置信度: ' + Math.round(mem.confidence * 100) + '%'">
                  {{ confidenceDot(mem.confidence) }}
                </span>
                <button class="settings-drawer__mem-del" @click="handleDeleteMem(mem.key)" title="删除">×</button>
              </div>
            </template>
          </div>
        </div>

        <!-- 新增 Memory -->
        <div v-if="showAddMem" class="settings-drawer__mem-add-form">
          <select v-model="newMemCategory" class="settings-drawer__mem-select">
            <option value="profile">📋 个人档案</option>
            <option value="preference">🎵 音乐偏好</option>
            <option value="context">📍 当前状态</option>
            <option value="feedback">💬 反馈记录</option>
          </select>
          <input v-model="newMemKey" class="settings-drawer__mem-input" placeholder="key（如 favorite_genres）" />
          <input v-model="newMemValue" class="settings-drawer__mem-input" placeholder="value（如 [&quot;pop&quot;,&quot;lo-fi&quot;]）" />
          <div class="settings-drawer__mem-add-actions">
            <button class="settings-drawer__mem-btn settings-drawer__mem-btn--cancel" @click="showAddMem = false">取消</button>
            <button class="settings-drawer__mem-btn settings-drawer__mem-btn--confirm" @click="handleAddMem">保存</button>
          </div>
        </div>
        <button v-else class="settings-drawer__mem-add-btn" @click="showAddMem = true">+ 添加记忆</button>
      </div>
    </div>
  </Transition>
</template>

<style lang="scss">
.drawer-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 100; backdrop-filter: blur(2px); }
.settings-drawer { position: fixed; top: 0; right: 0; width: 300px; height: 100%; background: $bg-secondary; border-left: 1px solid $border-subtle; z-index: 101; overflow-y: auto; padding: 20px 16px;
  &__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; h3 { font-size: $font-size-lg; color: $text-primary; margin: 0; } }
  &__close { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: none; border: 1px solid $border-subtle; border-radius: 50%; color: $text-secondary; cursor: pointer; font-size: 14px; &:hover { color: $text-primary; border-color: $border-default; } }
  &__user { display: flex; align-items: center; gap: 12px; padding-bottom: 20px; border-bottom: 1px solid $border-subtle; margin-bottom: 20px; }
  &__avatar { width: 52px; height: 52px; border-radius: 50%; background: linear-gradient(135deg, $accent-primary, $accent-secondary); display: flex; align-items: center; justify-content: center; font-size: 24px; cursor: pointer; position: relative; overflow: hidden; flex-shrink: 0;
    &:hover &-overlay { opacity: 1; }
    &-img { width: 100%; height: 100%; object-fit: cover; }
    &-overlay { position: absolute; inset: 0; border-radius: 50%; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.2s; font-size: 14px; }
  }
  &__file-input { display: none; }
  &__user-info { display: flex; flex-direction: column; gap: 2px; }
  &__nickname { font-size: $font-size-base; color: $text-primary; font-weight: 600; }
  &__name-display { display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 2px 4px; border-radius: 4px; &:hover { background: rgba($accent-primary, 0.1); .settings-drawer__edit-icon { opacity: 1; } } }
  &__edit-icon { font-size: 11px; color: $text-muted; opacity: 0; transition: opacity 0.15s; }
  &__name-edit { margin-bottom: 2px; }
  &__name-input { width: 100%; padding: 4px 8px; background: $bg-tertiary; border: 1px solid $accent-primary; border-radius: 4px; color: $text-primary; font-size: $font-size-base; font-weight: 600; outline: none; }
  &__import-btn { width: 100%; padding: 10px; margin-top: 12px; background: rgba($accent-primary, 0.1); border: 1px dashed rgba($accent-primary, 0.3); border-radius: $radius-md; color: $accent-primary; font-size: $font-size-sm; cursor: pointer; &:hover { background: rgba($accent-primary, 0.2); } }
  &__import-hint { font-size: 11px; color: $text-muted; margin: 6px 0 0; }
  &__section { padding-bottom: 20px; border-bottom: 1px solid $border-subtle; margin-bottom: 20px; &:last-child { border-bottom: none; margin-bottom: 0; } }
  &__section-title { font-size: $font-size-sm; color: $text-secondary; margin: 0 0 12px; font-weight: 600; }
  &__item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; &-info { font-size: $font-size-sm; color: $text-primary; } &-desc { font-size: 11px; color: $text-muted; } }
  &__tags { display: flex; flex-wrap: wrap; gap: 6px; }
  &__tag { padding: 3px 10px; background: $bg-glass; border: 1px solid $border-subtle; border-radius: $radius-full; font-size: 11px; color: $text-secondary; &--artist { background: rgba($accent-primary, 0.1); border-color: rgba($accent-primary, 0.2); } }
  &__apikey-row { display: flex; gap: 6px; align-items: center; }
  &__apikey-input { flex: 1; padding: 7px 10px; background: $bg-tertiary; border: 1px solid $border-subtle; border-radius: $radius-sm; color: $text-primary; font-size: $font-size-xs; font-family: 'Consolas', monospace; outline: none; &::placeholder { color: $text-muted; } &:focus { border-color: $accent-primary; } }
  &__apikey-toggle { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; background: $bg-glass; border: 1px solid $border-subtle; border-radius: $radius-sm; cursor: pointer; font-size: 14px; flex-shrink: 0; &:hover { border-color: $border-default; } }
  &__apikey-link { color: var(--accent-primary); font-size: 11px; text-decoration: none; &:hover { text-decoration: underline; } }
  &__select { padding: 4px 8px; background: $bg-tertiary; border: 1px solid $border-subtle; border-radius: 4px; color: $text-primary; font-size: 11px; outline: none; cursor: pointer; &:focus { border-color: $accent-primary; } }
}
.drawer-fade-enter-active, .drawer-fade-leave-active { transition: opacity 0.25s ease; }
.drawer-fade-enter-from, .drawer-fade-leave-to { opacity: 0; }
.drawer-slide-enter-active, .drawer-slide-leave-active { transition: transform 0.25s ease; }
.drawer-slide-enter-from, .drawer-slide-leave-to { transform: translateX(100%); }
// Memory 样式
.settings-drawer {
  &__mem-group { margin-bottom: 12px; }
  &__mem-cat { font-size: 11px; color: $text-muted; margin: 0 0 4px; font-weight: 600; }
  &__mem-empty { font-size: 11px; color: $text-muted; font-style: italic; padding: 4px 0; }
  &__mem-item { margin-bottom: 4px; }
  &__mem-row { display: flex; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 4px; &:hover { background: $bg-glass; } }
  &__mem-key { font-size: 11px; color: $accent-primary; font-weight: 600; flex-shrink: 0; min-width: 60px; }
  &__mem-val { font-size: 11px; color: $text-secondary; flex: 1; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; &:hover { color: $text-primary; } }
  &__mem-confidence { flex-shrink: 0; font-size: 10px; }
  &__mem-del { width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; background: none; border: 1px solid transparent; border-radius: 50%; color: $text-muted; cursor: pointer; font-size: 14px; flex-shrink: 0; &:hover { color: #ef4444; border-color: rgba(#ef4444, 0.3); } }
  &__mem-edit-row { display: flex; align-items: center; gap: 8px; padding: 2px 6px; }
  &__mem-input { flex: 1; padding: 3px 8px; background: $bg-tertiary; border: 1px solid $accent-primary; border-radius: 4px; color: $text-primary; font-size: 11px; outline: none; }
  &__mem-add-btn { width: 100%; padding: 6px; margin-top: 8px; background: none; border: 1px dashed $border-subtle; border-radius: $radius-sm; color: $text-muted; font-size: 11px; cursor: pointer; &:hover { border-color: $accent-primary; color: $accent-primary; } }
  &__mem-add-form { display: flex; flex-direction: column; gap: 6px; padding: 8px; background: $bg-glass; border-radius: $radius-sm; margin-top: 8px; }
  &__mem-select { padding: 4px 8px; background: $bg-tertiary; border: 1px solid $border-subtle; border-radius: 4px; color: $text-primary; font-size: 11px; outline: none; }
  &__mem-add-actions { display: flex; gap: 6px; justify-content: flex-end; }
  &__mem-btn { padding: 4px 14px; border-radius: $radius-full; font-size: 11px; cursor: pointer; border: none;
    &--confirm { background: $accent-primary; color: #fff; }
    &--cancel { background: $bg-glass; color: $text-secondary; }
  }
}

.import-dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 200; }
.import-dialog { background: $bg-secondary; border: 1px solid $border-subtle; border-radius: $radius-lg; padding: 24px; width: 320px; max-width: 90vw;
  h4 { margin: 0 0 8px; font-size: $font-size-base; color: $text-primary; }
  &__hint { font-size: $font-size-xs; color: $text-muted; margin: 0 0 12px; }
  &__textarea { width: 100%; padding: 10px 12px; background: $bg-tertiary; border: 1px solid $border-subtle; border-radius: $radius-sm; color: $text-primary; font-size: $font-size-sm; font-family: $font-family; resize: vertical; outline: none; &::placeholder { color: $text-muted; } &:focus { border-color: $accent-primary; } }
  &__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
  &__btn { padding: 8px 20px; border-radius: $radius-full; font-size: $font-size-sm; cursor: pointer; border: none;
    &--cancel { background: $bg-glass; color: $text-secondary; &:hover { color: $text-primary; } }
    &--confirm { background: $accent-primary; color: #fff; &:hover:not(:disabled) { background: $accent-secondary; } &:disabled { opacity: 0.4; cursor: not-allowed; } }
  }
}
</style>
