<template>
  <div class="agent-panel" :class="{ collapsed: !open, 'is-mobile': isMobile }">
    <div v-if="!open" class="agent-toggle" @click="openPanel">
      <div class="toggle-icon">🤖</div>
      <span class="toggle-label">Agent</span>
    </div>

    <div v-if="open" class="agent-content">
      <div class="agent-header">
        <div class="header-left">
          <span class="agent-dot"></span>
          <span class="agent-title">AI 助手</span>
        </div>
        <div class="header-right">
          <el-tag v-if="topoName" size="small" effect="plain" round class="topo-tag">{{ topoName }}</el-tag>
          <el-button text size="small" type="danger" icon="Delete" @click="resetPanel" class="reset-btn" />
          <el-button text size="small" icon="Close" @click="closePanel" class="close-btn" />
        </div>
      </div>

      <!-- 设备快速栏 -->
      <div v-if="topoDevices.length" class="device-quickbar">
        <div class="quickbar-title">设备</div>
        <div class="device-chips">
          <span v-for="d in topoDevices" :key="d.name" class="device-chip" @click="quickAsk(d)">
            {{ deviceIcon(d.type) }} {{ d.name }}
          </span>
        </div>
      </div>

      <div class="agent-messages" ref="msgList">
        <div v-if="messages.length === 0" class="agent-empty">
          <div class="empty-avatar">🤖</div>
          <p class="empty-title">AI 运维助手</p>
          <p class="empty-desc">直接描述需求，我会调用工具完成</p>
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

      <div class="agent-input-area">
        <el-input v-model="input" :placeholder="inputPlaceholder" @keyup.enter="sendMessage" :disabled="loading" size="default" class="agent-input">
          <template #append>
            <el-button v-if="!loading" icon="Promotion" @click="sendMessage" :disabled="!input.trim()" type="primary" />
            <el-button v-else type="danger" icon="Close" @click="cancelMessage" />
          </template>
        </el-input>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { api } from '@/stores/auth'
import { Close, Promotion, Delete } from '@element-plus/icons-vue'

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
const isMobile = ref(window.innerWidth < 768)
const topoDevices = ref([])

function checkMobile() { isMobile.value = window.innerWidth < 768 }

onMounted(() => {
  window.addEventListener('resize', checkMobile)
  loadTopoDevices()
  loadHistory()
})
onUnmounted(() => { window.removeEventListener('resize', checkMobile) })

const historyKey = computed(() => 'opsbrain-agent-history')

function saveHistory() {
  try { localStorage.setItem(historyKey.value, JSON.stringify(messages.value.slice(-50))) }
  catch { try { localStorage.removeItem(historyKey.value); localStorage.setItem(historyKey.value, JSON.stringify(messages.value.slice(-20))) } catch {} }
}
function loadHistory() {
  try { const raw = localStorage.getItem(historyKey.value); if (raw) { messages.value = JSON.parse(raw); return } } catch {}
  messages.value = []
}
function deleteMsg(idx) { messages.value.splice(idx, 1); saveHistory() }
async function resetPanel() {
  messages.value = []
  if (historyKey.value) localStorage.removeItem(historyKey.value)
  try { await api.post('/agent/chat', { message: '/reset' }, { timeout: 10000 }) } catch {}
}

const inputPlaceholder = computed(() => {
  if (loading.value) return '执行中…'
  return '描述需求...'
})

async function loadTopoDevices() {
  if (!props.topoId) return
  try {
    const res = await api.get(`/topology/${props.topoId}`)
    topoDevices.value = (res.data.device_data || []).slice(0, 10)
  } catch { topoDevices.value = [] }
}

function deviceIcon(type) {
  return { router: '🌐', switch: '🔀', firewall: '🛡️', server: '🖥️' }[type] || '📡'
}

function quickAsk(device) {
  input.value = `检查设备 ${device.name} ${device.ip ? `(${device.ip})` : ''} 的状态`
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

async function sendMessage() {
  const msg = input.value.trim()
  if (!msg) return
  messages.value.push({ role: 'user', content: msg })
  saveHistory(); input.value = ''; loading.value = true
  abortCtrl.value = new AbortController()
  scrollToBottom()

  try {
    const res = await api.post('/agent/chat', { message: msg }, { timeout: 120000, signal: abortCtrl.value.signal })
    messages.value.push({ role: 'assistant', content: res.data.reply || '无响应' })
    saveHistory()
  } catch (e) {
    if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') {
      messages.value.push({ role: 'assistant', content: '⏹ 已取消' })
    } else {
      messages.value.push({ role: 'assistant', content: '❌ ' + (e.response?.data?.detail || e.message) })
    }
  } finally {
    loading.value = false; abortCtrl.value = null; scrollToBottom()
  }
}

function openPanel() { open.value = true; scrollToBottom() }
function closePanel() { open.value = false }
function cancelMessage() { if (abortCtrl.value) abortCtrl.value.abort() }
function scrollToBottom() { nextTick(() => { if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight }) }
watch(() => messages.value.length, scrollToBottom)
</script>

<style scoped>
.agent-panel {
  position: fixed; right: 0; top: 56px; bottom: 0; width: 48px;
  z-index: 900; background: var(--card-bg); border-left: 1px solid var(--border-color);
  display: flex; flex-direction: column; transition: width 0.25s ease; overflow: hidden;
}
.agent-panel.collapsed { width: 48px; }
.agent-panel:not(.collapsed) { width: 400px; }
.agent-content { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

.agent-toggle {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  padding: 16px 0; cursor: pointer; height: 100%; width: 48px;
  color: var(--text-secondary); transition: color 0.15s;
}
.agent-toggle:hover { color: var(--primary-color); }
.toggle-icon { font-size: 20px; }
.toggle-label { font-size: 10px; letter-spacing: 1px; text-transform: uppercase; font-weight: 600; }
.agent-panel:not(.collapsed) .agent-toggle { display: none; }

.agent-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--border-color); flex-shrink: 0;
}
.header-left { display: flex; align-items: center; gap: 8px; }
.agent-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--success-color);
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
.agent-title { font-weight: 700; font-size: 14px; color: var(--text-color); }
.header-right { display: flex; align-items: center; gap: 4px; }
.topo-tag { font-size: 11px; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reset-btn, .close-btn { color: var(--text-muted); }

.device-quickbar { padding: 10px 16px; border-bottom: 1px solid var(--border-color); flex-shrink: 0; }
.quickbar-title { font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; }
.device-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.device-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 20px; font-size: 12px;
  background: var(--main-bg); color: var(--text-secondary);
  border: 1px solid var(--border-color); cursor: pointer;
  transition: all 0.15s; white-space: nowrap;
}
.device-chip:hover { background: var(--primary-light); color: var(--primary-color); border-color: var(--primary-color); }

.agent-messages { flex: 1; overflow-y: auto; padding: 16px; -webkit-overflow-scrolling: touch; }
.agent-empty { text-align: center; padding: 40px 16px; }
.empty-avatar { font-size: 40px; margin-bottom: 12px; }
.empty-title { font-size: 15px; font-weight: 600; color: var(--text-color); margin-bottom: 4px; }
.empty-desc { font-size: 13px; color: var(--text-secondary); }

.agent-msg { display: flex; gap: 10px; margin-bottom: 14px; }
.agent-msg.user { flex-direction: row-reverse; }
.msg-avatar {
  flex-shrink: 0; font-size: 18px; width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; background: var(--main-bg);
}
.msg-content {
  padding: 10px 14px; border-radius: var(--radius-md); max-width: 85%;
  font-size: 13px; line-height: 1.7; word-break: break-word;
}
.msg-bubble-wrap { position: relative; max-width: 85%; }
.msg-bubble-wrap .msg-content { max-width: 100%; }
.msg-delete { position: absolute; top: -4px; right: -30px; opacity: 0; transition: opacity .15s; padding: 2px; height: 22px; }
.msg-bubble-wrap:hover .msg-delete { opacity: 1; }
.agent-msg.user .msg-delete { right: auto; left: -30px; }
.agent-msg.user .msg-bubble-wrap { margin-left: auto; }
.agent-msg.user .msg-content {
  background: var(--primary-color); color: #fff;
  border-radius: var(--radius-md) var(--radius-md) 4px var(--radius-md);
}
.agent-msg.assistant .msg-content {
  background: var(--main-bg); color: var(--text-color);
  border-radius: var(--radius-md) var(--radius-md) var(--radius-md) 4px;
}
.typing .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); margin: 0 2px; animation: dotPulse 1.2s infinite; }
.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.typing .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse { 0%,60%,100% { opacity: 0.3; } 30% { opacity: 1; } }

.agent-input-area { flex-shrink: 0; padding: 12px 16px; border-top: 1px solid var(--border-color); background: var(--card-bg); }
.agent-input :deep(.el-input__wrapper) { border-radius: var(--radius-md) !important; }

@media (max-width: 768px) {
  .agent-panel:not(.collapsed) { width: 100vw; top: 48px; height: calc(100dvh - 48px); }
  .agent-panel.collapsed { width: 40px; }
  .agent-toggle { width: 40px; padding: 12px 0; }
  .msg-content { max-width: 90%; }
  .agent-input-area { padding: 8px 12px; }
}
</style>
