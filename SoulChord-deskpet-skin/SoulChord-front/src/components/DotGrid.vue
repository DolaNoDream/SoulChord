<script setup lang="ts">
/**
 * DotGrid.vue — 交互式点阵背景
 * Canvas 绘制网格白点，鼠标经过时产生"被球从下方顶起"的 3D 凸起效果：
 *   - 点向上位移（球体隆起）
 *   - 变亮（隆起处更清晰）
 *   - 平滑衰减（cosine falloff）
 */
import { ref, onMounted, onUnmounted } from 'vue'

const canvasRef = ref<HTMLCanvasElement | null>(null)

// ── 鼠标跟踪 ──
const mouse = { x: -9999, y: -9999 }

function onMouseMove(e: MouseEvent) {
  mouse.x = e.clientX
  mouse.y = e.clientY
}

function onMouseLeave() {
  mouse.x = -9999
  mouse.y = -9999
}

// ── Canvas 渲染 ──
let animId: number | null = null
let width = 0
let height = 0
let dpr = 1

const SPACING = 20
const DOT_RADIUS = 1.2
const EFFECT_RADIUS = 160
const MAX_DISPLACEMENT = 14
const BASE_ALPHA = 0.10
const PEAK_ALPHA = 0.55

function resize() {
  const canvas = canvasRef.value
  if (!canvas) return
  dpr = window.devicePixelRatio || 1
  width = window.innerWidth
  height = window.innerHeight
  canvas.width = width * dpr
  canvas.height = height * dpr
  canvas.style.width = width + 'px'
  canvas.style.height = height + 'px'
}

/** 平滑 falloff：cosine，中心 1 → 边缘 0 */
function falloff(dist: number): number {
  if (dist >= EFFECT_RADIUS) return 0
  return Math.cos((dist / EFFECT_RADIUS) * Math.PI / 2)
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)

  const mx = mouse.x
  const my = mouse.y

  // 检测主题：白天用灰色，夜晚用白色
  const isLight = document.documentElement.classList.contains('theme-light')
  const dotR = isLight ? 130 : 255
  const dotG = isLight ? 130 : 255
  const dotB = isLight ? 130 : 255

  // 逐行逐列绘制点阵
  for (let x = SPACING; x < width; x += SPACING) {
    for (let y = SPACING; y < height; y += SPACING) {
      const dx = x - mx
      const dy = y - my
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < EFFECT_RADIUS) {
        const t = falloff(dist)                          // 0~1 隆起强度
        const offsetY = -t * MAX_DISPLACEMENT            // 向上位移
        const alpha = BASE_ALPHA + t * (PEAK_ALPHA - BASE_ALPHA)

        ctx.beginPath()
        ctx.arc(x, y + offsetY, DOT_RADIUS * (1 + t * 0.4), 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${dotR}, ${dotG}, ${dotB}, ${alpha})`
        ctx.fill()
      } else {
        ctx.beginPath()
        ctx.arc(x, y, DOT_RADIUS, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${dotR}, ${dotG}, ${dotB}, ${BASE_ALPHA})`
        ctx.fill()
      }
    }
  }

  animId = requestAnimationFrame(draw)
}

onMounted(() => {
  resize()
  window.addEventListener('resize', resize)
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseleave', onMouseLeave)
  animId = requestAnimationFrame(draw)
})

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseleave', onMouseLeave)
  if (animId) cancelAnimationFrame(animId)
})
</script>

<template>
  <canvas ref="canvasRef" class="dot-grid"></canvas>
</template>

<style lang="scss">
.dot-grid {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;  /* 让鼠标事件穿透到文档 */
}
</style>
