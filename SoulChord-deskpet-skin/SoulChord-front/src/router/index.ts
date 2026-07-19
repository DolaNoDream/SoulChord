import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: DashboardView,
    meta: {
      title: 'SoulChord',
    },
  },
]

const router = createRouter({
  // 使用 hash 模式兼容 Electron file:// 协议
  history: createWebHashHistory(),
  routes,
})

// 路由守卫：更新页面标题
router.beforeEach((to) => {
  const title = to.meta?.title as string | undefined
  document.title = title ? `${title} - SoulChord` : 'SoulChord'
})

export default router
