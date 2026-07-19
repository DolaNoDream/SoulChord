<script setup lang="ts">
import { ref, watch, nextTick, inject } from 'vue'
import type { Ref } from 'vue'
import { usePlayerStore } from '@/stores/player'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { useChat } from '@/composables/useChat'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAudio } from '@/composables/useAudio'
import MusicPlayer from '@/components/MusicPlayer.vue'
import ChatBubble from '@/components/ChatBubble.vue'
import PlaylistPanel from '@/components/PlaylistPanel.vue'
import UserProfilePanel from '@/components/UserProfilePanel.vue'

const playerStore = usePlayerStore()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()
const { isSending, sendMessage } = useChat()
const { connect, send } = useWebSocket()
useAudio()  // 创建音频元素，否则 playSong() 无 audioElement 可播

const messageListRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const activeTab = ref<'chat' | 'playlist' | 'profile'>('chat')

// 等待 App.vue init 完成后才建立 WS 连接（对齐文档：HTTP 初始化成功 → WS 连接）
const initDone = inject<Ref<boolean>>('initDone', ref(false))
watch(initDone, (done) => { if (done && !import.meta.env.SSR) connect() }, { immediate: true })

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight
}
watch(() => chatStore.messages.length, () => scrollToBottom())

function checkLlmKey(): boolean {
  if (!settingsStore.hasLlmKey) {
    chatStore.addMessage({
      id: crypto.randomUUID(),
      role: 'system',
      content: '⚠️ 请先在设置中配置 LLM API Key',
      timestamp: new Date().toISOString(),
    })
    return false
  }
  return true
}

function handleSend() {
  if (!checkLlmKey()) return
  const text = sendMessage()
  if (text) send('chat', 'user_text', { text })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
}

function handleScene(sceneId: string) {
  if (!checkLlmKey()) return
  const scene = chatStore.quickScenes.find(s => s.id === sceneId)
  if (!scene) return
  const text = sendMessage(scene.promptTemplate)
  if (text) send('chat', 'user_text', { text })
}
</script>

<template>
  <div class="dashboard">
    <!-- 播放器 -->
    <section class="dashboard__player"><MusicPlayer /></section>

    <!-- Tab 切换 -->
    <div class="dashboard__tabs">
      <button
        class="dashboard__tab"
        :class="{ 'dashboard__tab--active': activeTab === 'chat' }"
        @click="activeTab = 'chat'"
      >💬 AI 对话</button>
      <button
        class="dashboard__tab"
        :class="{ 'dashboard__tab--active': activeTab === 'playlist' }"
        @click="activeTab = 'playlist'"
      >📋 歌单管理</button>
      <button
        class="dashboard__tab"
        :class="{ 'dashboard__tab--active': activeTab === 'profile' }"
        @click="activeTab = 'profile'"
      >🧬 音乐画像</button>
    </div>

    <!-- Chat 面板 -->
    <section v-if="activeTab === 'chat'" class="dashboard__chat">
      <div ref="messageListRef" class="dashboard__messages">
        <template v-if="chatStore.messages.length === 0">
          <div class="dashboard__empty-chat">
            <span class="dashboard__empty-chat-icon">🎙️</span>
            <span>和 AI DJ 聊聊你的心情</span>
          </div>
        </template>
        <ChatBubble v-for="msg in chatStore.messages" :key="msg.id" :message="msg" />
      </div>

      <div class="dashboard__scenes">
        <button v-for="scene in chatStore.quickScenes" :key="scene.id" class="dashboard__scene-btn" :disabled="isSending" @click="handleScene(scene.id)">
          {{ scene.id === 'tired' ? '🌙' : scene.id === 'focus' ? '🎯' : scene.id === 'happy' ? '☀️' : scene.id === 'sleep' ? '💤' : scene.id === 'commute' ? '🚗' : scene.id === 'workout' ? '🏃' : '💬' }} {{ scene.label }}
        </button>
      </div>

      <div class="dashboard__input-area">
        <input ref="inputRef" v-model="chatStore.inputText" type="text" class="dashboard__input" placeholder="说说你的心情..." :disabled="isSending" @keydown="handleKeydown" />
        <button class="dashboard__send-btn" :disabled="!chatStore.inputText.trim() || isSending" @click="handleSend">{{ isSending ? '...' : '发送' }}</button>
      </div>
    </section>

    <!-- 歌单管理面板 -->
    <section v-else-if="activeTab === 'playlist'" class="dashboard__panel">
      <PlaylistPanel />
    </section>

    <!-- 音乐画像面板 -->
    <section v-else-if="activeTab === 'profile'" class="dashboard__panel">
      <UserProfilePanel />
    </section>
  </div>
</template>

<style lang="scss">
.dashboard { display: flex; flex-direction: column; height: 100%; overflow: hidden;
  &__player { flex-shrink: 0; border-bottom: 1px solid $border-subtle; }
  &__tabs { display: flex; gap: 0; flex-shrink: 0; border-bottom: 1px solid $border-subtle; }
  &__tab { flex: 1; padding: 8px 12px; background: none; border: none; border-bottom: 2px solid transparent;
    color: $text-secondary; font-size: $font-size-xs; cursor: pointer; transition: all 0.2s;
    &:hover { color: $text-primary; }
    &--active { color: $accent-primary; border-bottom-color: $accent-primary; font-weight: 600; }
  }
  &__chat { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  &__messages { flex: 1; overflow-y: auto; padding: 8px 16px; }
  &__empty-chat { display: flex; flex-direction: column; align-items: center; padding: 40px 20px;
    color: $text-muted; gap: 8px; &-icon { font-size: 32px; } }
  &__scenes { display: flex; gap: 6px; padding: 8px 16px; overflow-x: auto; flex-shrink: 0;
    &::-webkit-scrollbar { height: 0; } }
  &__scene-btn { padding: 5px 12px; background: $bg-glass; border: 1px solid $border-subtle;
    border-radius: $radius-full; font-size: 11px; color: $text-secondary; cursor: pointer;
    white-space: nowrap; &:hover:not(:disabled) { border-color: $accent-primary; color: $accent-primary; }
    &:disabled { opacity: 0.5; cursor: not-allowed; } }
  &__input-area { display: flex; gap: 8px; padding: 10px 16px; border-top: 1px solid $border-subtle; flex-shrink: 0; }
  &__input { flex: 1; padding: 8px 14px; background: $bg-glass; border: 1px solid $border-subtle;
    border-radius: $radius-full; color: $text-primary; font-size: $font-size-sm; outline: none;
    &::placeholder { color: $text-muted; } &:focus { border-color: $accent-primary; } }
  &__send-btn { padding: 8px 18px; background: $accent-primary; border: none; border-radius: $radius-full;
    color: #fff; font-size: $font-size-sm; font-weight: 600; cursor: pointer;
    &:hover:not(:disabled) { background: $accent-secondary; } &:disabled { opacity: 0.4; cursor: not-allowed; } }
  &__panel { flex: 1; overflow-y: auto; }
}
</style>
