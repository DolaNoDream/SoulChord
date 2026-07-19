import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './assets/styles/global.scss'

// 创建应用实例
const app = createApp(App)

// Pinia 状态管理
const pinia = createPinia()
app.use(pinia)

// Vue Router
app.use(router)

// Element Plus
app.use(ElementPlus, { size: 'default', zIndex: 2000 })

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 挂载
app.mount('#app')
