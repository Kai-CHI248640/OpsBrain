<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-shape shape-1"></div>
      <div class="bg-shape shape-2"></div>
      <div class="bg-shape shape-3"></div>
    </div>

    <div class="login-card">
      <div class="login-header">
        <div class="brand-logo">OB</div>
        <h1>OpsBrain</h1>
        <p>AI 网络运维平台</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin" class="login-form">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="输入管理员用户名" :prefix-icon="User" size="large" clearable />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="输入密码" :prefix-icon="Lock" size="large" show-password @keyup.enter="handleLogin" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="handleLogin">
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="error" class="login-error">
        <el-alert :title="error" type="error" show-icon :closable="false" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref(null)
const loading = ref(false)
const error = ref('')

const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

async function handleLogin() {
  error.value = ''
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    if (e.message?.includes('Invalid username or password')) {
      error.value = '用户名或密码错误'
    } else if (e.message?.includes('ERR_NETWORK') || e.message?.includes('Network Error')) {
      error.value = '无法连接到服务器，请确认后端已启动'
    } else {
      error.value = e.message || '登录失败'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex; align-items: center; justify-content: center;
  min-height: 100vh; padding: 20px; position: relative; overflow: hidden;
  background: var(--bg-color);
}

.login-bg { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.bg-shape {
  position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.15;
}
.shape-1 { width: 600px; height: 600px; background: #3b82f6; top: -200px; right: -100px; }
.shape-2 { width: 400px; height: 400px; background: #8b5cf6; bottom: -100px; left: -100px; }
.shape-3 { width: 300px; height: 300px; background: #10b981; top: 50%; left: 50%; transform: translate(-50%, -50%); }

.login-card {
  width: 420px; max-width: 100%; padding: 40px 32px;
  background: var(--card-bg); border: 1px solid var(--border-color);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
  position: relative; z-index: 1;
}

.login-header { text-align: center; margin-bottom: 36px; }
.brand-logo {
  width: 56px; height: 56px; border-radius: 14px; margin: 0 auto 16px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 900; font-size: 20px; letter-spacing: -1px;
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.3);
}
.login-header h1 {
  font-size: 28px; font-weight: 800; color: var(--text-color);
  margin: 0; letter-spacing: 2px;
}
.login-header p { color: var(--text-secondary); margin: 6px 0 0; font-size: 14px; }

.login-form :deep(.el-form-item__label) { font-weight: 600; color: var(--text-secondary); font-size: 13px; }
.login-form :deep(.el-input__wrapper) { border-radius: var(--radius-sm) !important; }

.login-btn {
  width: 100%; height: 44px; font-size: 15px; font-weight: 600;
  border-radius: var(--radius-sm) !important; letter-spacing: 1px;
  background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
  border: none !important;
}
.login-btn:hover { opacity: 0.9; }

.login-error { margin-top: 16px; }

@media (max-width: 480px) {
  .login-card { padding: 28px 20px; }
  .login-header h1 { font-size: 24px; }
  .brand-logo { width: 48px; height: 48px; font-size: 18px; }
}
</style>
