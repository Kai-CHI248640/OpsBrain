<template>
  <div class="setup-container">
    <el-card class="setup-card" shadow="always">
      <div class="setup-header">
        <h1>初始化部署</h1>
        <p>首次部署 OpsBrain，请设置管理员账号</p>
      </div>

      <el-steps :active="step" align-center style="margin: 32px 0">
        <el-step title="创建管理员" description="设置账号密码" />
        <el-step title="初始化完成" description="准备就绪" />
      </el-steps>

      <!-- Step 1: 创建管理员 -->
      <div v-if="step === 0">
        <el-alert
          title="请牢记管理员账号和密码，后续所有管理操作都需要登录"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 24px"
        />

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="管理员用户名（2-64 位）"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item label="显示名称" prop="displayName">
            <el-input
              v-model="form.displayName"
              placeholder="显示名称（可留空，默认同用户名）"
              clearable
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="至少 6 位"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="再次输入密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              style="width: 100%"
              :loading="loading"
              @click="handleSetup"
            >
              {{ loading ? '初始化中...' : '创建账号并初始化' }}
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- Step 2: 完成 -->
      <div v-else class="setup-success">
        <el-result
          icon="success"
          title="初始化完成"
          sub-title="管理员账号已创建，系统准备就绪"
        >
          <template #extra>
            <el-button type="primary" size="large" @click="goToDashboard">
              进入控制台
            </el-button>
          </template>
        </el-result>
      </div>

      <div v-if="error" style="margin-top: 16px;">
        <el-alert
          :title="error"
          type="error"
          show-icon
          :closable="false"
        />
      </div>
    </el-card>
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

const form = reactive({
  username: '',
  displayName: '',
  password: '',
  confirmPassword: '',
})

const validateConfirm = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
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
    if (e.code === 'ERR_NETWORK') {
      error.value = '无法连接到后端服务'
    } else if (e.response?.status === 400) {
      error.value = detail || '初始化失败，系统可能已经初始化'
    } else {
      error.value = detail || `初始化失败 (${e.response?.status || '未知错误'})`
    }
  } finally {
    loading.value = false
  }
}

function goToDashboard() {
  router.push('/dashboard')
}
</script>

<style scoped>
.setup-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  padding: 40px 20px;
}

.setup-card {
  width: 520px;
  max-width: 100%;
}

.setup-header {
  text-align: center;
}

.setup-header h1 {
  font-size: 28px;
  font-weight: 800;
  margin: 0;
  color: #409eff;
  letter-spacing: 2px;
}

.setup-header p {
  color: #909399;
  margin: 8px 0 0;
}
</style>
