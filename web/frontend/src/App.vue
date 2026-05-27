<template>
  <div id="app-loading" v-if="initializing">
    <div class="loading-container">
      <div class="loading-logo">OpsBrain</div>
      <div class="loading-spinner"></div>
      <div class="loading-text">正在初始化...</div>
    </div>
  </div>
  <router-view v-else />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/stores/auth'

const router = useRouter()
const initializing = ref(true)

onMounted(async () => {
  try {
    // Step 1: 检查是否需要首次部署
    let needsSetup = false
    try {
      const resp = await api.get('/auth/setup-required')
      needsSetup = resp.data.setup_required
    } catch {
      // API 不可达 — 可能后端还没起
      needsSetup = false
    }

    if (needsSetup) {
      router.replace('/setup')
      return
    }

    // Step 2: 检查是否已登录
    const token = localStorage.getItem('opsbrain-token')
    const savedUser = localStorage.getItem('opsbrain-user')

    if (token && savedUser) {
      // 有 token，验证是否有效
      try {
        await api.get('/auth/me')
        router.replace('/dashboard')
        return
      } catch {
        // token 过期或无效，清掉走登录
        localStorage.removeItem('opsbrain-token')
        localStorage.removeItem('opsbrain-user')
      }
    }

    // Step 3: 没登录，去登录页
    router.replace('/login')
  } finally {
    initializing.value = false
  }
})
</script>

<style>
/* ── 全局初始化加载动画 ── */
#app-loading {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #141414;
  z-index: 9999;
}

.loading-container {
  text-align: center;
}

.loading-logo {
  font-size: 36px;
  font-weight: 800;
  color: #409eff;
  margin-bottom: 24px;
  letter-spacing: 4px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  margin: 0 auto;
  border: 3px solid #363637;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  margin-top: 16px;
  color: #909399;
  font-size: 14px;
}

body {
  margin: 0;
  padding: 0;
}
</style>
