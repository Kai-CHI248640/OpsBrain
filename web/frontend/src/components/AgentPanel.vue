<template>
  <div class="agent-panel" :class="{ collapsed: !open, 'is-mobile': isMobile }">
    <div v-if="!open" class="agent-toggle" @click="openPanel">
      <el-icon :size="18"><ChatDotRound /></el-icon>
      <span class="toggle-label">Subagent</span>
    </div>

    <div v-if="open" class="agent-content">
      <div class="agent-header">
        <span class="agent-title">Subagent</span>
        <el-tag v-if="topoName" size="small" type="info" effect="plain" class="ref-badge">
          📎 {{ topoName }}
        </el-tag>
        <el-tag size="small" :type="subagentStatusTagType" effect="plain" class="status-badge">
          {{ subagentStatusLabel }}
        </el-tag>
        <el-button text size="small" @click="closePanel" icon="Close" class="close-btn" />
        <el-button text size="small" type="danger" icon="Delete" @click="resetPanel" class="reset-btn">重置</el-button>
      </div>

      <!-- 设备面板 -->
      <div v-if="topoDevices.length" class="device-quickbar">
        <div class="quickbar-title">📡 可操作设备</div>
        <div class="device-chips">
          <span v-for="d in topoDevices" :key="d.name" class="device-chip"
                :class="{ 'has-ip': d.ip }"
                @click="quickAsk(d)">
            {{ deviceIcon(d.type) }} {{ d.name }}
            <span v-if="d.ip" class="chip-ip">{{ d.ip }}</span>
          </span>
        </div>
      </div>

      <div class="agent-messages" ref="msgList">
        <div v-if="messages.length === 0" class="agent-empty">
          <p>🤖 Subagent 已就绪</p>
          <p style="font-size:13px;color:#909399;line-height:1.8">
            <strong>执行:</strong> SSH/Telnet 到设备操作<br>
            <strong>配置:</strong> 部署网络配置/脚本<br>
            <strong>汇报:</strong> 向总控 Agent 报告结果<br>
          </p>
          <div style="margin-top:12px;font-size:12px;color:#909399">
            点击上方设备快速提问，或直接输入指令
          </div>
        </div>

        <div v-for="(msg, i) in messages" :key="i" :class="['agent-msg', msg.role]">
          <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="msg-bubble-wrap">
            <div class="msg-content" v-html="renderMarkdown(msg.content)" />
            <el-button class="msg-delete" text size="small" type="danger" icon="Delete" @click="deleteMsg(i)" />
          </div>
        </div>

        <div v-if="loading" class="agent-msg assistant">
          <div class="msg-avatar">🤖</div>
          <div class="msg-content typing">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>

      <div class="agent-input-area" ref="inputRef">
        <el-input v-model="input" :placeholder="inputPlaceholder"
                  @keyup.enter="sendMessage" :disabled="loading"
                  size="small" class="agent-input">
          <template #append>
            <el-button v-if="!loading" icon="Promotion" @click="sendMessage" :disabled="!input.trim()" />
            <el-button v-else type="danger" icon="Close" @click="cancelMessage">停止</el-button>
          </template>
        </el-input>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { api } from '@/stores/auth'
import { ChatDotRound, Close, Promotion, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  topoId: { type: String, default: '' },
  topoName: { type: String, default: '' },
})

const open = ref(false)
const input = ref('')
const messages = ref([])
const loading = ref(false)
const abortCtrl = ref(null)
const msgList = ref(null)
const inputRef = ref(null)
const isMobile = ref(window.innerWidth < 768)
const topoDevices = ref([])

function checkMobile() { isMobile.value = window.innerWidth < 768 }

onMounted(() => {
  window.addEventListener('resize', checkMobile)
  loadSubagent()
  loadTopoDevices()
  loadHistory()
})
onUnmounted(() => { window.removeEventListener('resize', checkMobile) })

const subagentId = ref('')
const subagentStatus = ref('idle')

// 聊天历史
const historyKey = computed(() => props.topoId ? `opsbrain-subagent-${props.topoId}-history` : '')
function saveHistory() {
  if (!historyKey.value) return
  try {
    localStorage.setItem(historyKey.value, JSON.stringify(messages.value.slice(-50)))
  } catch {
    try { localStorage.removeItem(historyKey.value); localStorage.setItem(historyKey.value, JSON.stringify(messages.value.slice(-20))) } catch {}
  }
}
function loadHistory() {
  if (!historyKey.value) return
  try {
    const raw = localStorage.getItem(historyKey.value)
    if (raw) { messages.value = JSON.parse(raw); return }
  } catch {}
  messages.value = []
}
function deleteMsg(idx) { messages.value.splice(idx, 1); saveHistory() }
async function resetPanel() {
  messages.value = []
  // 直接清除 localStorage 中该拓扑的所有聊天记录
  if (historyKey.value) {
    localStorage.removeItem(historyKey.value)
  }
  // 同时也清除无前缀的历史 key（兼容旧数据）
  localStorage.removeItem('opsbrain-agent-history')
  try {
    await api.post(`/agent/${props.topoId}/chat`, { message: '/reset' }, { timeout: 10000 })
    // 再次确认清除
    if (historyKey.value) {
      localStorage.removeItem(historyKey.value)
    }
  } catch {}
}

// 监听 topoId 变化，确保在拓扑加载完成后加载历史
watch(() => props.topoId, (newId) => {
  if (newId) loadHistory()
})
const subagentStatusLabel = computed(() =>
  ({ idle: '待机', working: '工作中', error: '异常' }[subagentStatus.value] || '待机'))
const subagentStatusTagType = computed(() =>
  ({ idle: 'info', working: 'warning', error: 'danger' }[subagentStatus.value] || 'info'))
const inputPlaceholder = computed(() => {
  if (loading.value) return '执行中…'
  return '指令（如: SSH 到 R1 查看配置 / 检查所有交换机端口状态 / 部署 VLAN 配置）'
})

async function loadSubagent() {
  if (!props.topoId) return
  try {
    const res = await api.get(`/subagents/topology/${props.topoId}`)
    subagentId.value = res.data.id
    subagentStatus.value = res.data.status || 'idle'
  } catch {}
}

async function loadTopoDevices() {
  if (!props.topoId) return
  try {
    const res = await api.get(`/topology/${props.topoId}`)
    topoDevices.value = (res.data.device_data || []).slice(0, 10)
  } catch { topoDevices.value = [] }
}

async function updateSubagentStatus(status) {
  if (!subagentId.value) return
  try {
    await api.put(`/subagents/${subagentId.value}/status`, {
      status, message_count: messages.value.filter(m => m.role === 'user').length,
    })
    subagentStatus.value = status
  } catch {}
}

function deviceIcon(type) {
  return { router: '🌐', switch: '🔀', firewall: '🛡️', server: '🖥️', unknown: '📡' }[type] || '📡'
}

function quickAsk(device) {
  input.value = `检查设备 ${device.name} ${device.ip ? `(${device.ip})` : ''} 的状态和配置`
  sendMessage()
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^- (.+)/gm, '• $1')
}

let statusPoll = null

function startStatusPoll() {
  statusPoll = setInterval(() => { loadSubagent() }, 2000)
}

function stopStatusPoll() {
  if (statusPoll) { clearInterval(statusPoll); statusPoll = null }
}

async function sendMessage() {
  const msg = input.value.trim()
  if (!msg || !props.topoId) return

  messages.value.push({ role: 'user', content: msg })
  saveHistory()
  input.value = ''
  loading.value = true
  abortCtrl.value = new AbortController()
  updateSubagentStatus('working')
  startStatusPoll()
  scrollToBottom()

  try {
    const res = await api.post(`/agent/${props.topoId}/chat`,
      { message: msg }, { timeout: 120000, signal: abortCtrl.value.signal })
    messages.value.push({ role: 'assistant', content: res.data.reply || '无响应' })
    saveHistory()
    updateSubagentStatus('idle')
  } catch (e) {
    if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') {
      messages.value.push({ role: 'assistant', content: '⏹ 已取消' })
    } else {
      messages.value.push({ role: 'assistant', content: '❌ ' + (e.response?.data?.detail || e.message) })
    }
    updateSubagentStatus('idle')
  } finally {
    loading.value = false
    abortCtrl.value = null
    stopStatusPoll()
    loadSubagent()  // final refresh
    scrollToBottom()
  }
}

function openPanel() { open.value = true; scrollToBottom() }
function closePanel() { open.value = false }
function cancelMessage() { if (abortCtrl.value) abortCtrl.value.abort() }

function scrollToBottom() {
  nextTick(() => {
    if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
  })
}

watch(() => messages.value.length, scrollToBottom)
</script>

<style scoped>
.agent-panel {
  position: fixed; right: 0; top: 56px; bottom: 0; width: 48px;
  z-index: 900; background: var(--card-bg); border-left: 1px solid var(--border-color);
  display: flex; flex-direction: column; transition: width 0.25s ease; overflow: hidden;
}
.agent-panel.collapsed { width: 48px; }
.agent-panel:not(.collapsed) { width: 380px; }
.agent-content { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.agent-toggle {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 16px 0; cursor: pointer; writing-mode: vertical-rl;
  color: var(--text-color); height: 100%; width: 48px;
}
.agent-panel:not(.collapsed) .agent-toggle { display: none; }
.toggle-label { font-size: 12px; letter-spacing: 2px; }
.agent-header { display: flex; align-items: center; gap: 6px; padding: 10px 14px; border-bottom: 1px solid var(--border-color); flex-shrink: 0; }
.agent-title { font-weight: 700; font-size: 14px; }
.ref-badge { font-size: 10px; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-badge { font-size: 10px; }
.close-btn { margin-left: auto; }

/* 设备快速栏 */
.device-quickbar { padding: 8px 14px; border-bottom: 1px solid var(--border-color); flex-shrink: 0; }
.quickbar-title { font-size: 11px; font-weight: 600; color: #909399; margin-bottom: 6px; }
.device-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.device-chip {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 3px 8px; border-radius: 12px; font-size: 11px;
  background: var(--main-bg); color: var(--text-color);
  border: 1px solid var(--border-color); cursor: pointer;
  transition: all 0.15s; white-space: nowrap;
}
.device-chip:hover { background: var(--primary-color); color: #fff; border-color: var(--primary-color); }
.device-chip.has-ip .chip-ip { font-size: 10px; color: #909399; }
.device-chip:hover .chip-ip { color: rgba(255,255,255,0.7); }

/* 消息 */
.agent-messages { flex: 1; overflow-y: auto; padding: 10px 14px; -webkit-overflow-scrolling: touch; }
.agent-empty { text-align: center; padding: 24px 8px; color: #909399; font-size: 13px; line-height: 1.8; }
.agent-msg { display: flex; gap: 8px; margin-bottom: 12px; }
.agent-msg.user { flex-direction: row-reverse; }
.msg-avatar { flex-shrink: 0; font-size: 20px; width: 28px; text-align: center; margin-top: 2px; }
.msg-content { padding: 8px 12px; border-radius: 12px; max-width: 80%; font-size: 13px; line-height: 1.6; word-break: break-word; }
.msg-bubble-wrap { position: relative; max-width: 80%; }
.msg-bubble-wrap .msg-content { max-width: 100%; }
.msg-delete { position: absolute; top: -4px; right: -28px; opacity: 0; transition: opacity .15s; padding: 2px; height: 22px; }
.msg-bubble-wrap:hover .msg-delete { opacity: 1; }
.agent-msg.user .msg-delete { right: auto; left: -28px; }
.agent-msg.user .msg-bubble-wrap { margin-left: auto; }
.agent-msg.user .msg-content { background: var(--primary-color); color: #fff; border-radius: 12px 12px 2px 12px; }
.agent-msg.assistant .msg-content { background: var(--main-bg); color: var(--text-color); border-radius: 12px 12px 12px 2px; }
.msg-content { padding: 8px 12px; border-radius: 12px; font-size: 13px; line-height: 1.6; word-break: break-word; }
.agent-msg.user .msg-content { background: var(--primary-color); color: #fff; border-radius: 12px 12px 2px 12px; }
.agent-msg.assistant .msg-content { background: var(--main-bg); color: var(--text-color); border-radius: 12px 12px 12px 2px; }
.typing .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #909399; margin: 0 2px; animation: dotPulse 1.2s infinite; }
.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.typing .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse { 0%,60%,100% { opacity: 0.3; } 30% { opacity: 1; } }
.agent-input-area { flex-shrink: 0; padding: 8px 14px 12px; border-top: 1px solid var(--border-color); background: var(--card-bg); }
.agent-input { width: 100%; }

@media (max-width: 768px) {
  .agent-panel:not(.collapsed) { width: 100vw; top: 48px; height: calc(100dvh - 48px); }
  .agent-panel.collapsed { width: 40px; }
  .agent-toggle { width: 40px; padding: 12px 0; }
  .msg-content { max-width: 90%; font-size: 13px; padding: 8px 10px; }
  .agent-input-area { padding: 6px 10px 10px; }
  .device-chips { gap: 3px; }
  .device-chip { padding: 2px 6px; font-size: 10px; }
}
</style>
