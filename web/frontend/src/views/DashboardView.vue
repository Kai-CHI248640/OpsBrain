<template>
  <div class="dashboard">
    <h2>控制台</h2>
    <p style="color: #666; margin-bottom: 24px;">OpsBrain 企业网络运维平台概览</p>

    <!-- ── 统计卡片 ── -->
    <el-row :gutter="[8, 8]" style="margin-bottom: 24px">
      <el-col :xs="12" :sm="12" :md="6" v-for="card in statCards" :key="card.title">
        <el-card shadow="hover" :class="{ 'card-clickable': card.clickable }"
                 @click="card.clickable && card.click()">
          <div class="stat-card">
            <div class="stat-icon" :style="{ background: card.color + '20', color: card.color }">
              <el-icon :size="24"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="{ 'has-warn': card.warn }">{{ card.value }}</div>
              <div class="stat-label">{{ card.title }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- ── 左侧：Subagent 监控面板 ── -->
      <el-col :xs="24" :md="12" style="display:flex; flex-direction:column; gap:12px">
        <!-- Subagent 列表 -->
        <el-card>
          <template #header>
            <div class="section-header">
              <span><el-icon style="margin-right:6px"><Cpu /></el-icon>Subagent 监控</span>
              <el-tag size="small" type="info">{{ subagents.length }} 个活动</el-tag>
            </div>
          </template>
          <div v-if="subagents.length === 0" style="text-align:center;padding:24px;color:#999">
            暂无 Subagent，创建拓扑后自动生成
          </div>
          <div v-else class="subagent-list">
            <div v-for="sa in subagents" :key="sa.id" class="subagent-item"
                 @click="dispatching = sa; dispatchTask = ''">
              <div class="sa-left">
                <span class="sa-icon">🤖</span>
                <div>
                  <div class="sa-name">{{ sa.name }}</div>
                  <div class="sa-topo">{{ sa.topo_name || '—' }}</div>
                </div>
              </div>
              <div class="sa-right">
                <el-tag :type="sa.status === 'working' ? 'warning' : 'info'" size="small" effect="plain">
                  {{ sa.status === 'working' ? '⚡ 执行中' : '待机' }}
                </el-tag>
                <span class="sa-msgs">{{ sa.message_count || 0 }} 次对话</span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 派发任务面板 -->
        <el-card v-if="dispatching" class="dispatch-card">
          <template #header>
            <div class="section-header">
              <span>📋 派发任务 → {{ dispatching.name }}</span>
              <el-button text size="small" @click="dispatching = null">✕</el-button>
            </div>
          </template>
          <el-input v-model="dispatchTask" type="textarea" :rows="3"
                    placeholder="描述要派发的任务，例如：SSH 到 R1 检查端口状态" />
          <el-button type="primary" size="small" style="margin-top:8px;width:100%"
                     :loading="dispatchingLoading" @click="doDispatch">
            🚀 派发任务
          </el-button>
          <div v-if="dispatchResult" class="dispatch-result" v-html="renderMd(dispatchResult)" />
        </el-card>
      </el-col>

      <!-- ── 右侧：总控 Agent + 系统信息 ── -->
      <el-col :xs="24" :md="12" style="margin-bottom:16px">
        <!-- 总控 Agent -->
        <el-card class="commander-card">
          <template #header>
            <div class="commander-header">
              <span>
                <el-icon style="margin-right:6px;vertical-align:middle"><Cpu /></el-icon>
                总控 Agent
              </span>
              <div class="commander-tags">
                <el-tag size="small" type="primary" effect="plain">规划</el-tag>
                <el-tag size="small" type="warning" effect="plain">指挥</el-tag>
                <el-tag size="small" type="success" effect="plain">监控</el-tag>
                <el-button text size="small" type="danger" icon="Delete" @click="resetCommander" style="margin-left:8px">重置</el-button>
              </div>
            </div>
          </template>

          <div class="commander-chat" ref="chatRef">
            <div v-if="commanderMessages.length === 0" class="chat-empty">
              <p>🤖 Commander 已就绪</p>
              <p style="font-size:12px;color:#909399">
                直接告诉我要做什么：<br>
                「检查全网设备状态」「部署 VLAN 配置」<br>
                「有哪些故障」「给我巡检报告」
              </p>
            </div>
            <div v-for="(msg, i) in commanderMessages" :key="i" :class="['chat-msg', msg.role]">
              <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
              <div class="msg-bubble-wrap">
                <div class="msg-bubble">
                  <div v-html="renderMd(msg.content)" />
                  <div v-if="msg.report" class="subagent-report" @click="msg.showReport = !msg.showReport">
                    <span>{{ msg.showReport ? '🔽' : '▶' }} Subagent 内部汇报</span>
                    <div v-if="msg.showReport" class="report-content" v-html="renderMd(msg.report)" />
                  </div>
                </div>
                <el-button class="msg-delete" text size="small" type="danger" icon="Delete" @click="deleteMsg(i)" />
              </div>
            </div>
            <div v-if="commanderLoading" class="chat-msg assistant">
              <div class="msg-avatar">🤖</div>
              <div class="msg-bubble loading-bubble">
                {{ loadingText }}<span class="dot-pulse"></span>
              </div>
            </div>
          </div>
          <div class="commander-input">
            <el-input v-model="commanderInput" placeholder="规划方案 / 指挥 Subagent / 查询状态…"
                      size="small" :disabled="commanderLoading"
                      @keyup.enter="sendCommander">
              <template #append>
                <el-button v-if="!commanderLoading" icon="Promotion" @click="sendCommander" :disabled="!commanderInput.trim()" />
                <el-button v-else type="danger" icon="Close" @click="cancelCommander">停止</el-button>
              </template>
            </el-input>
          </div>
        </el-card>

        <!-- 本机 + 系统信息 -->
        <el-card style="margin-top:16px">
          <template #header><span>本机 · OpsBrain 部署主机</span></template>
          <div v-if="localInfo.hostname" class="local-info">
            <div class="local-row">
              <span class="local-label">主机名</span>
              <span class="local-val">{{ localInfo.hostname }}</span>
            </div>
            <div class="local-row">
              <span class="local-label">CPU</span>
              <span class="local-val">{{ localInfo.cpu?.model?.substring(0,35) || '—' }}</span>
            </div>
            <div class="local-row">
              <span class="local-label">内存</span>
              <el-progress :percentage="localInfo.memory?.pct || 0" :stroke-width="6"
                :color="(localInfo.memory?.pct || 0) > 80 ? '#f56c6c' : '#67c23a'" />
              <span class="local-val-sm">{{ localInfo.memory?.used_mb || 0 }}M / {{ localInfo.memory?.total_mb || 0 }}M</span>
            </div>
            <div class="local-row">
              <span class="local-label">磁盘</span>
              <span class="local-val-sm">{{ localInfo.disk?.free_gb || 0 }}G 可用 / {{ localInfo.disk?.total_gb || 0 }}G 总计</span>
            </div>
            <div class="local-row" style="margin-top:8px">
              <span class="local-label">IP</span>
              <code style="font-size:11px">{{ (localInfo.network?.ips || []).slice(0,3).join(', ') || '—' }}</code>
            </div>
          </div>
          <div v-else style="text-align:center;padding:12px;color:#909399;font-size:12px">
            本机信息加载中...
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Connection, Warning, Aim, ChatDotRound, Cpu, Promotion, Close, Delete } from '@element-plus/icons-vue'
import { api } from '@/stores/auth'

const router = useRouter()
const chatRef = ref(null)

// ── 统计 ──
const stats = reactive({ topology_count: 0, faulty_devices: 0, api_status: {}, subagent_tasks: {} })
const apiHealthy = ref(true)

const statCards = computed(() => [
  { title: '拓扑数量', value: stats.topology_count ?? '--', icon: Connection, color: '#409EFF',
    clickable: true, click: () => router.push('/topology') },
  { title: '故障设备', value: stats.faulty_devices ?? '--', icon: Warning, color: '#F56C6C',
    warn: (stats.faulty_devices ?? 0) > 0 },
  { title: 'API 状态', value: apiHealthy.value ? '正常' : '异常', icon: Aim, color: '#67C23A',
    clickable: true, click: () => router.push('/settings') },
  { title: 'Subagent 任务', value: `${stats.subagent_tasks?.working ?? 0} 工作中 / ${stats.subagent_tasks?.total ?? 0} 总计`,
    icon: ChatDotRound, color: '#E6A23C' },
])

// ── Subagent 监控 ──
const subagents = ref([])
const dispatching = ref(null)
const dispatchTask = ref('')
const dispatchingLoading = ref(false)
const dispatchResult = ref('')

async function loadSubagents() {
  try {
    const [saRes, topoRes] = await Promise.all([
      api.get('/subagents/'), api.get('/topology/')
    ])
    const topoMap = {}
    ;(topoRes.data.topologies || []).forEach(t => { topoMap[t.id] = t.name })
    subagents.value = (saRes.data.subagents || []).map(s => ({
      ...s, topo_name: topoMap[s.topology_id] || '—'
    }))
  } catch { subagents.value = [] }
}

async function doDispatch() {
  if (!dispatching.value || !dispatchTask.value.trim()) return
  dispatchingLoading.value = true
  try {
    const res = await api.post('/agent/dispatch', {
      subagent_id: dispatching.value.id,
      task: dispatchTask.value.trim(),
    }, { timeout: 120000 })
    dispatchResult.value = res.data.reply || '任务已派发'
  } catch (e) {
    dispatchResult.value = '❌ ' + (e.response?.data?.detail || e.message)
  } finally {
    dispatchingLoading.value = false
    loadSubagents()
  }
}

// ── 总控 Agent ──
const commanderInput = ref('')
const commanderMessages = ref([])
const commanderLoading = ref(false)
const commanderAbort = ref(null)
const loadingText = ref('思考中')

const HISTORY_KEY = 'opsbrain-commander-history'

function saveHistory() {
  try {
    const data = commanderMessages.value.slice(-50)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(data))
  } catch (e) {
    // localStorage 满了就清掉旧的
    try { localStorage.removeItem(HISTORY_KEY); localStorage.setItem(HISTORY_KEY, JSON.stringify(commanderMessages.value.slice(-20))) } catch {} 
  }
}
function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (raw) { commanderMessages.value = JSON.parse(raw); return }
  } catch {}
  commanderMessages.value = []
}
function deleteMsg(idx) { commanderMessages.value.splice(idx, 1); saveHistory() }
async function resetCommander() {
  commanderMessages.value = []; saveHistory()
  // Clear backend memory
  try { await api.post('/agent/chat', { message: '/reset' }) } catch {}
}

// 动态加载文案
const loadingPhrases = ['分析需求中…', '正在调度 Subagent…', '等待 Subagent 汇报…', '汇总结果中…']
let loadingTimer = null

function renderMd(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^- (.+)/gm, '• $1')
}

function startLoading() {
  let idx = 0
  loadingText.value = loadingPhrases[0]
  loadingTimer = setInterval(() => {
    idx = (idx + 1) % loadingPhrases.length
    loadingText.value = loadingPhrases[idx]
  }, 3000)
}

function stopLoading() {
  if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null }
}

async function sendCommander() {
  const msg = commanderInput.value.trim()
  if (!msg) return
  commanderMessages.value.push({ role: 'user', content: msg })
  saveHistory()
  commanderInput.value = ''
  commanderLoading.value = true
  commanderAbort.value = new AbortController()
  startLoading()
  startFastPoll()
  scrollChat()
  try {
    const res = await api.post('/agent/chat', { message: msg }, { timeout: 120000, signal: commanderAbort.value.signal })
    const entry = { role: 'assistant', content: res.data.reply || '无响应' }
    // 如果有 Subagent 内部汇报，附加（默认折叠）
    if (res.data.subagent_report) {
      entry.report = res.data.subagent_report
      entry.showReport = false
    }
    commanderMessages.value.push(entry)
    saveHistory()  // 保存到 localStorage
  } catch (e) {
    if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') {
      commanderMessages.value.push({ role: 'assistant', content: '⏹ 操作已由用户取消' })
    } else {
      commanderMessages.value.push({ role: 'assistant', content: '❌ ' + (e.response?.data?.detail || e.message) })
    }
  } finally {
    commanderLoading.value = false
    commanderAbort.value = null
    stopLoading()
    stopFastPoll()
    await loadSubagents()
    await refreshStats()
    scrollChat()
  }
}

function cancelCommander() {
  if (commanderAbort.value) commanderAbort.value.abort()
}

function scrollChat() {
  nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight })
}

// ── 初始化 ──
let slowPoll = null
let fastPoll = null
let chatPoll = null

const localInfo = reactive({ hostname: '', cpu: {}, memory: {}, network: {}, disk: {} })

async function refreshStats() {
  try { Object.assign(stats, (await api.get('/dashboard/stats')).data) } catch {}
}

async function loadLocalInfo() {
  try { Object.assign(localInfo, (await api.get('/dashboard/local-info')).data) } catch {}
}

// 从服务器拉取 Commander 聊天历史（含飞书消息）
async function syncChatHistory() {
  try {
    const res = await api.get('/agent/chat/history')
    const serverMsgs = res.data.messages || []
    if (serverMsgs.length === 0) return
    // 合并：服务器消息追加到本地（按 ts 去重）
    const localIds = new Set(commanderMessages.value.map(m => m.ts || m.content?.slice(0,30)))
    let changed = false
    for (const sm of serverMsgs) {
      const key = sm.ts || sm.content?.slice(0,30) || ''
      if (key && !localIds.has(key)) {
        commanderMessages.value.push({ ...sm, fromServer: true })
        localIds.add(key)
        changed = true
      }
    }
    if (changed) {
      // 去重排序
      commanderMessages.value.sort((a, b) => (a.ts || '') > (b.ts || '') ? 1 : -1)
      saveHistory()
    }
  } catch { /* ignore */ }
}

function startFastPoll() {
  clearInterval(fastPoll)
  clearInterval(slowPoll)
  fastPoll = setInterval(() => { loadSubagents(); refreshStats(); syncChatHistory() }, 3000)
}

function stopFastPoll() {
  clearInterval(fastPoll)
  slowPoll = setInterval(() => { loadSubagents(); refreshStats(); loadLocalInfo(); syncChatHistory() }, 15000)
}

onMounted(async () => {
  loadHistory()
  await syncChatHistory()  // 首次从服务器同步
  try { Object.assign(stats, (await api.get('/dashboard/stats')).data) } catch {}
  try { const h = await api.get('/dashboard/api-health'); apiHealthy.value = h.data.total > 0 ? h.data.unhealthy === 0 : true } catch {}
  loadSubagents()
  loadLocalInfo()
  slowPoll = setInterval(() => { loadSubagents(); refreshStats(); loadLocalInfo(); syncChatHistory() }, 15000)
})
</script>

<style scoped>
.stat-card { display: flex; align-items: center; gap: 16px; }
.stat-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-value { font-size: 22px; font-weight: 700; line-height: 1.2; }
.stat-value.has-warn { color: #f56c6c; animation: warnPulse 1.5s infinite; }
.stat-label { font-size: 13px; color: #999; }
.card-clickable { cursor: pointer; transition: transform 0.15s; }
.card-clickable:hover { transform: translateY(-2px); }
@keyframes warnPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

/* Commander */
.commander-card { overflow: hidden; }
.commander-header { display: flex; align-items: center; justify-content: space-between; }
.commander-tags { display: flex; gap: 4px; }
.commander-chat { max-height: 300px; overflow-y: auto; padding: 4px 0; }
.chat-empty { text-align: center; padding: 20px 0; color: #909399; }
.chat-msg { display: flex; gap: 8px; margin-bottom: 12px; }
.chat-msg.user { flex-direction: row-reverse; }
.msg-avatar { flex-shrink: 0; font-size: 22px; width: 32px; text-align: center; margin-top: 2px; }
.msg-bubble { padding: 8px 12px; border-radius: 12px; max-width: 80%; font-size: 13px; line-height: 1.6; word-break: break-word; }
.chat-msg.user .msg-bubble { background: var(--primary-color); color: #fff; border-radius: 12px 12px 2px 12px; }
.chat-msg.assistant .msg-bubble { background: var(--main-bg); color: var(--text-color); border-radius: 12px 12px 12px 2px; }
.typing .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #909399; margin: 0 2px; animation: dotPulse 1.2s infinite; }
.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.typing .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse { 0%,60%,100% { opacity: 0.3; } 30% { opacity: 1; } }

.msg-bubble-wrap { position: relative; max-width: 80%; }
.msg-bubble-wrap .msg-bubble { max-width: 100%; }
.msg-delete { position: absolute; top: -4px; right: -28px; opacity: 0; transition: opacity .15s; padding: 2px; height: 22px; }
.msg-bubble-wrap:hover .msg-delete { opacity: 1; }
.chat-msg.user .msg-delete { right: auto; left: -28px; }
.loading-bubble { font-size: 13px; color: #909399; font-style: italic; }
.dot-pulse::after { content: ''; animation: ellipsis 1.5s infinite; }
@keyframes ellipsis { 0% { content: ''; } 25% { content: '.'; } 50% { content: '..'; } 75% { content: '...'; } 100% { content: ''; } }

.subagent-report { margin-top: 8px; padding: 6px 10px; background: #f0f5ff; border-radius: 6px; font-size: 12px; color: #409eff; cursor: pointer; user-select: none; }
.subagent-report:hover { background: #e6f0ff; }
.report-content { margin-top: 6px; padding-top: 6px; border-top: 1px dashed #d9e8ff; color: var(--text-secondary); font-size: 12px; line-height: 1.8; }
.commander-input { border-top: 1px solid var(--border-color); padding-top: 8px; margin-top: 4px; }

/* Subagent */
.section-header { display: flex; align-items: center; justify-content: space-between; }
.subagent-list { max-height: 280px; overflow-y: auto; }
.subagent-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 8px; border-radius: 6px; cursor: pointer; transition: background 0.15s; }
.subagent-item:hover { background: var(--main-bg); }
.sa-left { display: flex; align-items: center; gap: 10px; }
.sa-icon { font-size: 24px; }
.sa-name { font-size: 14px; font-weight: 600; }
.sa-topo { font-size: 12px; color: #909399; }
.sa-right { display: flex; align-items: center; gap: 8px; }
.sa-msgs { font-size: 11px; color: #909399; }
.dispatch-card { margin-top: 12px; }
.dispatch-result { margin-top: 10px; padding: 10px; background: var(--main-bg); border-radius: 6px; font-size: 13px; line-height: 1.6; max-height: 250px; overflow-y: auto; }

@media (max-width: 768px) {
  .commander-chat { max-height: 200px; }
  .msg-bubble { max-width: 90%; font-size: 12px; }
  .subagent-list { max-height: 200px; }
}

.local-info { font-size: 12px; }
.local-row { display: flex; align-items: center; justify-content: space-between; padding: 4px 0; gap: 8px; }
.local-label { color: #909399; flex-shrink: 0; min-width: 40px; }
.local-val { color: var(--text-color); font-weight: 600; font-size: 11px; text-align: right; }
.local-val-sm { color: var(--text-secondary); font-size: 11px; text-align: right; }
.local-row .el-progress { flex: 1; }
</style>
