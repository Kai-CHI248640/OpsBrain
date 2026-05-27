<template>
  <div class="topology-wizard">
    <h2>网络拓扑发现</h2>
    <p class="subtitle">选择发现方式，确认设备列表，生成网络拓扑</p>

    <!-- ═══ Step 指示器 ═══ -->
    <el-steps :active="step" align-center finish-status="success" style="margin: 28px 0 32px">
      <el-step :title="isLocalMode ? '连接本机' : '选择方式'" :description="isLocalMode ? '获取主机信息' : '选择嗅探方式'" />
      <el-step title="设备列表" :description="isLocalMode ? '本机数据' : '确认设备信息'" />
      <el-step :title="isLocalMode ? '系统信息' : '收集数据'" description="Agent 采集" />
      <el-step :title="isLocalMode ? '本机概览' : '拓扑结果'" :description="isLocalMode ? '系统状态' : '生成拓扑图'" />
    </el-steps>

    <!-- ════════════════════════════════════════════════════════════ -->
    <!-- Step 0: 选择嗅探方式 -->
    <!-- ════════════════════════════════════════════════════════════ -->
    <div v-if="step === 0" class="step-content">
      <el-row :gutter="[12, 12]">
        <el-col :xs="24" :sm="8" v-for="method in discoveryMethods" :key="method.id">
          <el-card
            :class="['method-card', { active: selectedMethod === method.id }]"
            shadow="hover"
            @click="selectedMethod = method.id"
          >
            <div class="method-icon">
              <el-icon :size="40"><component :is="method.icon" /></el-icon>
            </div>
            <h3>{{ method.title }}</h3>
            <p>{{ method.desc }}</p>
            <el-tag size="small" :type="method.tagType">{{ method.tag }}</el-tag>
          </el-card>
        </el-col>
      </el-row>

      <!-- 串口服务器配置 -->
      <el-card v-if="selectedMethod === 'serial'" class="serial-config" shadow="never">
        <template #header>串口服务器配置</template>
        <el-form :model="serialConfig" label-width="120px">
          <el-form-item label="串口服务器IP">
            <el-input v-model="serialConfig.ip" placeholder="10.0.0.100" />
          </el-form-item>
          <el-form-item label="端口范围">
            <el-col :span="11">
              <el-input v-model="serialConfig.portStart" placeholder="起始端口" />
            </el-col>
            <el-col :span="2" style="text-align:center">-</el-col>
            <el-col :span="11">
              <el-input v-model="serialConfig.portEnd" placeholder="结束端口" />
            </el-col>
          </el-form-item>
          <el-form-item label="登录方式">
            <el-radio-group v-model="serialConfig.loginMethod">
              <el-radio-button value="ssh">SSH</el-radio-button>
              <el-radio-button value="telnet">Telnet</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="默认账号">
            <el-input v-model="serialConfig.username" placeholder="admin" />
          </el-form-item>
          <el-form-item label="默认密码(选填)">
            <el-input v-model="serialConfig.password" type="password" show-password placeholder="留空则不采集" />
          </el-form-item>
        </el-form>
      </el-card>

      <div style="text-align:center; margin-top: 24px">
        <el-button type="primary" size="large" @click="startDiscovery" :loading="discovering">
          {{ discovering ? '正在发现设备...' : '开始发现设备' }}
        </el-button>
      </div>
    </div>

    <!-- ════════════════════════════════════════════════════════════ -->
    <!-- Step 1: 设备列表（可编辑） -->
    <!-- ════════════════════════════════════════════════════════════ -->
    <div v-if="step === 1" class="step-content">
      <el-alert
        :title="isLocalMode ? `已连接到本机: ${devices[0]?.name || ''}` : `已发现 ${devices.length} 台设备，请确认设备信息后开始收集拓扑数据`"
        :type="isLocalMode ? 'info' : 'success'"
        show-icon :closable="false"
        style="margin-bottom: 16px"
      />

      <!-- 设备列表表格 -->
      <el-table :data="devices" stripe border style="width:100%" max-height="500">
        <el-table-column prop="name" label="设备名称" min-width="140">
          <template #default="{ row }">
            <el-input v-model="row.name" size="small" placeholder="设备名" />
          </template>
        </el-table-column>

        <el-table-column prop="type" label="设备类型" width="120">
          <template #default="{ row }">
            <el-select v-model="row.type" size="small" style="width:100%">
              <el-option label="路由器" value="router" />
              <el-option label="交换机" value="switch" />
              <el-option label="防火墙" value="firewall" />
              <el-option label="服务器" value="server" />
              <el-option label="未知" value="unknown" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column prop="ip" label="IP 地址" width="150">
          <template #default="{ row }">
            <el-input v-model="row.ip" size="small" placeholder="192.168.1.1" />
          </template>
        </el-table-column>

        <el-table-column prop="vendor" label="厂商" width="110">
          <template #default="{ row }">
            <el-select v-model="row.vendor" size="small" style="width:100%">
              <el-option label="Cisco" value="cisco" />
              <el-option label="华为" value="huawei" />
              <el-option label="H3C" value="h3c" />
              <el-option label="Juniper" value="juniper" />
              <el-option label="锐捷" value="ruijie" />
              <el-option label="其他" value="other" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="登录方式" width="170">
          <template #default="{ row }">
            <div style="display:flex; gap:4px; flex-wrap:wrap">
              <el-select v-model="row.loginMethod" size="small" style="width:70px">
                <el-option label="SSH" value="ssh" />
                <el-option label="Telnet" value="telnet" />
                <el-option label="Console" value="console" />
              </el-select>
              <el-input v-model="row.username" size="small" placeholder="账号" style="width:80px" />
            </div>
          </template>
        </el-table-column>

        <el-table-column label="密码(选填)" width="130">
          <template #default="{ row }">
            <el-input v-model="row.password" size="small" type="password" show-password placeholder="选填，留空则不采集" />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row, $index }">
            <el-button text size="small" type="danger" icon="Delete" @click="removeDevice($index)" />
          </template>
        </el-table-column>
      </el-table>

      <!-- 添加设备（非本机模式才显示） -->
      <div v-if="!isLocalMode" style="margin-top:16px; display:flex; gap:12px">
        <el-button icon="Plus" @click="addDevice">添加设备</el-button>
        <el-button icon="Upload" @click="importFromExcel">从 Excel 导入</el-button>
      </div>

      <!-- 设备概要（本机模式显示系统信息） -->
      <el-card shadow="never" style="margin-top:16px">
        <template #header>{{ isLocalMode ? '本机系统信息' : '设备概要' }}</template>
        <div v-if="isLocalMode" style="font-size:13px;line-height:2">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="主机名">{{ localSystem?.hostname || '—' }}</el-descriptions-item>
            <el-descriptions-item label="OS">{{ localSystem?.os || '—' }}</el-descriptions-item>
            <el-descriptions-item label="CPU">{{ localSystem?.cpu?.model?.substring(0,30) || '—' }}</el-descriptions-item>
            <el-descriptions-item label="核心数">{{ localSystem?.cpu?.cores || '—' }} 核</el-descriptions-item>
            <el-descriptions-item label="总内存">{{ localSystem?.memory?.total_mb || '—' }} MB</el-descriptions-item>
            <el-descriptions-item label="已用">{{ localSystem?.memory?.used_mb || '—' }} MB ({{ localSystem?.memory?.pct || 0 }}%)</el-descriptions-item>
            <el-descriptions-item label="磁盘总量">{{ localSystem?.disk?.total_gb || '—' }} GB</el-descriptions-item>
            <el-descriptions-item label="可用">{{ localSystem?.disk?.free_gb || '—' }} GB</el-descriptions-item>
            <el-descriptions-item label="IP" :span="2">{{ (localSystem?.network?.ips || []).join(', ') || '—' }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <el-row v-else :gutter="[8, 8]">
          <el-col :xs="12" :sm="6">
            <div class="summary-item">
              <span class="summary-label">总计</span>
              <span class="summary-value">{{ devices.length }}</span>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="summary-item">
              <span class="summary-label">路由器</span>
              <span class="summary-value" style="color:#E6A23C">{{ typeCount('router') }}</span>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="summary-item">
              <span class="summary-label">交换机</span>
              <span class="summary-value" style="color:#409EFF">{{ typeCount('switch') }}</span>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="summary-item">
              <span class="summary-label">其他</span>
              <span class="summary-value" style="color:#67C23A">{{ typeCountOthers() }}</span>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <div style="text-align:center; margin-top:24px">
        <el-button size="large" @click="step = 0">← 返回</el-button>
        <el-button type="primary" size="large" @click="startCollection" :loading="collecting">
          {{ collecting ? 'Agent 正在采集...' : '确认并开始收集拓扑数据' }}
        </el-button>
      </div>
    </div>

    <!-- ════════════════════════════════════════════════════════════ -->
    <!-- Step 2: 收集数据（进度） -->
    <!-- ════════════════════════════════════════════════════════════ -->
    <div v-if="step === 2" class="step-content">
      <el-card shadow="never">
        <template #header>{{ isLocalMode ? '采集本机系统信息' : 'Agent 正在连接设备' }}</template>

        <div style="padding: 20px">
          <el-progress
            :percentage="collectProgress.percent"
            :status="collectProgress.status"
            :stroke-width="20"
            :text-inside="true"
          />

          <el-table :data="collectProgress.logs" stripe style="margin-top:20px" max-height="400">
            <el-table-column prop="device" label="采集项" width="140" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
                  {{ row.status === 'success' ? '✓ 完成' : row.status === 'failed' ? '✗ 失败' : '○ 等待' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="info" label="信息" min-width="200" />
          </el-table>
        </div>
      </el-card>
    </div>

    <!-- ════════════════════════════════════════════════════════════ -->
    <!-- Step 3: 拓扑结果 -->
    <!-- ════════════════════════════════════════════════════════════ -->
    <div v-if="step === 3" class="step-content">
      <el-row :gutter="[8, 8]" style="margin-bottom: 16px">
        <el-col :xs="12" :sm="6" v-for="stat in topologyStats" :key="stat.label">
          <el-card shadow="hover" :body-style="{ padding: '16px' }">
            <div style="text-align:center">
              <div style="font-size:28px; font-weight:700; color:var(--primary-color)">{{ stat.value }}</div>
              <div style="font-size:13px; color:#909399; margin-top:4px">{{ stat.label }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 拓扑分析 -->
      <el-card v-if="topologyInsight && !isLocalMode" shadow="never" style="margin-bottom: 16px">
        <template #header>
          <span>拓扑分析</span>
          <el-tag v-if="topologyInsight.type" style="margin-left:8px" size="small" effect="plain">
            {{ topologyInsight.type }}
          </el-tag>
        </template>
        <p style="color:#606266; line-height:1.8">{{ topologyInsight.description }}</p>
      </el-card>

      <!-- 链路列表（仅网络模式） -->
      <el-card v-if="!isLocalMode" shadow="never" style="margin-bottom: 16px">
        <template #header>设备链路</template>
        <el-table :data="topologyLinks" stripe style="width:100%">
          <el-table-column prop="source" label="源设备" width="150" />
          <el-table-column prop="sourcePort" label="源端口" width="100" />
          <el-table-column label="" width="50">
            <template #default><el-icon><Right /></el-icon></template>
          </el-table-column>
          <el-table-column prop="target" label="目标设备" width="150" />
          <el-table-column prop="targetPort" label="目标端口" width="100" />
          <el-table-column prop="speed" label="速率" width="80" />
          <el-table-column label="确认" width="80">
            <template #default="{ row }">
              <el-tag :type="row.confirmed ? 'success' : 'warning'" size="small">
                {{ row.confirmed ? '双向' : '单向' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 拓扑图（种子/嗅探模式） -->
      <el-card shadow="never" v-if="topologyLinks.length > 0" style="margin-bottom:16px">
        <template #header>拓扑图 <span style="font-weight:400;color:#909399;font-size:12px">点击节点查看详情 · 拖拽调整 · 滚轮缩放</span></template>
        <TopologyGraph
          :nodes="devices"
          :links="topologyLinks"
          @device-click="onTopoNodeClick"
          style="height:450px"
        />
      </el-card>

      <div style="text-align:center; margin-top:24px">
        <el-button size="large" @click="showSaveDialog = true" type="primary">保存拓扑</el-button>
        <el-button size="large" @click="resetWizard">取消</el-button>
      </div>

      <!-- Save Dialog -->
      <el-dialog v-model="showSaveDialog" title="保存拓扑" width="400px">
        <el-form label-width="80px">
          <el-form-item label="拓扑名称">
            <el-input v-model="saveName" :placeholder="autoName" />
          </el-form-item>
          <div style="color:#909399;font-size:12px">
            留空则自动命名为「{{ autoName }}」
          </div>
        </el-form>
        <template #footer>
          <el-button @click="showSaveDialog = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveTopology">
            {{ saving ? '保存中...' : '确认保存' }}
          </el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor, Connection, Search, Right, Setting } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { api } from '@/stores/auth'
import TopologyGraph from '@/components/TopologyGraph.vue'

const router = useRouter()
const step = ref(0)
const selectedMethod = ref('lan')
const isLocalMode = computed(() => selectedMethod.value === 'local')
const localSystem = ref(null)
const discovering = ref(false)
const collecting = ref(false)

// ── Discovery methods ──────────────────────────────────────────────
const discoveryMethods = [
  {
    id: 'seed',
    title: '种子发现',
    desc: '从一台已知交换机出发，SSH 登录后通过 LLDP/CDP 递归发现全拓扑',
    icon: Connection,
    tag: '最准确',
    tagType: 'success',
  },
  {
    id: 'lan',
    title: '局域网嗅探',
    desc: '自动扫描本机所在网段的所有 IP，探测开放端口',
    icon: Monitor,
    tag: '快速摸底',
    tagType: 'warning',
  },
  {
    id: 'serial',
    title: '串口服务器连接',
    desc: '通过串口服务器 (Console Server) 的带外管理链路接入设备',
    icon: Search,
    tag: '带外管理',
    tagType: 'info',
  },
  {
    id: 'local',
    title: '本机 (Local)',
    desc: '将 OpsBrain 部署主机自身加入拓扑',
    icon: Setting,
    tag: 'OpsBrain',
    tagType: 'primary',
  },
]

// ── Serial config ──────────────────────────────────────────────────
const serialConfig = reactive({
  ip: '',
  portStart: '2001',
  portEnd: '2048',
  loginMethod: 'ssh',
  username: 'admin',
  password: '',
})

// ── Devices ────────────────────────────────────────────────────────
const devices = ref([])

function addDevice() {
  devices.value.push({
    name: `Device-${devices.value.length + 1}`,
    type: 'unknown',
    ip: '',
    vendor: 'other',
    loginMethod: 'ssh',
    username: 'admin',
    password: '',
  })
}

function removeDevice(index) {
  devices.value.splice(index, 1)
}

function importFromExcel() {
  ElMessage.info('Excel 导入功能开发中，请使用上方按钮手动添加设备')
}

function typeCount(type) {
  return devices.value.filter(d => d.type === type).length
}

function typeCountOthers() {
  return devices.value.filter(d => !['router', 'switch'].includes(d.type)).length
}

// ── Discovery Simulation ───────────────────────────────────────────
function startDiscovery() {
  if (selectedMethod.value === 'serial' && !serialConfig.ip) {
    ElMessage.warning('请输入串口服务器 IP')
    return
  }

  discovering.value = true

  // 本机模式：从后端获取真实的主机信息
  if (selectedMethod.value === 'local') {
    api.get('/dashboard/local-info').then(res => {
      const d = res.data
      localSystem.value = d  // 保存供后续步骤使用
      devices.value = [{
        name: `OpsBrain-Local (${d.hostname})`,
        type: 'server',
        ip: d.network?.ips?.[0] || '127.0.0.1',
        vendor: 'local',
        loginMethod: 'ssh',
        username: '', password: '',
        local: true,
      }]
      discovering.value = false
      step.value = 1
    }).catch(() => {
      devices.value = [{
        name: 'OpsBrain-Local', type: 'server', ip: '127.0.0.1',
        vendor: 'local', loginMethod: 'ssh', username: '', password: '', local: true,
      }]
      discovering.value = false
      step.value = 1
    })
    return
  }

  // ── 种子发现：调后端 API ──
  if (selectedMethod.value === 'seed') {
    const seedDevices = []
    // Prompt user to add at least one seed device
    seedDevices.push({ ip: '', name: '', username: 'admin', password: '', vendor: 'cisco' })
    
    devices.value = seedDevices
    discovering.value = false
    step.value = 1
    ElMessage.info('请输入至少一台种子设备的 IP 和凭证')
    return
  }

  // ── 局域网嗅探 ──
  if (selectedMethod.value === 'lan') {
    api.post('/topology/discover', {
      method: 'lan', username: 'admin', password: '',
    }).then(res => {
      const data = res.data
      if (!data.ok) { ElMessage.error(data.error || '嗅探失败'); discovering.value = false; return }
      devices.value = (data.devices || []).map(d => ({
        name: d.name, type: d.type || 'unknown', ip: d.ip || '',
        vendor: d.vendor === '?' ? 'other' : (d.vendor || 'other'),
        loginMethod: d.loginMethod || 'ssh', username: 'admin', password: '',
      }))
      discovering.value = false
      step.value = 1
      ElMessage.success(`发现 ${data.device_count} 台设备`)
    }).catch(e => {
      ElMessage.error('嗅探失败: ' + (e.response?.data?.error || e.message))
      discovering.value = false
    })
    return
  }

  // ── 串口服务器 ──
  const portStart = parseInt(serialConfig.portStart) || 2001
  const portEnd = parseInt(serialConfig.portEnd) || 2048
  discovered = []
  for (let port = portStart; port <= portEnd; port++) {
    const name = `Console-Dev-${port}`
    discovered.push({
      name, type: 'unknown', ip: serialConfig.ip || '',
      vendor: 'other', loginMethod: 'console',
      username: serialConfig.username, password: serialConfig.password,
      consolePort: port,
    })
  }
  devices.value = discovered
  discovering.value = false
  step.value = 1
  ElMessage.success(`已添加 ${discovered.length} 个串口端口`)
}

// ── Collection Progress ───────────────────────────────────────────
const collectProgress = reactive({
  percent: 0,
  status: '',
  logs: [],
})

function startCollection() {
  if (devices.value.length === 0) {
    ElMessage.warning('设备列表为空')
    return
  }

  step.value = 2
  collecting.value = true
  collectProgress.percent = 0
  collectProgress.status = ''

  // ── 种子发现：调后端 API ──
  if (selectedMethod.value === 'seed') {
    const seeds = devices.value.filter(d => d.ip && d.username)
    if (seeds.length === 0) {
      ElMessage.warning('至少需要一台有 IP 和凭证的种子设备')
      collecting.value = false
      return
    }

    collectProgress.logs = [
      { device: '种子发现引擎', status: 'collecting', info: '正在连接种子设备…' },
    ]

    api.post('/topology/discover-seed', {
      seeds: seeds.map(d => ({
        ip: d.ip, name: d.name,
        username: d.username, password: d.password || '',
        vendor: d.vendor === 'other' ? 'cisco' : (d.vendor || 'cisco'),
      })),
      max_devices: 50,
      max_depth: 5,
    }).then(res => {
      const data = res.data
      if (!data.ok) {
        collectProgress.logs[0] = { device: '种子发现引擎', status: 'failed', info: data.error || '失败' }
        collectProgress.status = 'exception'
        collectProgress.percent = 100
        collecting.value = false
        ElMessage.error(data.error || '种子发现失败')
        return
      }
      collectProgress.logs[0] = { device: '种子发现引擎', status: 'success', info: `发现 ${data.device_count} 台设备` }
      collectProgress.percent = 100
      collectProgress.status = 'success'
      collecting.value = false

      // 将发现结果更新到设备列表和拓扑
      topologyLinks.value = (data.links || []).map(l => ({
        source: l.source, sourcePort: l.source_port,
        target: l.target, targetPort: l.target_port,
        confirmed: l.confirmed,
      }))
      topologyStats.value = [
        { label: '设备总数', value: data.device_count || 0 },
        { label: '确认链路', value: data.confirmed_links || 0 },
        { label: '未确认链路', value: data.unconfirmed_links || 0 },
        { label: '种子数量', value: seeds.length },
      ]
      mermaidCode.value = data.mermaid_code || ''

      setTimeout(() => { step.value = 3 }, 500)
    }).catch(e => {
      collectProgress.logs[0] = { device: '种子发现引擎', status: 'failed', info: e.message }
      collectProgress.status = 'exception'
      collectProgress.percent = 100
      collecting.value = false
      ElMessage.error('种子发现失败: ' + e.message)
    })
    return
  }

  // ── 非种子模式：模拟进度（后续替换为真实采集） ──
  if (selectedMethod.value === 'local') {
    collectProgress.logs = [
      { device: 'CPU 信息', status: 'pending', info: '读取 /proc/cpuinfo…' },
      { device: '内存信息', status: 'pending', info: '读取 /proc/meminfo…' },
      { device: '磁盘信息', status: 'pending', info: '读取磁盘用量…' },
      { device: '网络信息', status: 'pending', info: '获取 IP 和主机名…' },
    ]
  } else {
    collectProgress.logs = devices.value.map(d => ({ device: d.name, status: 'pending', info: '等待连接' }))
  }

  let i = 0
  const total = collectProgress.logs.length
  const interval = setInterval(() => {
    if (i >= total) {
      clearInterval(interval)
      collecting.value = false
      collectProgress.percent = 100
      collectProgress.status = 'success'
      generateTopology()
      return
    }
    collectProgress.logs[i].status = 'collecting'
    collectProgress.logs[i].info = '采集中…'
    setTimeout(() => {
      collectProgress.logs[i].status = 'success'
      collectProgress.logs[i].info = '完成'
      collectProgress.percent = Math.round(((i + 1) / total) * 100)
      i++
    }, 500)
  }, 200)
}

// ── Topology ───────────────────────────────────────────────────────
const topologyLinks = ref([])
const topologyInsight = ref(null)
const topologyStats = ref([
  { label: '设备总数', value: 0 },
  { label: '确认链路', value: 0 },
  { label: '未确认链路', value: 0 },
  { label: '网关设备', value: 0 },
])
const mermaidCode = ref('')

function generateTopology() {
  // 本机模式：不生成拓扑图，显示系统概览
  if (selectedMethod.value === 'local') {
    const info = localSystem.value || {}
    topologyLinks.value = []
    topologyInsight.value = { type: '本机 (Local)', description: `OpsBrain 部署主机。CPU: ${info.cpu?.cores || '?'} 核，内存: ${info.memory?.total_mb || '?'} MB，磁盘: ${info.disk?.total_gb || '?'} GB。` }
    topologyStats.value = [
      { label: 'CPU 核心', value: info.cpu?.cores || '—' },
      { label: '内存 (MB)', value: info.memory?.total_mb || '—' },
      { label: '已用内存', value: `${info.memory?.pct || 0}%` },
      { label: '磁盘 (GB)', value: info.disk?.total_gb || '—' },
    ]
    mermaidCode.value = ''
    setTimeout(() => { step.value = 3 }, 500)
    return
  }

  const routers = devices.value.filter(d => d.type === 'router' && !d.local)
  const switches = devices.value.filter(d => d.type === 'switch' && !d.local)
  const servers = devices.value.filter(d => d.type === 'server' && !d.local)
  const others = devices.value.filter(d => !['router', 'switch', 'server'].includes(d.type) && !d.local)
  const localDevs = devices.value.filter(d => d.local === true)

  let insight = { type: '', description: '' }
  let links = []
  let mermaid = ['graph TB']

  // ── Local 设备连接逻辑 ──
  function addLocalDevice(coreDevice) {
    localDevs.forEach((loc, i) => {
      links.push({
        source: coreDevice.name, sourcePort: `GE0/0/${99 + i}`,
        target: loc.name, targetPort: 'mgmt',
        speed: '1G', confirmed: true,
      })
      mermaid.push(`  ${escapeMd(coreDevice.name)} ==>|管理口| ${escapeMd(loc.name)}`)
      mermaid.push(`  style ${escapeMd(loc.name)} fill:#e6f7ff,stroke:#409eff,stroke-width:2px`)
    })
  }

  if (routers.length === 1) {
    // ═══ 局域网模式：单网关 ═══
    const gw = routers[0]
    insight = {
      type: '局域网（单网关）',
      description: `以 ${gw.name}(${gw.ip || '?'}) 为网关的局域网。` +
        `${switches.length} 台交换机 + ${servers.length} 台服务器 + ${others.length} 台其它设备。` +
        `${localDevs.length ? ` OpsBrain 部署在 ${localDevs[0].name}(${localDevs[0].ip || '?'})。` : ''}`
    }

    // 路由器 ↔ 交换机 ↔ 服务器
    switches.forEach((sw, i) => {
      links.push({
        source: gw.name, sourcePort: `GE0/0/${i}`,
        target: sw.name, targetPort: `gi0/1`,
        speed: '1G', confirmed: true,
      })
      mermaid.push(`  ${escapeMd(gw.name)} -->|GE0/0/${i}| ${escapeMd(sw.name)}`)
    })

    const lastSw = switches.length > 0 ? switches[switches.length - 1] : gw
    servers.forEach((srv, i) => {
      links.push({
        source: lastSw.name, sourcePort: `gi0/${i + 2}`,
        target: srv.name, targetPort: 'eth0',
        speed: '1G', confirmed: true,
      })
      mermaid.push(`  ${escapeMd(lastSw.name)} -.-> ${escapeMd(srv.name)}`)
    })

    others.forEach((o, i) => {
      const sw = switches[i % switches.length] || gw
      links.push({
        source: sw.name, sourcePort: `gi0/${i + 1}`,
        target: o.name, targetPort: '?',
        speed: '100M', confirmed: false,
      })
      mermaid.push(`  ${escapeMd(sw.name)} -.-> ${escapeMd(o.name)}`)
    })

    // Local 设备连到网关路由器
    addLocalDevice(gw)

  } else if (routers.length > 1) {
    // ═══ 多 VLAN 模式：核心-分支路由 ═══
    const core = routers[0]
    const edges = routers.slice(1)
    insight = {
      type: '多 VLAN 网络',
      description: `${routers.length} 台路由器跨 ${routers.length - 1} 个 VLAN 互联。` +
        `${core.name}(${core.ip || '?'}) 为核心路由，各 VLAN 通过路由器互通。` +
        `${switches.length} 台交换机 + ${servers.length} 台服务器。` +
        `${localDevs.length ? ` OpsBrain 部署在 ${localDevs[0].name}(${localDevs[0].ip || '?'})，连接到核心路由。` : ''}`
    }

    // 路由间链路：核心 ↔ 分支
    edges.forEach((r, i) => {
      links.push({
        source: core.name, sourcePort: `GE0/0/${i}`,
        target: r.name, targetPort: `GE0/0/0`,
        speed: '10G', confirmed: false,
      })
      mermaid.push(`  ${escapeMd(core.name)} -->|GE0/0/${i} (跨VLAN)| ${escapeMd(r.name)}`)
    })

    // 交换机分配到各路由器下
    switches.forEach((sw, i) => {
      const parent = i < Math.ceil(switches.length / 2) ? core : (edges[0] || core)
      links.push({
        source: parent.name, sourcePort: `GE0/1/${i}`,
        target: sw.name, targetPort: 'gi0/1',
        speed: '1G', confirmed: true,
      })
      mermaid.push(`  ${escapeMd(parent.name)} -->|GE0/1/${i}| ${escapeMd(sw.name)}`)
    })

    servers.forEach((srv, i) => {
      const sw = switches[i % switches.length]
      if (sw) {
        links.push({
          source: sw.name, sourcePort: `gi0/${i + 2}`,
          target: srv.name, targetPort: 'eth0',
          speed: '1G', confirmed: true,
        })
        mermaid.push(`  ${escapeMd(sw.name)} -.-> ${escapeMd(srv.name)}`)
      }
    })

    // Local 设备连到核心路由
    addLocalDevice(core)

  } else {
    // ═══ 纯 L2 网络 ═══
    insight = {
      type: '二层网络',
      description: '无路由器设备。纯二层交换网络，所有设备通过交换机互联。无法确定出口网关。'
    }
    switches.forEach((sw, i) => {
      if (i > 0) {
        links.push({
          source: switches[0].name, sourcePort: `gi1/0/${i}`,
          target: sw.name, targetPort: 'gi0/1',
          speed: '1G', confirmed: false,
        })
        mermaid.push(`  ${escapeMd(switches[0].name)} --> ${escapeMd(sw.name)}`)
      }
    })
    if (switches.length > 0) addLocalDevice(switches[0])
  }

  topologyLinks.value = links
  topologyInsight.value = insight
  topologyStats.value = [
    { label: '设备总数', value: devices.value.length },
    { label: '确认链路', value: links.filter(l => l.confirmed).length },
    { label: '未确认链路', value: links.filter(l => !l.confirmed).length },
    { label: '网关设备', value: routers.length },
  ]
  mermaidCode.value = mermaid.join('\n')

  setTimeout(() => { step.value = 3 }, 1000)
}

function escapeMd(name) {
  return name.replace(/[^a-zA-Z0-9\u4e00-\u9fff\-_]/g, '_')
}

function onTopoNodeClick(device) {
  ElMessage.info(`${device.name} (${device.type || '未知'}) - ${device.ip || '无IP'}`)
}

function resetWizard() {
  step.value = 0
  selectedMethod.value = 'lan'
  devices.value = []
  topologyLinks.value = []
  topologyInsight.value = null
  mermaidCode.value = ''
  showSaveDialog.value = false
  saveName.value = ''
}

// ── Save Topology ───────────────────────────────────────────────
const showSaveDialog = ref(false)
const saveName = ref('')
const saving = ref(false)
const autoName = computed(() => {
  const count = topologyLinks.value.length
  return `Topology${count > 0 ? '-' + new Date().toLocaleDateString('zh-CN') : ''}`
})

async function saveTopology() {
  saving.value = true
  try {
    await api.post('/topology/', {
      name: saveName.value || autoName.value,
      discovery_method: selectedMethod.value,
      device_count: devices.value.length,
      link_count: topologyLinks.value.filter(l => l.confirmed).length,
      device_data: devices.value,
      link_data: topologyLinks.value,
      analysis: topologyInsight.value?.description || '',
      mermaid_code: mermaidCode.value,
    })
    ElMessage.success('拓扑已保存')
    showSaveDialog.value = false
    router.push('/topology')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// Override the router guard on this page to actually load
import { onMounted } from 'vue'
onMounted(() => {
  // Reset to step 0 on mount
  resetWizard()
})
</script>

<style scoped>
.topology-wizard {
  max-width: 1200px;
}
.subtitle {
  color: #909399;
  margin: 0 0 8px;
}

/* ── 移动端步骤条 ── */
@media (max-width: 768px) {
  .topology-wizard h2 { font-size: 18px; }
  .topology-wizard > p { font-size: 12px; margin-bottom: 12px; }

  .topology-wizard .el-steps {
    margin: 16px 0 20px !important;
    overflow-x: auto;
    padding: 4px 0;
    -webkit-overflow-scrolling: touch;
  }
  .topology-wizard .el-step {
    flex-shrink: 0;
    min-width: 80px;
  }
  .topology-wizard .el-step__title {
    font-size: 11px;
  }
  .topology-wizard .el-step__description {
    display: none;
  }

  /* 方法卡片 */
  .method-card {
    padding: 12px 10px;
  }
  .method-card h3 { font-size: 14px; margin: 0 0 4px; }
  .method-card p { font-size: 11px; margin-bottom: 4px; }
  .method-icon { margin-bottom: 8px; }
  .method-icon .el-icon { font-size: 28px !important; }

  /* 串口配置 */
  .serial-config { margin-top: 16px; }
  .serial-config .el-form-item { margin-bottom: 10px; }
  .serial-config .el-form-item__label { font-size: 12px; }

  /* 设备表 */
  .step-content .el-table { font-size: 11px; overflow-x: auto; }
  .step-content .el-table td,
  .step-content .el-table th { padding: 4px 2px; }
  .step-content .el-table .el-input__inner,
  .step-content .el-table .el-select .el-input__inner { font-size: 11px; padding: 0 4px; height: 28px; }

  /* 概要 */
  .summary-item { padding: 4px; }
  .summary-value { font-size: 16px; }
  .summary-label { font-size: 10px; }

  /* 采集进度 */
  .el-progress-bar__outer { height: 16px !important; }

  /* 拓扑统计 */
  .el-card .el-card__body { padding: 10px !important; }

  /* 链路表 */
  .el-table .el-table__cell { padding: 2px 0; }

  /* 操作按钮 */
  .step-content > div:last-child {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
  }
  .step-content > div:last-child .el-button {
    flex: 1;
    min-width: 120px;
  }
}

@media (min-width: 769px) and (max-width: 1024px) {
  .method-card h3 { font-size: 15px; }
  .method-card p { font-size: 12px; }
  .summary-value { font-size: 18px; }
}

/* ── Method cards ── */
.method-card {
  cursor: pointer;
  text-align: center;
  padding: 20px 0;
  border: 2px solid transparent;
  transition: all 0.2s;
}
.method-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
}
.method-card.active {
  border-color: var(--primary-color);
  background: var(--primary-color)0f;
}
.method-icon {
  margin-bottom: 12px;
  color: var(--primary-color);
}
.method-card h3 {
  margin: 0 0 8px;
  font-size: 16px;
}
.method-card p {
  color: #909399;
  font-size: 13px;
  margin: 0 0 8px;
}

/* ── Serial config ── */
.serial-config {
  margin-top: 24px;
  background: var(--card-bg);
}

/* ── Summary ── */
.summary-item {
  text-align: center;
  padding: 8px;
}
.summary-label {
  font-size: 12px;
  color: #909399;
  display: block;
}
.summary-value {
  font-size: 20px;
  font-weight: 700;
}

/* ── Mermaid ── */
.mermaid-output {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.8;
}
</style>
