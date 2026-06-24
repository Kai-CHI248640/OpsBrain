<template>
  <div class="task-list">
    <div class="page-header">
      <h2>定时任务管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showModal = true">
          <el-icon><Plus /></el-icon>
          新增任务
        </el-button>
      </div>
    </div>

    <div class="task-stats">
      <el-statistic title="任务总数" :value="tasks.length" />
      <el-statistic title="已启用" :value="enabledCount" />
      <el-statistic title="已禁用" :value="disabledCount" />
    </div>

    <div class="task-table">
      <el-table :data="tasks" v-loading="loading" border>
        <el-table-column prop="name" label="任务名称" min-width="150" />
        <el-table-column prop="target_agent_name" label="目标Agent" min-width="120" />
        <el-table-column label="时间模式" min-width="100">
          <template #default="{ row }">
            <el-tag :type="row.time_mode === 'simple' ? 'primary' : 'warning'">
              {{ row.time_mode === 'simple' ? '简单模式' : '高级模式' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间配置" min-width="200">
          <template #default="{ row }">
            <div class="time-config-preview">
              <span v-if="row.time_mode === 'simple'">
                {{ formatSimpleTime(row.time_config) }}
              </span>
              <span v-else>
                {{ formatAdvancedTime(row.time_config) }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" min-width="160" />
        <el-table-column label="状态" min-width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_enabled"
              @change="(val) => handleToggle(row, val)"
              :loading="toggleLoading[row.id]"
            />
          </template>
        </el-table-column>
        <el-table-column prop="execution_count" label="执行次数" min-width="80" />
        <el-table-column prop="last_executed_at" label="最后执行" min-width="160" />
        <el-table-column label="操作" min-width="160">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button size="small" @click="handleViewLogs(row)">日志</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="tasks.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无定时任务，点击上方按钮新增" />
      </div>
    </div>

    <TaskFormModal
      v-model:visible="showModal"
      :edit-data="editData"
      :agents="agents"
      @submit="handleFormSubmit"
    />

    <el-dialog
      v-model="showLogs"
      title="执行日志"
      width="800px"
    >
      <el-table :data="logs" border>
        <el-table-column prop="execution_time" label="执行时间" min-width="160" />
        <el-table-column prop="target_agent_name" label="目标Agent" min-width="120" />
        <el-table-column prop="task_content" label="任务内容" min-width="200" />
        <el-table-column label="状态" min-width="80">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="200" />
      </el-table>
      <div v-if="logs.length === 0" class="empty-state">
        <el-empty description="暂无执行日志" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useTaskStore } from '@/stores/task'
import { useTopologyStore } from '@/stores/topology'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import TaskFormModal from '@/components/TaskFormModal.vue'

const taskStore = useTaskStore()
const topologyStore = useTopologyStore()

const showModal = ref(false)
const showLogs = ref(false)
const editData = ref(null)
const logs = ref([])
const toggleLoading = ref({})

const tasks = computed(() => taskStore.tasks)
const loading = computed(() => taskStore.loading)

const enabledCount = computed(() => tasks.value.filter(t => t.is_enabled).length)
const disabledCount = computed(() => tasks.value.filter(t => !t.is_enabled).length)

const agents = computed(() => {
  const result = []
  const subagents = topologyStore.subagents || []
  subagents.forEach(sa => {
    result.push({ id: sa.id, name: sa.name })
  })
  result.push({ id: 'master', name: '总控Agent' })
  return result
})

onMounted(() => {
  taskStore.fetchTasks()
  topologyStore.fetchSubagents()
})

function formatSimpleTime(config) {
  if (!config || !config.weekDays || !config.time) return '-'
  const dayMap = { 0: '日', 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六' }
  const days = config.weekDays.map(d => dayMap[d]).sort().join('、')
  return `${days} ${config.time}`
}

function formatAdvancedTime(config) {
  if (!config || !config.schedules) return '-'
  const dayMap = { 0: '周日', 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六' }
  const times = []
  Object.keys(config.schedules).forEach(day => {
    config.schedules[day].forEach(hour => {
      times.push(`${dayMap[day]} ${hour - 1}:00`)
    })
  })
  return times.length > 3 ? `${times.slice(0, 3).join('、')}...` : times.join('、')
}

function getStatusTagType(status) {
  const map = {
    running: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

function getStatusText(status) {
  const map = {
    running: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

function handleFormSubmit(data) {
  if (data.id) {
    taskStore.updateTask(data.id, data).then(() => {
      ElMessage.success('任务更新成功')
    }).catch(() => {
      ElMessage.error('任务更新失败')
    })
  } else {
    taskStore.createTask(data).then(() => {
      ElMessage.success('任务创建成功')
    }).catch(() => {
      ElMessage.error('任务创建失败')
    })
  }
}

function handleEdit(row) {
  editData.value = { ...row }
  showModal.value = true
}

async function handleDelete(row) {
  await ElMessage.confirm(`确定删除任务 "${row.name}" 吗？`, '提示', {
    type: 'warning'
  })
  try {
    await taskStore.deleteTask(row.id)
    ElMessage.success('任务删除成功')
  } catch {
    ElMessage.error('任务删除失败')
  }
}

function handleToggle(row, val) {
  toggleLoading.value[row.id] = true
  taskStore.toggleTask(row.id, val).then(() => {
    ElMessage.success(val ? '任务已启用' : '任务已禁用')
  }).catch(() => {
    ElMessage.error('操作失败')
  }).finally(() => {
    toggleLoading.value[row.id] = false
  })
}

async function handleViewLogs(row) {
  logs.value = await taskStore.fetchLogs(row.id)
  showLogs.value = true
}
</script>

<style scoped>
.task-list {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.task-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.task-table {
  background: #fff;
  border-radius: 8px;
}

.time-config-preview {
  color: #606266;
  font-size: 13px;
}

.empty-state {
  padding: 40px;
}
</style>
