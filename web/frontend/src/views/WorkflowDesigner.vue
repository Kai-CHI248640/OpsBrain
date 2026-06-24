<template>
  <div class="workflow-designer">
    <div class="designer-header">
      <div class="header-left">
        <el-button text icon="ArrowLeft" @click="$router.push('/workflows')">返回</el-button>
        <el-divider direction="vertical" />
        <span class="wf-name">{{ workflow.name }}</span>
        <el-tag v-if="workflow.is_template" size="small" effect="plain">模板</el-tag>
      </div>
      <div class="header-right">
        <el-button size="small" @click="showExecutions = true">执行记录</el-button>
        <el-button size="small" type="success" icon="VideoPlay" @click="executeWorkflow" :loading="executing">执行</el-button>
        <el-button size="small" type="primary" icon="Check" @click="saveWorkflow" :loading="saving">保存</el-button>
      </div>
    </div>

    <div class="designer-body">
      <div class="designer-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-title">节点</div>
          <div class="node-palette">
            <div v-for="nodeType in nodeTypes" :key="nodeType.type" class="palette-item"
              draggable="true" @dragstart="onDragStart($event, nodeType)">
              <span class="palette-icon">{{ nodeType.icon }}</span>
              <span class="palette-label">{{ nodeType.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="designer-canvas" @drop="onDrop" @dragover.prevent>
        <div class="canvas-bg">
          <svg class="canvas-svg" width="100%" height="100%">
            <defs>
              <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#409eff" />
              </marker>
            </defs>
            <line v-for="edge in edges" :key="edge.id"
              :x1="getNodeCenter(edge.source).x"
              :y1="getNodeCenter(edge.source).y"
              :x2="getNodeCenter(edge.target).x"
              :y2="getNodeCenter(edge.target).y"
              stroke="#409eff" stroke-width="2" marker-end="url(#arrowhead)" />
            <line v-if="connecting"
              :x1="connectStart.x" :y1="connectStart.y"
              :x2="connectEnd.x" :y2="connectEnd.y"
              stroke="#67c23a" stroke-width="2" stroke-dasharray="5,5" />
          </svg>

          <div v-for="node in nodes" :key="node.id"
            class="canvas-node" :class="[`node-${node.type}`, { selected: selectedNode?.id === node.id }]"
            :style="{ left: node.position.x + 'px', top: node.position.y + 'px' }"
            @mousedown="startDragNode($event, node)"
            @click.stop="selectNode(node)"
            @dblclick="editNode(node)">
            <div class="node-header">
              <span class="node-icon">{{ getNodeIcon(node.type) }}</span>
              <span class="node-label">{{ node.data?.label || node.type }}</span>
            </div>
            <div v-if="node.type === 'agent'" class="node-preview">
              {{ node.data?.agent_name || 'Agent' }}: {{ (node.data?.prompt || '').substring(0, 30) }}...
            </div>
            <div class="node-ports">
              <div v-if="node.type !== 'start'" class="port port-in"
                @mousedown.stop="startConnect(node, 'in')"
                @mouseup.stop="endConnect(node, 'in')"></div>
              <div v-if="node.type !== 'end'" class="port port-out"
                @mousedown.stop="startConnect(node, 'out')"
                @mouseup.stop="endConnect(node, 'out')"></div>
            </div>
            <button class="node-delete" @click.stop="deleteNode(node.id)" v-if="node.type !== 'start' && node.type !== 'end'">×</button>
          </div>
        </div>
      </div>

      <div class="designer-properties" v-if="selectedNode">
        <div class="prop-header">
          <span class="prop-title">节点属性</span>
          <el-button text icon="Close" @click="selectedNode = null" />
        </div>
        <div class="prop-body">
          <el-form label-width="70px" size="small">
            <el-form-item label="类型">
              <el-tag>{{ selectedNode.type }}</el-tag>
            </el-form-item>
            <el-form-item label="标签">
              <el-input v-model="selectedNode.data.label" @change="onNodeDataChange" />
            </el-form-item>

            <template v-if="selectedNode.type === 'agent'">
              <el-form-item label="Agent">
                <el-input v-model="selectedNode.data.agent_name" placeholder="Agent 名称" @change="onNodeDataChange" />
              </el-form-item>
              <el-form-item label="提示词">
                <el-input v-model="selectedNode.data.prompt" type="textarea" :rows="4" placeholder="输入 Agent 提示词" @change="onNodeDataChange" />
              </el-form-item>
            </template>

            <template v-if="selectedNode.type === 'condition'">
              <el-form-item label="条件">
                <el-input v-model="selectedNode.data.condition" placeholder='例: contains(input, "error")' @change="onNodeDataChange" />
              </el-form-item>
            </template>

            <template v-if="selectedNode.type === 'delay'">
              <el-form-item label="延迟(秒)">
                <el-input-number v-model="selectedNode.data.seconds" :min="1" :max="3600" @change="onNodeDataChange" />
              </el-form-item>
            </template>
          </el-form>
        </div>
      </div>
    </div>

    <el-dialog v-model="showExecutions" title="执行记录" width="700px">
      <el-table :data="executions" v-loading="loadingExecutions" empty-text="暂无执行记录">
        <el-table-column prop="id" label="ID" width="100">
          <template #default="{ row }">{{ row.id.substring(0, 8) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" width="160">
          <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
        </el-table-column>
        <el-table-column prop="end_time" label="结束时间" width="160">
          <template #default="{ row }">{{ formatTime(row.end_time) }}</template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const wfId = route.params.id

const workflow = ref({ id: '', name: '', description: '', nodes: [], edges: [] })
const nodes = ref([])
const edges = ref([])
const selectedNode = ref(null)
const saving = ref(false)
const executing = ref(false)
const showExecutions = ref(false)
const executions = ref([])
const loadingExecutions = ref(false)

const connecting = ref(false)
const connectStart = reactive({ x: 0, y: 0 })
const connectEnd = reactive({ x: 0, y: 0 })
let connectSourceNode = null

const nodeTypes = [
  { type: 'agent', icon: '🤖', label: 'Agent', defaults: { agent_name: '运维助手', prompt: '' } },
  { type: 'condition', icon: '🔀', label: '条件', defaults: { condition: '' } },
  { type: 'delay', icon: '⏱️', label: '延迟', defaults: { seconds: 5 } },
]

const fetchWorkflow = async () => {
  try {
    const { data } = await api.get(`/workflows/${wfId}`)
    workflow.value = data
    nodes.value = data.nodes || []
    edges.value = data.edges || []
  } catch (e) {
    ElMessage.error('加载工作流失败')
    router.push('/workflows')
  }
}

const fetchExecutions = async () => {
  loadingExecutions.value = true
  try {
    const { data } = await api.get(`/workflows/${wfId}/executions`)
    executions.value = data.executions || []
  } catch {} finally {
    loadingExecutions.value = false
  }
}

const saveWorkflow = async () => {
  saving.value = true
  try {
    await api.put(`/workflows/${wfId}`, {
      name: workflow.value.name,
      description: workflow.value.description,
      nodes: nodes.value,
      edges: edges.value,
    })
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const executeWorkflow = async () => {
  executing.value = true
  try {
    await api.post(`/workflows/${wfId}/execute`, {})
    ElMessage.success('工作流已开始执行')
    fetchExecutions()
  } catch (e) {
    ElMessage.error('执行失败')
  } finally {
    executing.value = false
  }
}

const getNodeIcon = (type) => {
  const icons = { start: '▶️', end: '⏹️', agent: '🤖', condition: '🔀', delay: '⏱️' }
  return icons[type] || '⚙️'
}

const getNodeCenter = (nodeId) => {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node) return { x: 0, y: 0 }
  return { x: node.position.x + 80, y: node.position.y + 30 }
}

const selectNode = (node) => {
  selectedNode.value = node
}

const editNode = (node) => {
  selectedNode.value = node
}

const onNodeDataChange = () => {
  nodes.value = [...nodes.value]
}

const deleteNode = (id) => {
  nodes.value = nodes.value.filter(n => n.id !== id)
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
  if (selectedNode.value?.id === id) selectedNode.value = null
}

const addNode = (type, position, defaults) => {
  const id = `${type}_${Date.now()}`
  const node = {
    id,
    type,
    position,
    data: { label: defaults?.label || type, ...defaults },
  }
  nodes.value.push(node)
  return node
}

const onDragStart = (event, nodeType) => {
  event.dataTransfer.setData('nodeType', nodeType.type)
  event.dataTransfer.setData('defaults', JSON.stringify(nodeType.defaults))
}

const onDrop = (event) => {
  const type = event.dataTransfer.getData('nodeType')
  const defaults = JSON.parse(event.dataTransfer.getData('defaults') || '{}')
  const canvas = event.currentTarget
  const rect = canvas.getBoundingClientRect()
  const x = event.clientX - rect.left - 80
  const y = event.clientY - rect.top - 30
  addNode(type, { x: Math.max(0, x), y: Math.max(0, y) }, defaults)
}

const startConnect = (node, port) => {
  if (port === 'out') {
    connecting.value = true
    connectSourceNode = node
    connectStart.x = node.position.x + 160
    connectStart.y = node.position.y + 30
    connectEnd.x = connectStart.x
    connectEnd.y = connectStart.y
  }
}

const endConnect = (node, port) => {
  if (port === 'in' && connectSourceNode && connectSourceNode.id !== node.id) {
    const exists = edges.value.some(e => e.source === connectSourceNode.id && e.target === node.id)
    if (!exists) {
      edges.value.push({
        id: `edge_${Date.now()}`,
        source: connectSourceNode.id,
        target: node.id,
      })
    }
  }
  connecting.value = false
  connectSourceNode = null
}

const startDragNode = (event, node) => {
  if (event.target.closest('.port') || event.target.closest('.node-delete')) return
  const startX = event.clientX
  const startY = event.clientY
  const origX = node.position.x
  const origY = node.position.y

  const onMove = (e) => {
    node.position.x = origX + (e.clientX - startX)
    node.position.y = origY + (e.clientY - startY)
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

const formatTime = (t) => {
  if (!t) return '—'
  return new Date(t).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

watch(showExecutions, (v) => { if (v) fetchExecutions() })

onMounted(() => {
  fetchWorkflow()
})
</script>

<style scoped>
.workflow-designer { height: 100vh; display: flex; flex-direction: column; background: var(--bg-color); }

.designer-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px; background: var(--header-bg); border-bottom: 1px solid var(--border-color);
}
.header-left { display: flex; align-items: center; gap: 8px; }
.wf-name { font-size: 16px; font-weight: 600; color: var(--text-color); }
.header-right { display: flex; gap: 8px; }

.designer-body { flex: 1; display: flex; overflow: hidden; }

.designer-sidebar {
  width: 200px; background: var(--card-bg); border-right: 1px solid var(--border-color);
  padding: 16px; overflow-y: auto;
}
.sidebar-title { font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 12px; font-weight: 600; }
.palette-item {
  display: flex; align-items: center; gap: 8px; padding: 10px 12px;
  background: var(--main-bg); border: 1px solid var(--border-color); border-radius: 8px;
  margin-bottom: 8px; cursor: grab; transition: all 0.15s; color: var(--text-color); font-size: 13px;
}
.palette-item:hover { border-color: var(--primary-color); background: var(--primary-light); }
.palette-icon { font-size: 18px; }

.designer-canvas { flex: 1; position: relative; overflow: auto; }
.canvas-bg {
  width: 100%; height: 100%; position: relative;
  background-color: var(--main-bg);
  background-image: radial-gradient(circle, var(--border-color) 1px, transparent 1px);
  background-size: 20px 20px;
}
.canvas-svg { position: absolute; inset: 0; pointer-events: none; z-index: 1; }

.canvas-node {
  position: absolute; z-index: 2; min-width: 160px;
  background: var(--card-bg); border: 2px solid var(--border-color); border-radius: 10px;
  cursor: move; transition: border-color 0.15s;
}
.canvas-node:hover { border-color: var(--primary-hover); }
.canvas-node.selected { border-color: var(--primary-color); box-shadow: 0 0 0 3px rgba(59,130,246,0.2); }
.canvas-node.node-start { border-color: var(--success-color); }
.canvas-node.node-end { border-color: var(--danger-color); }
.canvas-node.node-agent { border-color: var(--primary-color); }
.canvas-node.node-condition { border-color: var(--warning-color); }
.canvas-node.node-delay { border-color: var(--text-muted); }

.node-header { display: flex; align-items: center; gap: 6px; padding: 8px 12px; }
.node-icon { font-size: 16px; }
.node-label { font-size: 13px; font-weight: 600; color: var(--text-color); }
.node-preview { padding: 0 12px 8px; font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.node-ports { position: relative; }
.port {
  width: 12px; height: 12px; background: var(--main-bg); border: 2px solid var(--primary-color);
  border-radius: 50%; position: absolute; cursor: crosshair; z-index: 3;
}
.port:hover { background: var(--primary-color); transform: scale(1.3); }
.port-in { left: -6px; top: 50%; transform: translateY(-50%); }
.port-out { right: -6px; top: 50%; transform: translateY(-50%); }

.node-delete {
  position: absolute; top: -8px; right: -8px; width: 20px; height: 20px;
  background: var(--danger-color); color: #fff; border: none; border-radius: 50%;
  cursor: pointer; font-size: 14px; display: none; z-index: 4;
  align-items: center; justify-content: center; line-height: 1;
}
.canvas-node:hover .node-delete { display: flex; }

.designer-properties {
  width: 280px; background: var(--card-bg); border-left: 1px solid var(--border-color);
  overflow-y: auto;
}
.prop-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid var(--border-color);
}
.prop-title { font-size: 14px; font-weight: 600; color: var(--text-color); }
.prop-body { padding: 16px; }

:deep(.el-form-item__label) { color: var(--text-secondary); }
:deep(.el-input__wrapper) { background: var(--main-bg); border-color: var(--border-color); }
:deep(.el-textarea__inner) { background: var(--main-bg); border-color: var(--border-color); color: var(--text-color); }
</style>
