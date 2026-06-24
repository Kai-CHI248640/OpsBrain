<template>
  <div class="topology-list">
    <div class="page-header">
      <div>
        <h2 class="page-title">网络拓扑</h2>
        <p class="page-desc">管理已发现的网络拓扑结构</p>
      </div>
      <el-button type="primary" size="large" :icon="Search" @click="startSniff" class="action-btn">
        开始嗅探
      </el-button>
    </div>

    <!-- 已保存的拓扑 -->
    <div v-if="topologies.length > 0" class="topo-grid">
      <div v-for="t in topologies" :key="t.id" class="topo-card" @click="openTopology(t)">
        <div class="topo-card-header">
          <div class="topo-card-icon">🗺️</div>
          <div class="topo-card-info">
            <div class="topo-card-name">{{ t.name }}</div>
            <div class="topo-card-meta">
              <el-tag size="small" :type="methodTag(t.discovery_method)" effect="plain" round>
                {{ methodLabel(t.discovery_method) }}
              </el-tag>
            </div>
          </div>
          <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, t)">
            <el-button text size="small" :icon="MoreFilled" class="more-btn" @click.stop />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename" :icon="EditPen">重命名</el-dropdown-item>
                <el-dropdown-item command="delete" :icon="Delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="topo-card-stats">
          <div class="topo-stat">
            <span class="topo-stat-value">{{ t.device_count }}</span>
            <span class="topo-stat-label">设备</span>
          </div>
          <div class="topo-stat">
            <span class="topo-stat-value">{{ t.link_count }}</span>
            <span class="topo-stat-label">链路</span>
          </div>
          <div class="topo-stat">
            <span class="topo-stat-value">{{ formatTime(t.updated_at || t.created_at) }}</span>
            <span class="topo-stat-label">更新</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="topologies.length === 0 && !loading" class="empty-state">
      <div class="empty-icon">🗺️</div>
      <h3>暂无拓扑数据</h3>
      <p>点击下方按钮开始发现网络拓扑</p>
      <el-button type="primary" size="large" :icon="Search" @click="startSniff" class="action-btn">
        开始第一次嗅探
      </el-button>
    </div>

    <div v-if="loading" class="loading-state">
      <el-icon :size="40" class="loading-icon"><Loading /></el-icon>
      <p>加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete, Loading, MoreFilled, EditPen } from '@element-plus/icons-vue'
import { api } from '@/stores/auth'

const router = useRouter()
const topologies = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const data = await api.get('/topology/')
    topologies.value = data || []
  } catch (e) {
    console.error('Failed to load topologies:', e)
  } finally {
    loading.value = false
  }
})

function startSniff() { router.push('/topology/wizard') }
function openTopology(row) { router.push(`/topology/${row.id}`) }

function handleCommand(cmd, row) {
  if (cmd === 'delete') deleteTopology(row)
  else if (cmd === 'rename') renameTopology(row)
}

async function renameTopology(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名拓扑', {
      inputValue: row.name,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
    })
    if (value && value !== row.name) {
      await api.put(`/topology/${row.id}`, { name: value })
      row.name = value
      ElMessage.success('已重命名')
    }
  } catch {}
}

async function deleteTopology(row) {
  try {
    await ElMessageBox.confirm(`确定删除拓扑「${row.name}」？`, '确认删除', { type: 'warning' })
    await api.delete(`/topology/${row.id}`)
    ElMessage.success('已删除')
    topologies.value = topologies.value.filter(t => t.id !== row.id)
  } catch {}
}

function methodLabel(m) {
  return { lan: '局域网', seed: '种子发现', multivlan: '多VLAN', serial: '串口', scan: '扫描' }[m] || m
}
function methodTag(m) {
  return { lan: 'success', seed: 'primary', multivlan: 'warning', serial: 'info', scan: '' }[m] || ''
}
function formatTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return d.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.topology-list { max-width: 1200px; }

.page-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 800; color: var(--text-color); margin-bottom: 4px; letter-spacing: -0.5px; }
.page-desc { font-size: 14px; color: var(--text-secondary); margin: 0; }
.action-btn {
  background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
  border: none !important; border-radius: var(--radius-sm) !important;
  font-weight: 600; letter-spacing: 0.5px;
}

/* ── Topo Grid ── */
.topo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.topo-card {
  background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--radius-md);
  padding: 20px; cursor: pointer; transition: all 0.2s;
}
.topo-card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); border-color: var(--primary-color); }

.topo-card-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
.topo-card-icon { font-size: 32px; flex-shrink: 0; }
.topo-card-info { flex: 1; min-width: 0; }
.topo-card-name { font-size: 16px; font-weight: 700; color: var(--text-color); margin-bottom: 6px; }
.topo-card-meta { display: flex; align-items: center; gap: 8px; }
.more-btn { color: var(--text-muted); }

.topo-card-stats { display: flex; gap: 24px; padding-top: 16px; border-top: 1px solid var(--border-color); }
.topo-stat { display: flex; flex-direction: column; gap: 2px; }
.topo-stat-value { font-size: 18px; font-weight: 800; color: var(--text-color); }
.topo-stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }

/* ── Empty State ── */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 64px; margin-bottom: 16px; }
.empty-state h3 { font-size: 18px; color: var(--text-color); margin-bottom: 8px; }
.empty-state p { color: var(--text-secondary); margin-bottom: 24px; }

/* ── Loading ── */
.loading-state { text-align: center; padding: 60px; color: var(--text-secondary); }
.loading-icon { animation: spin 1s linear infinite; color: var(--primary-color); }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .page-header { flex-direction: column; align-items: stretch; }
  .action-btn { width: 100%; }
  .topo-grid { grid-template-columns: 1fr; }
  .topo-card-stats { gap: 16px; }
}
</style>
