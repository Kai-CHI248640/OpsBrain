<template>
  <div class="setup-page">
    <div class="setup-bg">
      <div class="bg-shape shape-1"></div>
      <div class="bg-shape shape-2"></div>
    </div>

    <div class="setup-card">
      <div class="setup-header">
        <div class="brand-logo">OB</div>
        <h1>初始化部署</h1>
        <p>首次部署 OpsBrain，请设置管理员账号</p>
      </div>

      <el-steps :active="step" align-center class="setup-steps">
        <el-step title="创建管理员" description="设置账号密码" />
        <el-step title="初始化完成" description="准备就绪" />
      </el-steps>

      <div v-if="step === 0">
        <el-alert title="请牢记管理员账号和密码，后续所有管理操作都需要登录" type="warning" show-icon :closable="false" class="setup-alert" />

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" class="setup-form">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="管理员用户名（2-64 位）" :prefix-icon="User" clearable />
          </el-form-item>

          <el-form-item label="显示名称" prop="displayName">
            <el-input v-model="form.displayName" placeholder="显示名称（可留空）" clearable />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" placeholder="至少 6 位" :prefix-icon="Lock" show-password />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input v-model="form.confirmPassword" type="password" placeholder="再次输入密码" :prefix-icon="Lock" show-password />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" size="large" class="setup-btn" :loading="loading" @click="handleSetup">
              {{ loading ? '初始化中...' : '创建账号并初始化' }}
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <div v-else class="setup-success">
        <el-result icon="success" title="初始化完成" sub-title="管理员账号已创建，系统准备就绪">
          <template #extra>
            <el-button type="primary" size="large" @click="goToDashboard" class="setup-btn">进入控制台</el-button>
          </template>
        </el-result>
      </div>

      <div v-if="error" class="setup-error">
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
const step = ref(0)

const form = reactive({ username: '', displayName: '', password: '', confirmPassword: '' })

const validateConfirm = (rule, value, callback) => {
  if (value !== form.password) callback(new Error('两次输入的密码不一致'))
  else callback()
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '用户名长度 2-64 位', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度 6-128 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleSetup() {
  error.value = ''
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.setup(form.username, form.password, form.displayName)
    step.value = 1
    ElMessage.success('初始化成功')
  } catch (e) {
    const detail = e.response?.data?.detail
    if (e.code === 'ERR_NETWORK') error.value = '无法连接到后端服务'
    else if (e.response?.status === 400) error.value = detail || '初始化失败，系统可能已经初始化'
    else error.value = detail || `初始化失败 (${e.response?.status || '未知错误'})`
  } finally {
    loading.value = false
  }
}

function goToDashboard() { router.push('/dashboard') }
</script>

<style scoped>
.setup-page {
  display: flex; align-items: center; justify-content: center;
  min-height: 100vh; padding: 40px 20px; position: relative; overflow: hidden;
  background: var(--bg-color);
}

.setup-bg { position: absolute; inset: 0; pointer-events: none; }
.bg-shape { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.15; }
.shape-1 { width: 500px; height: 500px; background: #8b5cf6; top: -150px; left: -100px; }
.shape-2 { width: 400px; height: 400px; background: #3b82f6; bottom: -100px; right: -100px; }

.setup-card {
  width: 520px; max-width: 100%; padding: 40px 32px;
  background: var(--card-bg); border: 1px solid var(--border-color);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
  position: relative; z-index: 1;
}

.setup-header { text-align: center; margin-bottom: 24px; }
.brand-logo {
  width: 56px; height: 56px; border-radius: 14px; margin: 0 auto 16px;
  background: linear-gradient(135deg, #8b5cf6, #3b82f6);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 900; font-size: 20px; letter-spacing: -1px;
  box-shadow: 0 4px 14px rgba(139, 92, 246, 0.3);
}
.setup-header h1 { font-size: 24px; font-weight: 800; color: var(--text-color); margin: 0; letter-spacing: 1px; }
.setup-header p { color: var(--text-secondary); margin: 6px 0 0; font-size: 14px; }

.setup-steps { margin: 28px 0; }
.setup-alert { margin-bottom: 24px; border-radius: var(--radius-sm); }
.setup-form :deep(.el-form-item__label) { font-weight: 600; color: var(--text-secondary); font-size: 13px; }
.setup-form :deep(.el-input__wrapper) { border-radius: var(--radius-sm) !important; }

.setup-btn {
  width: 100%; height: 44px; font-size: 15px; font-weight: 600;
  border-radius: var(--radius-sm) !important; letter-spacing: 1px;
  background: linear-gradient(135deg, #8b5cf6, #3b82f6) !important;
  border: none !important;
}

.setup-success { padding: 20px 0; }
.setup-error { margin-top: 16px; }

@media (max-width: 480px) {
  .setup-card { padding: 28px 20px; }
  .setup-header h1 { font-size: 20px; }
}
</style>
