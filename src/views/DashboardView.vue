<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { usePlayerStore } from '@/stores/player'
import { useChatStore } from '@/stores/chat'
import { useChat } from '@/composables/useChat'
import { useWebSocket } from '@/composables/useWebSocket'
import MusicPlayer from '@/components/MusicPlayer.vue'
import ChatBubble from '@/components/ChatBubble.vue'
import type { Song } from '@/types/music'

const playerStore = usePlayerStore()
const chatStore = useChatStore()
const { isSending, sendMessage } = useChat()
const { connect, send } = useWebSocket()

const messageListRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

connect()  // 建立 WS 连接

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight
}
watch(() => chatStore.messages.length, () => scrollToBottom())

function handleSend() {
  const text = sendMessage()
  if (text) send('chat', 'user_text', { text, source: 'chat' })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
}

function handleScene(sceneId: string) {
  const scene = chatStore.quickScenes.find(s => s.id === sceneId)
  if (!scene) return
  const text = sendMessage(scene.promptTemplate)
  if (text) send('chat', 'user_text', { text, source: 'chat' })
}

function handlePlaySong(song: Song) {
  playerStore.playSong(song, '')
}
</script>

<template>
  <div class="dashboard">
    <section class="dashboard__player"><MusicPlayer /></section>
    <div class="dashboard__divider"><div class="dashboard__divider-line"></div><span class="dashboard__divider-text">AI DJ</span><div class="dashboard__divider-line"></div></div>

    <section class="dashboard__chat">
      <div ref="messageListRef" class="dashboard__messages">
        <template v-if="chatStore.messages.length === 0">
          <div class="dashboard__empty-chat"><span class="dashboard__empty-chat-icon">🎙️</span><span>和 AI DJ 聊聊你的心情</span></div>
        </template>
        <ChatBubble v-for="msg in chatStore.messages" :key="msg.id" :message="msg" @play-song="handlePlaySong" />
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
  </div>
</template>

<style lang="scss">
.dashboard { display: flex; flex-direction: column; height: 100%; overflow: hidden;
  &__player { flex-shrink: 0; border-bottom: 1px solid $border-subtle; }
  &__divider { display: flex; align-items: center; gap: 10px; padding: 6px 20px; flex-shrink: 0; &-line { flex: 1; height: 1px; background: $border-subtle; } &-text { font-size: 11px; color: $text-muted; } }
  &__chat { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  &__messages { flex: 1; overflow-y: auto; padding: 8px 16px; }
  &__empty-chat { display: flex; flex-direction: column; align-items: center; padding: 40px 20px; color: $text-muted; gap: 8px; &-icon { font-size: 32px; } }
  &__scenes { display: flex; gap: 6px; padding: 8px 16px; overflow-x: auto; flex-shrink: 0; &::-webkit-scrollbar { height: 0; } }
  &__scene-btn { padding: 5px 12px; background: $bg-glass; border: 1px solid $border-subtle; border-radius: $radius-full; font-size: 11px; color: $text-secondary; cursor: pointer; white-space: nowrap; &:hover:not(:disabled) { border-color: $accent-primary; color: $accent-primary; } &:disabled { opacity: 0.5; cursor: not-allowed; } }
  &__input-area { display: flex; gap: 8px; padding: 10px 16px; border-top: 1px solid $border-subtle; flex-shrink: 0; }
  &__input { flex: 1; padding: 8px 14px; background: $bg-glass; border: 1px solid $border-subtle; border-radius: $radius-full; color: $text-primary; font-size: $font-size-sm; outline: none; &::placeholder { color: $text-muted; } &:focus { border-color: $accent-primary; } }
  &__send-btn { padding: 8px 18px; background: $accent-primary; border: none; border-radius: $radius-full; color: #fff; font-size: $font-size-sm; font-weight: 600; cursor: pointer; &:hover:not(:disabled) { background: $accent-secondary; } &:disabled { opacity: 0.4; cursor: not-allowed; } }
}
</style>
