<template>
  <div class="dashboard">
    <div class="page-header">
      <div>
        <h2 class="page-title">控制台</h2>
        <p class="page-desc">OpsBrain 企业网络运维平台</p>
      </div>
    </div>

    <!-- ── 统计卡片 ── -->
    <div class="stats-grid">
      <div v-for="card in statCards" :key="card.title" class="stat-card" :class="{ clickable: card.clickable, 'has-warn': card.warn }" @click="card.clickable && card.click()">
        <div class="stat-icon-wrap" :style="{ background: card.bg }">
          <el-icon :size="22" :style="{ color: card.color }"><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.title }}</div>
        </div>
      </div>
    </div>

    <div class="content-grid">
      <!-- ── 左侧：拓扑概览 ── -->
      <div class="content-col">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title"><el-icon style="margin-right:6px;vertical-align:middle"><Connection /></el-icon>拓扑概览</span>
            <el-tag size="small" effect="plain" round>{{ topologies.length }} 个</el-tag>
          </div>
          <div class="panel-body">
            <div v-if="topologies.length === 0" class="empty-state">
              <div class="empty-icon">🗺️</div>
              <p>暂无拓扑</p>
              <p class="empty-hint">在右侧 Agent 中说「发现网络拓扑」即可创建</p>
            </div>
            <div v-else class="topo-list">
              <div v-for="t in topologies" :key="t.id" class="topo-item" @click="$router.push(`/topology/${t.id}`)">
                <div class="topo-icon">🗺️</div>
                <div class="topo-info">
                  <div class="topo-name">{{ t.name }}</div>
                  <div class="topo-meta">{{ t.device_count }} 设备 · {{ t.link_count }} 链路</div>
                </div>
                <el-tag size="small" effect="plain" round class="topo-method">{{ t.discovery_method || 'lan' }}</el-tag>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">本机信息</span>
          </div>
          <div class="panel-body">
            <div v-if="localInfo.hostname" class="local-info">
              <div class="info-row">
                <span class="info-label">主机名</span>
                <span class="info-val">{{ localInfo.hostname }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">CPU</span>
                <span class="info-val">{{ localInfo.cpu?.model?.substring(0,30) || '—' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">内存</span>
                <div class="info-progress">
                  <el-progress :percentage="localInfo.memory?.pct || 0" :stroke-width="6" :show-text="false"
                    :color="(localInfo.memory?.pct || 0) > 80 ? 'var(--danger-color)' : 'var(--success-color)'" />
                </div>
                <span class="info-val-sm">{{ localInfo.memory?.used_mb || 0 }}M / {{ localInfo.memory?.total_mb || 0 }}M</span>
              </div>
              <div class="info-row">
                <span class="info-label">磁盘</span>
                <span class="info-val-sm">{{ localInfo.disk?.free_gb || 0 }}G 可用 / {{ localInfo.disk?.total_gb || 0 }}G</span>
              </div>
            </div>
            <div v-else class="empty-state small">加载中...</div>
          </div>
        </div>
      </div>

      <!-- ── 右侧：AI Agent ── -->
      <div class="content-col">
        <div class="panel agent-panel">
          <div class="panel-header">
            <span class="panel-title">
              <span class="agent-dot"></span>
              AI 运维助手
            </span>
            <div class="agent-tags">
              <span class="mini-tag blue">发现</span>
              <span class="mini-tag green">操作</span>
              <span class="mini-tag orange">分析</span>
              <el-button text size="small" type="danger" icon="Delete" @click="resetAgent" class="reset-btn">重置</el-button>
            </div>
          </div>

          <div class="agent-chat" ref="chatRef">
            <div v-if="messages.length === 0" class="chat-empty">
              <div class="empty-avatar">🤖</div>
              <p class="empty-title">AI 运维助手已就绪</p>
              <div class="quick-actions">
                <button class="quick-btn" @click="quickSend('发现网络拓扑')">🗺️ 发现拓扑</button>
                <button class="quick-btn" @click="quickSend('检查全网设备状态')">🔍 检查设备</button>
                <button class="quick-btn" @click="quickSend('查看系统概览')">📊 系统概览</button>
              </div>
            </div>

            <div v-for="(msg, i) in messages" :key="i" :class="['chat-msg', msg.role]">
              <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
              <div class="msg-bubble-wrap">
                <div class="msg-bubble" v-html="renderMd(msg.content)" />
                <el-button class="msg-delete" text size="small" type="danger" icon="Delete" @click="deleteMsg(i)" />
              </div>
            </div>

            <div v-if="loading" class="chat-msg assistant">
              <div class="msg-avatar">🤖</div>
              <div class="msg-bubble loading-bubble">
                <span class="loading-dots">{{ loadingText }}<span class="dot-pulse"></span></span>
              </div>
            </div>
          </div>

          <div class="agent-input">
            <el-input v-model="input" placeholder="描述需求... 如: 发现网络拓扑 / 检查设备 / SSH 执行命令"
                      size="large" :disabled="loading" @keyup.enter="sendMessage" class="chat-input">
              <template #append>
                <el-button v-if="!loading" :icon="Promotion" @click="sendMessage" :disabled="!input.trim()" type="primary" />
                <el-button v-else type="danger" :icon="Close" @click="cancelMessage" />
              </template>
            </el-input>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Connection, Warning, Aim, Cpu, Promotion, Close, Delete } from '@element-plus/icons-vue'
import { api } from '@/stores/auth'

const router = useRouter()
const chatRef = ref(null)

const stats = reactive({ topology_count: 0, faulty_devices: 0, api_status: {}, total_devices: 0 })
const apiState = ref({ configured: false, checking: true, healthy: null })
const topologies = ref([])
const localInfo = reactive({ hostname: '', cpu: {}, memory: {}, network: {}, disk: {} })

const statCards = computed(() => [
  { title: '拓扑数量', value: stats.topology_count ?? '--', icon: Connection, color: '#3b82f6', bg: '#eff6ff',
    clickable: true, click: () => router.push('/topology') },
  { title: '故障设备', value: stats.faulty_devices ?? '--', icon: Warning, color: '#ef4444', bg: '#fef2f2',
    warn: (stats.faulty_devices ?? 0) > 0 },
  { title: 'API 状态', value: apiStatusText.value, icon: Aim, color: apiStatusColor.value, bg: apiStatusBg.value,
    clickable: true, click: () => router.push('/settings') },
  { title: '设备总数', value: stats.total_devices ?? '--', icon: Cpu, color: '#10b981', bg: '#ecfdf5' },
])

const apiStatusText = computed(() => {
  if (!apiState.value.configured) return '未配置'
  if (apiState.value.checking) return '检测中'
  return apiState.value.healthy ? '正常' : '异常'
})
const apiStatusColor = computed(() => {
  if (!apiState.value.configured) return '#94a3b8'
  if (apiState.value.checking) return '#f59e0b'
  return apiState.value.healthy ? '#10b981' : '#ef4444'
})
const apiStatusBg = computed(() => {
  if (!apiState.value.configured) return '#f1f5f9'
  if (apiState.value.checking) return '#fffbeb'
  return apiState.value.healthy ? '#ecfdf5' : '#fef2f2'
})

const input = ref('')
const messages = ref([])
const loading = ref(false)
const abortCtrl = ref(null)
const loadingText = ref('思考中')
const HISTORY_KEY = 'opsbrain-agent-history'

const loadingPhrases = ['分析需求中…', '调用工具执行…', '等待设备响应…', '汇总结果中…']
let loadingTimer = null

function saveHistory() {
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(messages.value.slice(-50))) }
  catch { try { localStorage.removeItem(HISTORY_KEY); localStorage.setItem(HISTORY_KEY, JSON.stringify(messages.value.slice(-20))) } catch {} }
}
function loadHistory() {
  try { const raw = localStorage.getItem(HISTORY_KEY); if (raw) { messages.value = JSON.parse(raw); return } } catch {}
  messages.value = []
}
function deleteMsg(idx) { messages.value.splice(idx, 1); saveHistory() }
async function resetAgent() {
  messages.value = []; saveHistory()
  try { await api.post('/agent/chat', { message: '/reset' }) } catch {}
}

function renderMd(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^- (.+)/gm, '• $1')
}

function startLoading() {
  let idx = 0; loadingText.value = loadingPhrases[0]
  loadingTimer = setInterval(() => { idx = (idx + 1) % loadingPhrases.length; loadingText.value = loadingPhrases[idx] }, 3000)
}
function stopLoading() { if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null } }

function quickSend(msg) { input.value = msg; sendMessage() }

async function sendMessage() {
  const msg = input.value.trim()
  if (!msg) return
  messages.value.push({ role: 'user', content: msg })
  saveHistory(); input.value = ''; loading.value = true
  abortCtrl.value = new AbortController()
  startLoading(); scrollChat()
  try {
    const data = await api.post('/agent/chat', { message: msg }, { timeout: 120000, signal: abortCtrl.value.signal })
    messages.value.push({ role: 'assistant', content: data.reply || '无响应' })
    saveHistory()
  } catch (e) {
    if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') {
      messages.value.push({ role: 'assistant', content: '⏹ 已取消' })
    } else {
      messages.value.push({ role: 'assistant', content: '❌ ' + e.message })
    }
  } finally {
    loading.value = false; abortCtrl.value = null; stopLoading()
    await refreshStats(); scrollChat()
  }
}
function cancelMessage() { if (abortCtrl.value) abortCtrl.value.abort() }
function scrollChat() { nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight }) }

async function refreshStats() {
  try { Object.assign(stats, await api.get('/dashboard/stats')); apiState.value.configured = stats.api_status?.configured ?? (stats.api_status?.total > 0) } catch {}
}
async function loadTopologies() {
  try { topologies.value = await api.get('/topology/') || [] } catch { topologies.value = [] }
}
async function loadLocalInfo() {
  try { Object.assign(localInfo, await api.get('/dashboard/local-info')) } catch {}
}

let slowPoll = null
onMounted(async () => {
  loadHistory()
  await refreshStats()
  try {
    const h = await api.get('/dashboard/api-health')
    apiState.value.configured = h.total > 0
    apiState.value.healthy = h.total > 0 ? h.unhealthy === 0 : null
  } catch { apiState.value.healthy = false }
  finally { apiState.value.checking = false }
  loadTopologies(); loadLocalInfo()
  slowPoll = setInterval(() => { refreshStats(); loadTopologies(); loadLocalInfo() }, 15000)
})
</script>

<style scoped>
.dashboard { max-width: 1400px; margin: 0 auto; }

.page-header { margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 800; color: var(--text-color); margin-bottom: 4px; letter-spacing: -0.5px; }
.page-desc { font-size: 14px; color: var(--text-secondary); }

/* ── Stats Grid ── */
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card {
  background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--radius-md);
  padding: 20px; display: flex; align-items: center; gap: 16px; transition: all 0.2s;
}
.stat-card:hover { box-shadow: var(--shadow-md); transform: translateY(-1px); }
.stat-card.clickable { cursor: pointer; }
.stat-card.has-warn { border-color: var(--danger-color); }
.stat-card.has-warn .stat-value { color: var(--danger-color); animation: warnPulse 1.5s infinite; }
@keyframes warnPulse { 0%,100%{opacity:1} 50%{opacity:.5} }
.stat-icon-wrap { width: 48px; height: 48px; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-value { font-size: 28px; font-weight: 800; line-height: 1; color: var(--text-color); }
.stat-label { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

/* ── Content Grid ── */
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.content-col { display: flex; flex-direction: column; gap: 16px; }

/* ── Panel ── */
.panel {
  background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--radius-md);
  overflow: hidden; display: flex; flex-direction: column;
}
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px; border-bottom: 1px solid var(--border-color); flex-shrink: 0;
}
.panel-title { font-size: 15px; font-weight: 700; color: var(--text-color); display: flex; align-items: center; }
.panel-body { padding: 16px 20px; flex: 1; overflow-y: auto; }

/* ── Empty State ── */
.empty-state { text-align: center; padding: 32px 16px; color: var(--text-secondary); }
.empty-state.small { padding: 16px; font-size: 13px; }
.empty-icon { font-size: 40px; margin-bottom: 12px; }
.empty-state p { margin-bottom: 4px; }
.empty-hint { font-size: 12px; color: var(--text-muted); }

/* ── Topo List ── */
.topo-list { display: flex; flex-direction: column; gap: 8px; }
.topo-item {
  display: flex; align-items: center; gap: 12px; padding: 12px; border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.15s; border: 1px solid transparent;
}
.topo-item:hover { background: var(--primary-light); border-color: var(--primary-color); }
.topo-icon { font-size: 24px; }
.topo-info { flex: 1; min-width: 0; }
.topo-name { font-size: 14px; font-weight: 600; color: var(--text-color); }
.topo-meta { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.topo-method { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }

/* ── Local Info ── */
.local-info { display: flex; flex-direction: column; gap: 10px; }
.info-row { display: flex; align-items: center; gap: 12px; }
.info-label { color: var(--text-muted); font-size: 12px; min-width: 48px; flex-shrink: 0; }
.info-val { color: var(--text-color); font-weight: 600; font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.info-val-sm { color: var(--text-secondary); font-size: 12px; }
.info-progress { flex: 1; }

/* ── Agent Panel ── */
.agent-panel { min-height: 500px; }
.agent-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--success-color);
  display: inline-block; margin-right: 8px; animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.2)} }

.agent-tags { display: flex; align-items: center; gap: 6px; }
.mini-tag {
  font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; letter-spacing: 0.5px;
}
.mini-tag.blue { background: #eff6ff; color: #3b82f6; }
.mini-tag.green { background: #ecfdf5; color: #10b981; }
.mini-tag.orange { background: #fffbeb; color: #f59e0b; }
[data-theme="dark"] .mini-tag.blue { background: #1e3a5f; color: #60a5fa; }
[data-theme="dark"] .mini-tag.green { background: #1a3a2a; color: #34d399; }
[data-theme="dark"] .mini-tag.orange { background: #3a2a1a; color: #fbbf24; }
.reset-btn { margin-left: 4px; font-size: 12px; }

.agent-chat { flex: 1; overflow-y: auto; padding: 16px 20px; min-height: 300px; }
.chat-empty { text-align: center; padding: 40px 16px; }
.empty-avatar { font-size: 48px; margin-bottom: 12px; }
.empty-title { font-size: 15px; font-weight: 600; color: var(--text-color); margin-bottom: 20px; }
.quick-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
.quick-btn {
  padding: 8px 16px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);
  background: var(--card-bg); color: var(--text-secondary); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.quick-btn:hover { background: var(--primary-light); color: var(--primary-color); border-color: var(--primary-color); }

.chat-msg { display: flex; gap: 10px; margin-bottom: 16px; }
.chat-msg.user { flex-direction: row-reverse; }
.msg-avatar { flex-shrink: 0; font-size: 20px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--main-bg); }
.msg-bubble-wrap { position: relative; max-width: 80%; }
.msg-bubble-wrap .msg-bubble { max-width: 100%; }
.msg-bubble {
  padding: 10px 14px; border-radius: var(--radius-md); font-size: 13px; line-height: 1.7;
  word-break: break-word;
}
.chat-msg.user .msg-bubble {
  background: var(--primary-color); color: #fff; border-radius: var(--radius-md) var(--radius-md) 4px var(--radius-md);
}
.chat-msg.assistant .msg-bubble {
  background: var(--main-bg); color: var(--text-color); border-radius: var(--radius-md) var(--radius-md) var(--radius-md) 4px;
}
.msg-delete { position: absolute; top: -4px; right: -32px; opacity: 0; transition: opacity .15s; padding: 2px; height: 22px; }
.msg-bubble-wrap:hover .msg-delete { opacity: 1; }
.chat-msg.user .msg-delete { right: auto; left: -32px; }
.loading-bubble { font-size: 13px; color: var(--text-secondary); font-style: italic; }
.loading-dots { display: inline-flex; align-items: center; }
.dot-pulse::after { content: ''; animation: ellipsis 1.5s infinite; }
@keyframes ellipsis { 0%{content:''} 25%{content:'.'} 50%{content:'..'} 75%{content:'...'} 100%{content:''} }

.agent-input { padding: 12px 16px 16px; border-top: 1px solid var(--border-color); flex-shrink: 0; }
.chat-input :deep(.el-input__wrapper) { border-radius: var(--radius-md) !important; }

/* ── Responsive ── */
@media (max-width: 1024px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .content-grid { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .stat-card { padding: 14px; }
  .stat-value { font-size: 22px; }
  .stat-icon-wrap { width: 40px; height: 40px; }
  .agent-chat { min-height: 250px; }
  .msg-bubble { max-width: 90%; }
  .quick-actions { flex-direction: column; }
  .quick-btn { width: 100%; }
}
</style>
