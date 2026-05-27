<template>
  <div class="topo-detail">
    <div class="detail-header">
      <div class="detail-header-left">
        <el-button text icon="ArrowLeft" @click="$router.push('/topology')">返回</el-button>
        <el-input
          v-if="editingName"
          v-model="editNameValue"
          size="small"
          style="width:160px"
          @keyup.enter="saveName"
          @blur="saveName"
          ref="nameInput"
        />
        <h2 v-else style="display:inline;cursor:pointer;margin:0" @click="startEditName">{{ topology.name }}</h2>
        <el-button v-if="!editingName" text size="small" icon="Edit" @click="startEditName" />
        <span class="meta">{{ nodeList.length }}设备 · {{ linkList.length }}链路</span>
      </div>
      <div class="detail-header-right">
        <el-button size="small" @click="$refs.topoGraph?.fitView()">适配</el-button>
        <el-button size="small" @click="$refs.topoGraph?.restartPhysics()">重排</el-button>
      </div>
    </div>

    <!-- Stats -->
    <el-row :gutter="[6, 6]" style="margin-bottom:12px">
      <el-col :xs="8" :sm="4" v-for="stat in stats" :key="stat.label">
        <el-card shadow="hover" :body-style="{ padding:'8px 12px' }">
          <div style="text-align:center">
            <div style="font-size:22px;font-weight:700;color:var(--primary-color)">{{ stat.value }}</div>
            <div style="font-size:11px;color:#909399">{{ stat.label }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="8" :sm="4">
        <el-card shadow="hover" :body-style="{ padding:'8px 12px' }">
          <div style="text-align:center">
            <div style="font-size:18px;font-weight:700;color:#909399">
              {{ nodeList.filter(n => n.dragging).length ? '拖拽中...' : '就绪' }}
            </div>
            <div style="font-size:10px;color:#909399">画布状态</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Obsidian 风格拓扑图 -->
    <TopologyGraph
      ref="topoGraph"
      :nodes="nodeList"
      :links="linkList"
      @device-click="onDeviceClick"
      style="margin-bottom:16px"
    />

    <!-- Device List (Editable) -->
    <el-card shadow="never" style="margin-top:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>设备清单</span>
          <el-button type="primary" size="small" :loading="savingDevices" @click="saveDevices" :disabled="!devicesChanged">
            保存更改
          </el-button>
        </div>
      </template>
      <el-table :data="nodeList" stripe size="small">
        <el-table-column label="名称" width="160">
          <template #default="{ row }">
            <el-input v-model="row.name" size="small" @change="onDeviceChanged" />
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-select v-model="row.type" size="small" style="width:100%" @change="onDeviceChanged">
              <el-option label="路由器" value="router" />
              <el-option label="交换机" value="switch" />
              <el-option label="防火墙" value="firewall" />
              <el-option label="服务器" value="server" />
              <el-option label="未知" value="unknown" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="150">
          <template #default="{ row }">
            <el-input v-model="row.ip" size="small" @change="onDeviceChanged" />
          </template>
        </el-table-column>
        <el-table-column label="连接方式" width="120">
          <template #default="{ row }">
            <el-select v-model="row.loginMethod" size="small" style="width:100%" @change="onDeviceChanged">
              <el-option label="SSH" value="ssh" />
              <el-option label="Telnet" value="telnet" />
              <el-option label="Console" value="console" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="账户" width="110">
          <template #default="{ row }">
            <el-input v-model="row.username" size="small" @change="onDeviceChanged" />
          </template>
        </el-table-column>
        <el-table-column label="密码" width="130">
          <template #default="{ row }">
            <el-input v-model="row.password" size="small" type="password" show-password @change="onDeviceChanged" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :style="{ color: statusColor(row.status||'unknown'), fontSize:'12px' }">
              {{ row.status === 'online' ? '● 在线' : row.status === 'offline' ? '● 离线' : '● 未知' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Agent Panel -->
    <AgentPanel :topo-id="topology.id" :topo-name="topology.name" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Edit } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '@/stores/auth'
import AgentPanel from '@/components/AgentPanel.vue'
import TopologyGraph from '@/components/TopologyGraph.vue'

const route = useRoute()
const topology = ref({})
const nodeList = ref([])
const linkList = ref([])
const topoGraph = ref(null)

// Name editing
const editingName = ref(false)
const editNameValue = ref('')
const nameInput = ref(null)
const savingDevices = ref(false)
const devicesChanged = ref(false)

function startEditName() {
  editNameValue.value = topology.value.name
  editingName.value = true
  nextTick(() => nameInput.value?.focus())
}

async function saveName() {
  if (!editNameValue.value.trim()) { editingName.value = false; return }
  try {
    await api.put(`/topology/${topology.value.id}`, { name: editNameValue.value.trim() })
    topology.value.name = editNameValue.value.trim()
    ElMessage.success('名称已更新')
  } catch { ElMessage.error('更新失败') }
  editingName.value = false
}

function onDeviceChanged() { devicesChanged.value = true }

async function saveDevices() {
  savingDevices.value = true
  try {
    await api.put(`/topology/${topology.value.id}`, { device_data: nodeList.value })
    devicesChanged.value = false
    ElMessage.success('设备信息已保存')
  } catch { ElMessage.error('保存失败') }
  finally { savingDevices.value = false }
}

onMounted(async () => {
  try {
    const res = await api.get(`/topology/${route.params.id}`)
    topology.value = res.data
    nodeList.value = (res.data.device_data || []).map(d => ({
      ...d,
      status: d.status || 'unknown',
      portCount: d.type === 'router' ? 4 : d.type === 'switch' ? 24 : 2,
    }))
    linkList.value = res.data.link_data || []
    // 数据加载后自动适配
    setTimeout(() => topoGraph.value?.fitView(), 500)
  } catch (e) {
    console.error(e)
  }
})

const stats = computed(() => [
  { label: '设备', value: nodeList.value.length },
  { label: '链路', value: linkList.value.length },
  { label: '路由器', value: nodeList.value.filter(d => d.type === 'router').length },
  { label: '交换机', value: nodeList.value.filter(d => d.type === 'switch').length },
  { label: '在线', value: nodeList.value.filter(d => d.status === 'online').length },
  { label: '离线', value: nodeList.value.filter(d => d.status === 'offline').length },
])

// ── TopologyGraph 事件 ────────────────────────────────────────────
function onDeviceClick(device) {
  // 可扩展：打开设备详情面板或弹窗
  ElMessage.info(`设备: ${device.name} (${device.type || '未知'})`)
}
</script>

<style scoped>
.topo-detail { max-width: 1300px; }
.detail-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px }
.detail-header-left { display:flex; align-items:center; gap:6px; flex-wrap:wrap; min-width:0; }
.detail-header-right { display:flex; gap:6px; flex-shrink:0; }
.detail-header-left h2 { font-size: clamp(14px, 3vw, 22px); max-width: 200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.meta { color: #909399; font-size: 12px; white-space:nowrap; }

/* ── Device table ── */
.topo-detail .el-table__body-wrapper { overflow-x: auto; }

/* ── 移动端 ── */
@media (max-width: 768px) {
  .detail-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }
  .detail-header-right {
    width: 100%;
    justify-content: flex-start;
    gap: 4px;
  }
  .detail-header-right .el-button {
    padding: 4px 8px;
    font-size: 12px;
  }
}
</style>
