<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { usePlayerStore } from '@/stores/player'
import { useChat } from '@/composables/useChat'
import ChatBubble from '@/components/ChatBubble.vue'
import type { Song } from '@/types/music'

const chatStore = useChatStore()
const playerStore = usePlayerStore()
const { isSending, error, sendMessage, sendScene } = useChat()

const messageListRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

/** 自动滚动到底部 */
async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

// 监听消息变化，自动滚动
watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

watch(() => chatStore.currentStreamingMessage, () => {
  scrollToBottom()
})

/** 发送消息 */
function handleSend() {
  sendMessage()
}

/** 键盘事件 */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

/** 快捷场景 */
function handleScene(sceneId: string) {
  sendScene(sceneId)
}

/** 播放歌曲 */
function handlePlaySong(song: Song) {
  playerStore.playSong(song)
}

onMounted(() => {
  inputRef.value?.focus()
})
</script>

<template>
  <div class="chat-view">
    <!-- 头部 -->
    <header class="chat-view__header">
      <div class="chat-view__dj-avatar">🎧</div>
      <div>
        <h2 class="chat-view__dj-name">AI DJ</h2>
        <p class="chat-view__dj-status">在线 · 随时陪你聊天</p>
      </div>
    </header>

    <!-- 消息列表 -->
    <div ref="messageListRef" class="chat-view__messages">
      <template v-if="chatStore.messages.length === 0 && !chatStore.isStreaming">
        <div class="chat-view__empty">
          <div class="chat-view__empty-icon">🎙️</div>
          <h3 class="chat-view__empty-title">和你的专属 AI DJ 聊聊天吧</h3>
          <p class="chat-view__empty-hint">
            告诉我你的心情，我会为你推荐最适合的音乐
          </p>
        </div>
      </template>

      <ChatBubble
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
        @play-song="handlePlaySong"
      />

      <!-- 流式消息 -->
      <div v-if="chatStore.isStreaming" class="chat-view__streaming">
        <ChatBubble
          :message="{
            id: 'streaming',
            role: 'assistant',
            content: chatStore.currentStreamingMessage || '...',
            timestamp: new Date().toISOString(),
            isStreaming: true,
          }"
        />
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="chat-view__error">
      ⚠️ {{ error }}
    </div>

    <!-- 快捷场景 -->
    <div class="chat-view__scenes">
      <button
        v-for="scene in chatStore.quickScenes"
        :key="scene.id"
        class="chat-view__scene-btn"
        :disabled="isSending"
        @click="handleScene(scene.id)"
      >
        <span class="chat-view__scene-icon">{{ scene.icon === 'Moon' ? '🌙' : scene.icon === 'Aim' ? '🎯' : scene.icon === 'Sunny' ? '☀️' : scene.icon === 'MoonNight' ? '💤' : scene.icon === 'Van' ? '🚗' : scene.icon === 'Bicycle' ? '🏃' : '💬' }}</span>
        {{ scene.label }}
      </button>
    </div>

    <!-- 输入区域 -->
    <div class="chat-view__input-area">
      <input
        ref="inputRef"
        v-model="chatStore.inputText"
        type="text"
        class="chat-view__input"
        placeholder="说说你的心情..."
        :disabled="isSending"
        @keydown="handleKeydown"
      />
      <button
        class="chat-view__send-btn"
        :disabled="!chatStore.inputText.trim() || isSending"
        @click="handleSend"
      >
        {{ isSending ? '...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<style lang="scss">
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;

  &__header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    border-bottom: 1px solid $border-subtle;
    flex-shrink: 0;
  }

  &__dj-avatar {
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: linear-gradient(135deg, $accent-warm, #ef4444);
    font-size: 22px;
  }

  &__dj-name {
    font-size: $font-size-base;
    font-weight: 700;
    color: $text-primary;
    margin: 0;
  }

  &__dj-status {
    font-size: $font-size-xs;
    color: #4ade80;
    margin: 2px 0 0;
  }

  &__messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;

    &-icon {
      font-size: 48px;
      margin-bottom: 16px;
    }

    &-title {
      font-size: $font-size-lg;
      color: $text-primary;
      margin: 0 0 8px;
    }

    &-hint {
      font-size: $font-size-sm;
      color: $text-muted;
      margin: 0;
      line-height: 1.6;
    }
  }

  &__error {
    background: rgba(#ef4444, 0.1);
    border: 1px solid rgba(#ef4444, 0.3);
    color: #ef4444;
    padding: 8px 16px;
    margin: 0 16px;
    border-radius: $radius-sm;
    font-size: $font-size-xs;
    flex-shrink: 0;
  }

  &__scenes {
    display: flex;
    gap: 8px;
    padding: 10px 16px;
    overflow-x: auto;
    flex-shrink: 0;
    border-top: 1px solid $border-subtle;

    &::-webkit-scrollbar {
      height: 0;
    }
  }

  &__scene-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 14px;
    background: $bg-glass;
    border: 1px solid $border-subtle;
    border-radius: $radius-full;
    font-size: $font-size-xs;
    color: $text-secondary;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
    flex-shrink: 0;

    &:hover:not(:disabled) {
      border-color: $accent-primary;
      color: $accent-primary;
      background: rgba($accent-primary, 0.1);
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  &__scene-icon {
    font-size: 14px;
  }

  &__input-area {
    display: flex;
    gap: 10px;
    padding: 12px 16px;
    border-top: 1px solid $border-subtle;
    flex-shrink: 0;
  }

  &__input {
    flex: 1;
    padding: 10px 16px;
    background: $bg-glass;
    border: 1px solid $border-subtle;
    border-radius: $radius-full;
    color: $text-primary;
    font-size: $font-size-base;
    outline: none;
    transition: border-color 0.2s;

    &::placeholder {
      color: $text-muted;
    }

    &:focus {
      border-color: $accent-primary;
    }

    &:disabled {
      opacity: 0.5;
    }
  }

  &__send-btn {
    padding: 10px 20px;
    background: $accent-primary;
    border: none;
    border-radius: $radius-full;
    color: $text-on-accent;
    font-size: $font-size-sm;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;

    &:hover:not(:disabled) {
      background: $accent-secondary;
    }

    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
  }
}
</style>
