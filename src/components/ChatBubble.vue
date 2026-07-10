<script setup lang="ts">
import type { ChatMessage } from '@/types/chat'
import SongCard from './SongCard.vue'

defineProps<{
  message: ChatMessage
}>()

const emit = defineEmits<{
  playSong: [song: import('@/types/music').Song]
}>()

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`

  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div
    class="chat-bubble"
    :class="{
      'chat-bubble--user': message.role === 'user',
      'chat-bubble--assistant': message.role === 'assistant',
      'chat-bubble--streaming': message.isStreaming,
    }"
  >
    <!-- 头像 -->
    <div class="chat-bubble__avatar">
      <template v-if="message.role === 'user'">
        <div class="chat-bubble__avatar-icon chat-bubble__avatar-icon--user">👤</div>
      </template>
      <template v-else>
        <div class="chat-bubble__avatar-icon chat-bubble__avatar-icon--dj">🎧</div>
      </template>
    </div>

    <!-- 消息内容 -->
    <div class="chat-bubble__body">
      <div class="chat-bubble__header">
        <span class="chat-bubble__name">
          {{ message.role === 'user' ? '我' : 'AI DJ' }}
        </span>
        <span class="chat-bubble__time">{{ formatTime(message.timestamp) }}</span>
      </div>

      <!-- 文字内容 -->
      <div class="chat-bubble__content">
        <p>{{ message.content }}</p>
        <span v-if="message.isStreaming" class="chat-bubble__cursor">|</span>
      </div>

      <!-- 附件：歌曲推荐 -->
      <div
        v-if="message.attachments && message.attachments.length > 0"
        class="chat-bubble__attachments"
      >
        <template v-for="att in message.attachments" :key="att.type + (att.type === 'song' ? att.song.id : '')">
          <div v-if="att.type === 'song'" class="chat-bubble__song-attachment">
            <SongCard
              :song="att.song"
              :show-reason="true"
              @play="emit('playSong', att.song)"
            />
          </div>
          <div v-else-if="att.type === 'playlist'" class="chat-bubble__playlist-attachment">
            <p class="chat-bubble__playlist-name">📻 {{ att.playlist.name }}</p>
            <p class="chat-bubble__playlist-reason">{{ att.reason }}</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style lang="scss">
.chat-bubble {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  animation: bubbleIn 0.3s ease-out;

  &--user {
    flex-direction: row-reverse;

    .chat-bubble__body {
      align-items: flex-end;
    }

    .chat-bubble__content {
      background: rgba($accent-primary, 0.2);
      border: 1px solid rgba($accent-primary, 0.3);
    }
  }

  &--assistant {
    .chat-bubble__content {
      background: $bg-glass;
    }
  }

  &--streaming {
    .chat-bubble__content {
      border-color: rgba($accent-warm, 0.3);
    }
  }

  &__avatar {
    flex-shrink: 0;
    width: 36px;
    height: 36px;

    &-icon {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      font-size: 18px;

      &--user {
        background: linear-gradient(135deg, $accent-primary, $accent-secondary);
      }

      &--dj {
        background: linear-gradient(135deg, $accent-warm, #ef4444);
      }
    }
  }

  &__body {
    display: flex;
    flex-direction: column;
    max-width: 80%;
    min-width: 0;
  }

  &__header {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 4px;
    padding: 0 4px;
  }

  &__name {
    font-size: $font-size-xs;
    color: $text-secondary;
    font-weight: 600;
  }

  &__time {
    font-size: 10px;
    color: $text-muted;
  }

  &__content {
    padding: 10px 14px;
    border-radius: $radius-md;
    border: 1px solid $border-subtle;
    color: $text-primary;
    font-size: $font-size-base;
    line-height: 1.6;
    word-break: break-word;

    p {
      margin: 0;
      display: inline;
    }
  }

  &__cursor {
    display: inline-block;
    animation: blink 0.8s infinite;
    color: $accent-warm;
    font-weight: bold;
  }

  &__attachments {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  &__song-attachment {
    max-width: 280px;
  }

  &__playlist-attachment {
    background: $bg-glass;
    padding: 10px 14px;
    border-radius: $radius-md;
    border: 1px solid $border-subtle;

    &-name {
      margin: 0;
      font-weight: 600;
      color: $text-primary;
      font-size: $font-size-sm;
    }

    &-reason {
      margin: 4px 0 0;
      font-size: $font-size-xs;
      color: $text-secondary;
    }
  }
}

@keyframes bubbleIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
