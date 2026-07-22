<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const now = ref(new Date())
let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => { timer = setInterval(() => { now.value = new Date() }, 1000) })
onUnmounted(() => { if (timer) clearInterval(timer) })

/** 格式化为 HH:mm */
function formatTime(d: Date): string {
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="clock">
    <div class="clock__time">{{ formatTime(now) }}</div>
    <div class="clock__detail">
      {{ WEEKDAYS[now.getDay()] }} · {{ now.getMonth() + 1 }}月{{ now.getDate() }}日
    </div>
  </div>
</template>

<style lang="scss">
.clock {
  text-align: center;
  padding: 24px 20px 4px;
  user-select: none;

  &__time {
    font-size: 96px;
    font-weight: 600;
    font-family: $font-display;
    color: var(--text-primary);
    letter-spacing: 8px;
    font-variant-numeric: tabular-nums;
    line-height: 1;
    text-shadow: var(--text-glow);
  }

  &__detail {
    margin-top: 8px;
    font-family: $font-mono;
    font-size: $font-size-xs;
    color: var(--text-muted);
    letter-spacing: 2px;
    text-transform: uppercase;
  }
}
</style>
