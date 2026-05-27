<template>
  <div class="topology-list">
    <div class="page-header">
      <div>
        <h2>网络拓扑</h2>
        <p class="subtitle">管理已发现的网络拓扑结构</p>
      </div>
      <el-button type="primary" size="large" icon="Search" @click="startSniff">
        开始嗅探
      </el-button>
    </div>

    <!-- 已保存的拓扑 -->
    <el-card v-if="topologies.length > 0" shadow="never" style="margin-top:16px">
      <template #header>
        <span>拓扑列表 ({{ topologies.length }})</span>
      </template>
      <el-table :data="topologies" stripe style="width:100%" @row-click="openTopology" row-style="cursor:pointer">
        <el-table-column prop="name" label="名称" min-width="160">
          <template #default="{ row }">
            <span style="font-weight:600">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="嗅探方式" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="methodTag(row.discovery_method)" effect="plain">
              {{ methodLabel(row.discovery_method) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="device_count" label="设备数" width="80" />
        <el-table-column prop="link_count" label="链路数" width="80" />
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <span style="color:#909399;font-size:13px">{{ formatTime(row.updated_at || row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button text size="small" type="primary" icon="View" @click.stop="openTopology(row)">
              查看
            </el-button>
            <el-button text size="small" type="danger" icon="Delete" @click.stop="deleteTopology(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 空状态 -->
    <el-empty
      v-if="topologies.length === 0 && !loading"
      description="暂无拓扑数据，点击上方按钮开始嗅探"
      :image-size="120"
      style="margin-top:40px"
    >
      <el-button type="primary" size="large" icon="Search" @click="startSniff">
        开始第一次嗅探
      </el-button>
    </el-empty>

    <div v-if="loading" style="text-align:center;padding:60px">
      <el-icon :size="40" style="animation: spin 1s linear infinite"><Loading /></el-icon>
      <p style="color:#909399;margin-top:16px">加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, View, Delete, Loading } from '@element-plus/icons-vue'
import { api } from '@/stores/auth'

const router = useRouter()
const topologies = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await api.get('/topology/')
    topologies.value = res.data.topologies || []
  } catch (e) {
    console.error('Failed to load topologies:', e)
  } finally {
    loading.value = false
  }
})

function startSniff() {
  router.push('/topology/wizard')
}

function openTopology(row) {
  router.push(`/topology/${row.id}`)
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
  return { lan: '局域网', multivlan: '多VLAN', serial: '串口' }[m] || m
}
function methodTag(m) {
  return { lan: 'success', multivlan: 'warning', serial: 'info' }[m] || ''
}
function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}
</script>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
.topology-list { max-width: 1200px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.page-header h2 { margin: 0; }
.page-header .el-button { flex-shrink: 0; }
.subtitle { color: #909399; margin: 0; }

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
  .page-header .el-button {
    width: 100%;
  }
  .el-table {
    font-size: 12px;
  }
  .el-table .el-button {
    padding: 0 4px;
    font-size: 12px;
  }
}
</style>
