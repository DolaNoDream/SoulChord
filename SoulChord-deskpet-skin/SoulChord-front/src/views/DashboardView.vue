<script setup lang="ts">
import { ref, watch, nextTick, inject, onMounted } from 'vue'
import type { Ref } from 'vue'
import { usePlayerStore } from '@/stores/player'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { useChat } from '@/composables/useChat'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAudio } from '@/composables/useAudio'
import ClockDisplay from '@/components/ClockDisplay.vue'
import DigitalOrb from '@/components/DigitalOrb.vue'
import MusicPlayer from '@/components/MusicPlayer.vue'
import ChatBubble from '@/components/ChatBubble.vue'
import PlaylistPanel from '@/components/PlaylistPanel.vue'
import QueuePanel from '@/components/QueuePanel.vue'
import UserProfilePanel from '@/components/UserProfilePanel.vue'

const playerStore = usePlayerStore()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()
const { isSending, sendMessage } = useChat()
const { connect, send } = useWebSocket()
useAudio()  // 创建音频元素，否则 playSong() 无 audioElement 可播

const messageListRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const activeTab = ref<'chat' | 'playlist' | 'queue' | 'profile'>('chat')

// 等待 App.vue init 完成后才建立 WS 连接
const initDone = inject<Ref<boolean>>('initDone', ref(false))
watch(initDone, (done) => { if (done && !import.meta.env.SSR) connect() }, { immediate: true })

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight
}
watch(() => chatStore.messages.length, () => scrollToBottom(), { immediate: true })
onMounted(() => scrollToBottom())

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
    <!-- 顶部区域：时钟 → AI 能量球 -->
    <ClockDisplay />
    <DigitalOrb />

    <!-- 播放器 -->
    <MusicPlayer />

    <!-- Tab 切换 -->
    <div class="dashboard__tabs">
      <button
        class="dashboard__tab"
        :class="{ 'dashboard__tab--active': activeTab === 'chat' }"
        @click="activeTab = 'chat'">💬 对话</button>
      <button
        class="dashboard__tab"
        :class="{ 'dashboard__tab--active': activeTab === 'playlist' }"
        @click="activeTab = 'playlist'"
      >📋 歌单</button>
      <button
        class="dashboard__tab"
        :class="{ 'dashboard__tab--active': activeTab === 'queue' }"
        @click="activeTab = 'queue'"
      >🎶 队列</button>
      <button
        class="dashboard__tab"
        :class="{ 'dashboard__tab--active': activeTab === 'profile' }"
        @click="activeTab = 'profile'"
      >🧬 画像</button>
    </div>

    <!-- Chat 面板（广播稿风格） -->
    <section v-if="activeTab === 'chat'" class="dashboard__chat">
      <div ref="messageListRef" class="dashboard__messages">
        <template v-if="chatStore.messages.length === 0">
          <div class="dashboard__empty-chat">
            <span class="dashboard__empty-chat-text">🎙️ 和 AI DJ 聊聊你的心情</span>
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
        <button class="dashboard__send-btn" :disabled="!chatStore.inputText.trim() || isSending" @click="handleSend">{{ isSending ? '···' : '发送' }}</button>
      </div>
    </section>

    <!-- 歌单管理面板 -->
    <section v-else-if="activeTab === 'playlist'" class="dashboard__panel">
      <PlaylistPanel />
    </section>

    <!-- 播放列表面板 -->
    <section v-else-if="activeTab === 'queue'" class="dashboard__panel">
      <QueuePanel />
    </section>

    <!-- 音乐画像面板 -->
    <section v-else-if="activeTab === 'profile'" class="dashboard__panel">
      <UserProfilePanel />
    </section>
  </div>
</template>

<style lang="scss">
.dashboard {
  display: flex; flex-direction: column; height: 100%; overflow: hidden;

  /* ── Tab ── */
  &__tabs { display: flex; gap: 0; flex-shrink: 0; border-bottom: 1px solid $border-subtle; margin-top: 4px; }
  &__tab { flex: 1; padding: 8px 12px; background: none; border: none; border-bottom: 2px solid transparent;
    color: $text-muted; font-size: $font-size-xs; font-family: $font-mono; cursor: pointer; transition: all 0.2s;
    letter-spacing: 0.5px;
    &:hover { color: $text-secondary; }
    &--active { color: $accent-primary; border-bottom-color: $accent-primary; }
  }

  /* ── 聊天区（透明，点阵透出）── */
  &__chat {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 160px;
    margin: 6px 12px 10px;
    border: 1px solid var(--border-subtle);
    border-radius: $radius-lg;
    box-shadow: 0 0 50px rgba(25, 230, 162, 0.25), inset 0 0 50px rgba(25, 230, 162, 0.1);
  }

  &__messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
  }

  &__empty-chat {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 20px;
    color: $text-muted;
    gap: 8px;
  }

  &__empty-chat-text {
    font-size: $font-size-sm;
    font-family: $font-ai;
    font-style: italic;
  }

  &__scenes {
    display: flex;
    gap: 6px;
    padding: 6px 14px;
    overflow-x: auto;
    flex-shrink: 0;
    border-top: 1px solid $border-subtle;

    &::-webkit-scrollbar { height: 0; }
  }

  &__scene-btn {
    padding: 4px 10px;
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: $radius-full;
    font-size: 10px;
    font-family: $font-mono;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s;

    &:hover:not(:disabled) {
      border-color: rgba($accent-primary, 0.3);
      color: $accent-primary;
    }

    &:disabled { opacity: 0.5; cursor: not-allowed; }
  }

  &__input-area {
    display: flex;
    gap: 8px;
    padding: 8px 14px;
    border-top: 1px solid $border-subtle;
    flex-shrink: 0;
  }

  &__input {
    flex: 1;
    padding: 8px 14px;
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: $radius-full;
    color: var(--text-primary);
    font-size: $font-size-sm;
    font-family: $font-family;
    outline: none;

    &::placeholder { color: $text-muted; }
    &:focus { border-color: rgba($accent-primary, 0.3); }
  }

  &__send-btn {
    padding: 8px 18px;
    background: transparent;
    border: 1px solid rgba($accent-primary, 0.3);
    border-radius: $radius-full;
    color: $accent-primary;
    font-size: $font-size-sm;
    font-family: $font-mono;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;

    &:hover:not(:disabled) {
      background: rgba($accent-primary, 0.1);
      box-shadow: 0 0 8px rgba($accent-primary, 0.2);
    }

    &:disabled { opacity: 0.3; cursor: not-allowed; }
  }

  /* ── 非聊天面板 ── */
  &__panel {
    flex: 1;
    overflow: hidden;
    min-height: 160px;
  }
}
</style>
