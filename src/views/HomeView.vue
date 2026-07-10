<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePlayerStore } from '@/stores/player'
import MusicPlayer from '@/components/MusicPlayer.vue'
import Playlist from '@/components/Playlist.vue'
import SongCard from '@/components/SongCard.vue'
import { getMockPlaylists } from '@/api/music'
import { getRecommendations } from '@/api/agent'
import type { Playlist as PlaylistData, Song } from '@/types/music'

const playerStore = usePlayerStore()
const dailyPlaylists = ref<PlaylistData[]>([])
const isLoading = ref(false)
const activeTab = ref<'recommend' | 'queue'>('recommend')

onMounted(async () => {
  isLoading.value = true
  try {
    // 尝试获取 AI 推荐，失败则使用 mock 数据
    try {
      const playlist = await getRecommendations()
      dailyPlaylists.value = [playlist]
    } catch {
      dailyPlaylists.value = getMockPlaylists()
    }
  } finally {
    isLoading.value = false
  }
})

/** 播放整个歌单 */
function playPlaylist(playlist: PlaylistData) {
  playerStore.playPlaylist(playlist.songs)
}

/** 播放单首歌曲 */
function playSong(song: Song) {
  // 将 playlist 的所有歌曲加入队列并播放指定歌曲
  const allSongs = dailyPlaylists.value.flatMap((p: PlaylistData) => p.songs)
  const startIndex = allSongs.findIndex((s: Song) => s.id === song.id)
  playerStore.playPlaylist(allSongs, Math.max(0, startIndex))
}
</script>

<template>
  <div class="home-view">
    <!-- 音乐播放器 -->
    <section class="home-view__player">
      <MusicPlayer />
    </section>

    <!-- 标签切换 -->
    <section class="home-view__tabs">
      <button
        class="home-view__tab"
        :class="{ 'home-view__tab--active': activeTab === 'recommend' }"
        @click="activeTab = 'recommend'"
      >
        今日推荐
      </button>
      <button
        class="home-view__tab"
        :class="{ 'home-view__tab--active': activeTab === 'queue' }"
        @click="activeTab = 'queue'"
      >
        播放队列
      </button>
    </section>

    <!-- 今日推荐 -->
    <section v-if="activeTab === 'recommend'" class="home-view__recommend">
      <div v-if="isLoading" class="home-view__loading">
        <div class="home-view__loading-spinner"></div>
        <p>AI DJ 正在为你挑选今日音乐...</p>
      </div>

      <template v-else>
        <div v-for="playlist in dailyPlaylists" :key="playlist.id" class="home-view__playlist">
          <div class="home-view__playlist-header">
            <h3 class="home-view__playlist-name">{{ playlist.name }}</h3>
            <button class="home-view__play-all-btn" @click="playPlaylist(playlist)">
              ▶ 播放全部
            </button>
          </div>
          <p class="home-view__playlist-desc">{{ playlist.description }}</p>
          <div class="home-view__song-list">
            <SongCard
              v-for="song in playlist.songs"
              :key="song.id"
              :song="song"
              :show-reason="true"
              @play="playSong"
            />
          </div>
        </div>
      </template>
    </section>

    <!-- 播放队列 -->
    <section v-else class="home-view__queue">
      <Playlist />
    </section>
  </div>
</template>

<style lang="scss">
.home-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;

  &__player {
    flex-shrink: 0;
    border-bottom: 1px solid $border-subtle;
  }

  &__tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid $border-subtle;
    flex-shrink: 0;
  }

  &__tab {
    flex: 1;
    padding: 10px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: $text-muted;
    font-size: $font-size-sm;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      color: $text-secondary;
    }

    &--active {
      color: $accent-primary;
      border-bottom-color: $accent-primary;
    }
  }

  &__recommend {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
  }

  &__loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    color: $text-secondary;
    gap: 16px;

    &-spinner {
      width: 40px;
      height: 40px;
      border: 3px solid $border-subtle;
      border-top-color: $accent-primary;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
  }

  &__playlist {
    margin-bottom: 20px;

    &-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    &-name {
      font-size: $font-size-base;
      font-weight: 700;
      color: $text-primary;
      margin: 0;
    }

    &-desc {
      font-size: $font-size-xs;
      color: $text-muted;
      margin: 0 0 10px;
    }
  }

  &__play-all-btn {
    background: rgba($accent-primary, 0.15);
    border: 1px solid rgba($accent-primary, 0.3);
    color: $accent-primary;
    padding: 4px 14px;
    border-radius: $radius-full;
    font-size: $font-size-xs;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: rgba($accent-primary, 0.25);
    }
  }

  &__song-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  &__queue {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
