import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: undefined })

// 从 localStorage 恢复主题（默认深色）
const savedTheme = localStorage.getItem('opsbrain-theme') || 'dark'
document.documentElement.setAttribute('data-theme', savedTheme)

// 全局错误处理
app.config.errorHandler = (err, vm, info) => {
  console.error('[OpsBrain Error]', err, info)
}

app.mount('#app')
