<script setup lang="ts">
import type { ChatMessage } from '@/types/chat'
import { useUserStore } from '@/stores/user'
import SongCard from './SongCard.vue'

defineProps<{
  message: ChatMessage
}>()

const userStore = useUserStore()

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
    class="transcript"
    :class="{
      'transcript--user': message.role === 'user',
      'transcript--assistant': message.role === 'assistant',
      'transcript--streaming': message.isStreaming,
    }"
  >
    <!-- role label -->
    <div class="transcript__label">
      <img v-if="message.role === 'user' && userStore.localAvatar" :src="userStore.localAvatar" class="transcript__avatar" />
      <img v-if="message.role === 'assistant' && userStore.djAvatar" :src="userStore.djAvatar" class="transcript__avatar" />
      <span class="transcript__role" :class="`transcript__role--${message.role}`">
        {{ message.role === 'user' ? userStore.nickname : userStore.djName }}
      </span>
      <span class="transcript__time">{{ formatTime(message.timestamp) }}</span>
    </div>

    <!-- 消息内容 -->
    <div class="transcript__body">
      <p class="transcript__text">
        {{ message.content }}
        <span v-if="message.isStreaming" class="transcript__cursor">|</span>
      </p>
    </div>

    <!-- 操作指示器 -->
    <div v-if="message.operation && message.role === 'assistant'" class="transcript__operation">
      <span v-if="message.operation === 'recommend'" class="transcript__op-tag transcript__op-tag--recommend">🎵 歌曲推荐</span>
      <span v-else-if="message.operation === 'play_song'" class="transcript__op-tag transcript__op-tag--play">▶ 正在播放</span>
      <span v-else-if="message.operation === 'skip_song'" class="transcript__op-tag transcript__op-tag--skip">⏭ 已切歌</span>
      <span v-else-if="message.operation === 'add_playlist'" class="transcript__op-tag transcript__op-tag--add">📋 已加入队列</span>
      <span v-else-if="message.operation === 'song_intro'" class="transcript__op-tag transcript__op-tag--intro">📖 歌曲介绍</span>
    </div>

    <!-- 歌曲链接预览 -->
    <div v-if="message.url && message.role === 'assistant'" class="transcript__url-preview">
      <img v-if="message.url.match(/\.(jpg|jpeg|png|gif|webp)(\?|$)/i)" :src="message.url" class="transcript__url-img" />
    </div>

    <!-- 附件：歌曲推荐 -->
    <div v-if="message.attachments && message.attachments.length > 0" class="transcript__attachments">
      <template v-for="att in message.attachments" :key="att.type + (att.type === 'song' ? att.song.id : '')">
        <div v-if="att.type === 'song'" class="transcript__song-attachment">
          <SongCard :song="att.song" :show-reason="true" @play="() => {}" />
        </div>
        <div v-else-if="att.type === 'playlist'" class="transcript__playlist-attachment">
          <p class="transcript__playlist-name">📻 推荐歌单</p>
          <p class="transcript__playlist-reason">{{ att.reason }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<style lang="scss">
.transcript {
  margin-bottom: 16px;
  animation: fadeIn 0.3s ease-out;

  &--user {
    align-self: flex-end;
    text-align: right;

    .transcript__label { flex-direction: row-reverse; }
    .transcript__role { color: $text-secondary; }
  }

  &--assistant {
    align-self: flex-start;

    .transcript__role { color: $accent-primary; }
  }

  &--streaming {
    .transcript__body {
      border-color: rgba($accent-warm, 0.3);
    }
  }

  /* ── role label ── */
  &__label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    padding: 0 4px;
  }

  &__role {
    font-family: $font-mono;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  &__avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }

  &__time {
    font-size: 10px;
    color: $text-muted;
    font-family: $font-mono;
  }

  /* ── 消息内容（透明，点阵透出）── */
  &__body {
    padding: 10px 14px;
    border-radius: $radius-md;
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    line-height: 1.7;
    word-break: break-word;
  }

  &__text {
    margin: 0;
    font-size: 14px;

    .transcript--assistant & {
      font-family: $font-ai;
    }
  }

  &__cursor {
    display: inline-block;
    animation: blink 0.8s infinite;
    color: $accent-warm;
    font-weight: bold;
    margin-left: 2px;
  }

  &__operation { margin-top: 6px; }

  &__op-tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: $radius-full;
    font-size: 10px;
    font-weight: 500;
    font-family: $font-mono;
    letter-spacing: 0.3px;

    &--recommend { background: rgba($accent-primary, 0.12); color: $accent-primary; }
    &--play { background: rgba($accent-success, 0.12); color: $accent-success; }
    &--skip { background: rgba($text-muted, 0.15); color: $text-secondary; }
    &--add { background: rgba($accent-cool, 0.12); color: $accent-cool; }
    &--intro { background: rgba($accent-warm, 0.12); color: $accent-warm; }
  }

  &__url-preview { margin-top: 8px; }

  &__url-img {
    max-width: 200px;
    max-height: 200px;
    border-radius: $radius-sm;
    object-fit: cover;
    border: 1px solid $border-subtle;
  }

  &__attachments {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  &__song-attachment { max-width: 280px; }

  &__playlist-attachment {
    background: rgba(20, 25, 40, 0.45);
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

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
