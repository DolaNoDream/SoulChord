<script setup lang="ts">
/**
 * DigitalOrb.vue — 像素音频可视化柱状图
 * 使用 Web Audio API AnalyserNode 读取真实音频频率数据，
 * 激昂时柱子高、轻柔时低。无音频时柔和呼吸降级。
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { usePlayerStore } from '@/stores/player'

const playerStore = usePlayerStore()

const BAR_COUNT = 20
const barHeights = ref<number[]>(Array(BAR_COUNT).fill(4))

// ── Web Audio API ──
let audioCtx: AudioContext | null = null
let analyser: AnalyserNode | null = null
let dataArray: Uint8Array | null = null
let useRealAudio = false

function initWebAudio() {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const anl = ctx.createAnalyser()
    anl.fftSize = 64                    // → 32 个频率 bin
    anl.smoothingTimeConstant = 0.85    // 硬件级平滑，变化慢

    const audio = playerStore.audioElement
    if (audio && !(audio as any).__viz) {
      const src = ctx.createMediaElementSource(audio)
      src.connect(anl)
      // ★ 必须连 destination，否则音频静默（createMediaElementSource 会断开默认输出）
      anl.connect(ctx.destination)
      ;(audio as any).__viz = true
    } else if (!audio) {
      ctx.close()
      return
    }

    audioCtx = ctx
    analyser = anl
    dataArray = new Uint8Array(anl.frequencyBinCount)  // 32
    useRealAudio = true
  } catch {
    useRealAudio = false
  }
}

/** 从 AnalyserNode 读取频率数据映射为柱子高度 */
function readAnalyserHeights(): number[] | null {
  if (!analyser || !dataArray || !audioCtx) return null

  // AudioContext 因浏览器策略 suspend → 尝试 resume
  if (audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
    return null
  }

  try {
    analyser.getByteFrequencyData(dataArray)
    const heights: number[] = []
    const step = dataArray.length / BAR_COUNT
    for (let i = 0; i < BAR_COUNT; i++) {
      const idx = Math.min(Math.floor(i * step), dataArray.length - 1)
      const normalized = dataArray[idx] / 255        // 0 ~ 1
      const curved = Math.pow(normalized, 0.45)       // 指数拉伸，低音更明显
      heights.push(Math.max(3, curved * 44 + 3))      // 映射到 3~47px
    }
    return heights
  } catch {
    return null
  }
}

// ── 过程动画降级（无真实音频时使用）──
let time = 0

function calcProcedural(i: number, t: number, active: boolean): number {
  const phase = (i / BAR_COUNT) * Math.PI * 2
  if (active) {
    const wave = Math.sin(t * 1.8 + phase) * 0.3 + 0.5
    const bounce = Math.sin(t * 3 + phase * 1.5) * 0.2
    return Math.max(3, (wave + bounce) * 34 + 6)
  } else {
    const wave = Math.sin(t * 0.35 + phase) * 0.3 + 0.5
    return Math.max(3, wave * 8 + 3)
  }
}

// ── 渲染循环 ──
let animId: number | null = null
const smoothBuf = Array(BAR_COUNT).fill(4)

function tick() {
  const isActive = playerStore.isPlaying && !playerStore.isLoading

  // 1) 采样子 → 真实频率数据
  let raw: number[] | null = null
  if (useRealAudio) raw = readAnalyserHeights()

  // 2) 降级 → 过程动画
  if (!raw) {
    time += isActive ? 0.016 : 0.008
    raw = smoothBuf.map((_, i) => calcProcedural(i, time, isActive))
  }

  // 3) JS 层平滑插值（让跳变更柔和）
  const factor = 0.22
  for (let i = 0; i < BAR_COUNT; i++) {
    smoothBuf[i] += (raw[i] - smoothBuf[i]) * factor
  }
  barHeights.value = smoothBuf.slice()

  animId = requestAnimationFrame(tick)
}

onMounted(() => {
  initWebAudio()
  animId = requestAnimationFrame(tick)
})

onUnmounted(() => {
  if (animId) cancelAnimationFrame(animId)
  // 不关闭 audioCtx，避免后续复用冲突
})
</script>

<template>
  <div class="visualizer">
    <div
      v-for="(h, i) in barHeights"
      :key="i"
      class="visualizer__bar"
      :style="{ height: h + 'px' }"
    ></div>
  </div>
</template>

<style lang="scss" scoped>
@use 'sass:math';

.visualizer {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 3px;
  height: 52px;
  padding: 0 20px;
  margin: 8px auto 4px;

  &__bar {
    width: 4px;
    min-height: 3px;
    background: $accent-primary;
    border-radius: 0;        /* 平顶，像素感 */
    transition: height 0.04s ease-out;

    /* 从左到右渐变透明度 */
    @for $i from 0 through 19 {
      &:nth-child(#{$i + 1}) {
        opacity: 0.5 + math.div($i, 19) * 0.35;
      }
    }
  }
}
</style>
