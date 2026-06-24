<template>
  <div class="workflow-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">工作流</h2>
        <p class="page-desc">可视化编排多个 Agent 协同工作</p>
      </div>
      <el-button type="primary" icon="Plus" @click="showCreateDialog = true">新建工作流</el-button>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="workflows.length === 0" class="empty-state">
      <div class="empty-icon">⚡</div>
      <p>暂无工作流</p>
      <p class="empty-hint">创建工作流来编排 Agent 自动执行运维任务</p>
      <el-button type="primary" @click="showCreateDialog = true">创建工作流</el-button>
    </div>

    <div v-else class="workflow-grid">
      <div v-for="wf in workflows" :key="wf.id" class="workflow-card" @click="openDesigner(wf.id)">
        <div class="wf-card-header">
          <div class="wf-card-icon">⚡</div>
          <div class="wf-card-info">
            <div class="wf-card-name">{{ wf.name }}</div>
            <div class="wf-card-desc">{{ wf.description || '暂无描述' }}</div>
          </div>
          <el-dropdown trigger="click" @command="handleCommand($event, wf)" @click.stop>
            <el-button text icon="More" @click.stop />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="execute">执行</el-dropdown-item>
                <el-dropdown-item command="export">导出</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="wf-card-body">
          <div class="wf-stat">
            <span class="wf-stat-num">{{ wf.nodes?.length || 0 }}</span>
            <span class="wf-stat-label">节点</span>
          </div>
          <div class="wf-stat">
            <span class="wf-stat-num">{{ wf.edges?.length || 0 }}</span>
            <span class="wf-stat-label">连线</span>
          </div>
          <div class="wf-stat">
            <span class="wf-stat-num">{{ wf.is_template ? '模板' : '工作流' }}</span>
            <span class="wf-stat-label">类型</span>
          </div>
        </div>
        <div class="wf-card-footer">
          <span class="wf-time">{{ formatTime(wf.updated_at) }}</span>
          <el-tag size="small" :type="wf.is_enabled ? 'success' : 'info'">
            {{ wf.is_enabled ? '已启用' : '已禁用' }}
          </el-tag>
        </div>
      </div>
    </div>

    <el-dialog v-model="showCreateDialog" title="新建工作流" width="480px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newWf.name" placeholder="输入工作流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newWf.description" type="textarea" :rows="3" placeholder="工作流描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createWorkflow" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/stores/auth'

const router = useRouter()

const loading = ref(true)
const creating = ref(false)
const workflows = ref([])
const showCreateDialog = ref(false)
const newWf = ref({ name: '', description: '' })

const fetchWorkflows = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/workflows/')
    workflows.value = data.workflows || []
  } catch (e) {
    console.error('Workflow error:', e)
    ElMessage.error('加载工作流失败')
  } finally {
    loading.value = false
  }
}

const createWorkflow = async () => {
  creating.value = true
  try {
    const { data } = await api.post('/workflows/', {
      name: newWf.value.name || undefined,
      description: newWf.value.description,
      nodes: [
        { id: 'start', type: 'start', position: { x: 100, y: 200 }, data: { label: '开始' } },
        { id: 'end', type: 'end', position: { x: 600, y: 200 }, data: { label: '结束' } },
      ],
      edges: [],
    })
    ElMessage.success('工作流创建成功')
    showCreateDialog.value = false
    newWf.value = { name: '', description: '' }
    router.push(`/workflow/${data.id}`)
  } catch (e) {
    ElMessage.error('创建工作流失败')
  } finally {
    creating.value = false
  }
}

const openDesigner = (id) => {
  router.push(`/workflow/${id}`)
}

const handleCommand = async (cmd, wf) => {
  if (cmd === 'edit') {
    router.push(`/workflow/${wf.id}`)
  } else if (cmd === 'execute') {
    try {
      await api.post(`/workflows/${wf.id}/execute`, {})
      ElMessage.success('工作流已开始执行')
    } catch (e) {
      ElMessage.error('执行失败')
    }
  } else if (cmd === 'export') {
    try {
      const { data } = await api.get(`/workflows/export/${wf.id}`)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${wf.name}.json`
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    } catch {
      ElMessage.error('导出失败')
    }
  } else if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(`确定删除工作流 "${wf.name}"？`, '确认删除', { type: 'warning' })
      await api.delete(`/workflows/${wf.id}`)
      ElMessage.success('已删除')
      fetchWorkflows()
    } catch {}
  }
}

const formatTime = (t) => {
  if (!t) return ''
  const d = new Date(t)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  fetchWorkflows()
})
</script>

<style scoped>
.workflow-page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; color: var(--text-color); margin: 0; }
.page-desc { color: var(--text-secondary); margin: 4px 0 0; font-size: 13px; }

.empty-state { text-align: center; padding: 80px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-state p { color: var(--text-secondary); margin: 8px 0; }
.empty-hint { font-size: 13px; color: var(--text-muted); }

.workflow-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }

.workflow-card {
  background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px;
  padding: 20px; cursor: pointer; transition: all 0.2s;
}
.workflow-card:hover { border-color: var(--primary-color); transform: translateY(-2px); box-shadow: var(--shadow-md); }

.wf-card-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
.wf-card-icon { font-size: 28px; }
.wf-card-info { flex: 1; min-width: 0; }
.wf-card-name { font-size: 16px; font-weight: 600; color: var(--text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-card-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

.wf-card-body { display: flex; gap: 24px; margin-bottom: 16px; padding: 12px 0; border-top: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color); }
.wf-stat { text-align: center; flex: 1; }
.wf-stat-num { display: block; font-size: 18px; font-weight: 700; color: var(--primary-color); }
.wf-stat-label { font-size: 11px; color: var(--text-secondary); }

.wf-card-footer { display: flex; justify-content: space-between; align-items: center; }
.wf-time { font-size: 12px; color: var(--text-muted); }

.loading-state { padding: 24px; }
</style>
