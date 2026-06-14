<template>
  <div class="topo-graph" ref="containerRef" @dblclick.self="resetView">
    <!-- Controls -->
    <div class="graph-controls">
      <el-tooltip content="还原视角" placement="left">
        <el-button size="small" circle @click="fitView" :icon="ZoomOut" />
      </el-tooltip>
      <el-tooltip content="力导向重排" placement="left">
        <el-button size="small" circle @click="restartPhysics" :icon="Refresh" />
      </el-tooltip>
      <el-tooltip content="导出 PNG" placement="left">
        <el-button size="small" circle @click="exportPNG" :icon="Download" />
      </el-tooltip>
    </div>

    <!-- Info popup -->
    <div v-if="selectedNode" class="node-popup" :style="popupStyle">
      <div class="popup-header">
        <span class="popup-icon">{{ deviceIcon(selectedNode.type) }}</span>
        <strong>{{ selectedNode.label }}</strong>
        <el-button text size="small" @click="selectedNode = null">&times;</el-button>
      </div>
      <div class="popup-body">
        <div class="popup-row"><span>IP</span><span>{{ selectedNode.ip || '—' }}</span></div>
        <div class="popup-row"><span>厂商</span><span>{{ selectedNode.vendor || '—' }}</span></div>
        <div class="popup-row"><span>类型</span><span>{{ typeLabel(selectedNode.type) }}</span></div>
        <div class="popup-row"><span>状态</span><span :style="{ color: statusColor(selectedNode.status) }">
          {{ selectedNode.status === 'online' ? '在线' : selectedNode.status === 'offline' ? '离线' : '未知' }}
        </span></div>
        <div class="popup-row"><span>连接</span><span>{{ selectedNode.connectionCount || 0 }} 条链路</span></div>
      </div>
      <div class="popup-actions">
        <el-button size="small" @click="focusNode(selectedNode.id)">聚焦</el-button>
        <el-button size="small" type="primary" @click="$emit('device-click', selectedNode)">详情</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ZoomOut, Refresh, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  links: { type: Array, default: () => [] },
})

const emit = defineEmits(['device-click', 'node-moved'])

const containerRef = ref(null)
let network = null
let nodesDataset = null
let edgesDataset = null

const selectedNode = ref(null)
const popupStyle = ref({})

// ── 颜色方案 ──────────────────────────────────────────
function isDark() {
  return document.documentElement.getAttribute('data-theme') === 'dark'
}

function getTheme() {
  const dark = isDark()
  return {
    bg: dark ? '#1e293b' : '#f1f5f9',
    nodeColors: {
      router: '#3b82f6',
      switch: '#10b981',
      firewall: '#f59e0b',
      server: '#8b5cf6',
      ap: '#ec4899',
      unknown: '#94a3b8',
    },
    edgeColor: dark ? '#94a3b8' : '#94a3b8',
    edgeHighlight: dark ? '#e2e8f0' : '#334155',
    fontColor: dark ? '#f1f5f9' : '#0f172a',
    glowColor: dark ? 'rgba(96, 165, 250, 0.15)' : 'rgba(59, 130, 246, 0.1)',
  }
}

// ── 设备图标 SVG ──────────────────────────────────────────
function deviceIconSvg(type, color) {
  const icons = {
    router: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="${color}"/><text x="32" y="42" text-anchor="middle" font-size="28" fill="white">🌐</text></svg>`,
    switch: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="${color}"/><text x="32" y="42" text-anchor="middle" font-size="28" fill="white">🔀</text></svg>`,
    firewall: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="${color}"/><text x="32" y="42" text-anchor="middle" font-size="28" fill="white">🛡️</text></svg>`,
    server: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="${color}"/><text x="32" y="42" text-anchor="middle" font-size="28" fill="white">🖥️</text></svg>`,
    ap: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="${color}"/><text x="32" y="42" text-anchor="middle" font-size="28" fill="white">📶</text></svg>`,
    unknown: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="${color}"/><text x="32" y="44" text-anchor="middle" font-size="32" font-weight="bold" fill="white">?</text></svg>`,
  }
  return icons[type] || icons.unknown
}

function deviceIcon(type) {
  return { router: '🌐', switch: '🔀', firewall: '🛡️', server: '🖥️', ap: '📶', unknown: '❓' }[type] || '❓'
}

function typeLabel(type) {
  return { router: '路由器', switch: '交换机', firewall: '防火墙', server: '服务器', ap: '无线AP', unknown: '未知' }[type] || type
}

function statusColor(status) {
  return { online: '#a6e3a1', offline: '#f38ba8', unknown: '#6c7086' }[status] || '#6c7086'
}

function makeIconImage(type, color) {
  const svg = deviceIconSvg(type, color)
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

// ── 初始化 vis-network ─────────────────────────────────────────────
function initNetwork() {
  if (!containerRef.value) return

  const THEME = getTheme()
  const nodeColors = THEME.nodeColors

  const visNodes = props.nodes.map(n => {
    const type = n.type || 'unknown'
    const color = nodeColors[type] || nodeColors.unknown
    return {
      id: n.name || n.id,
      label: n.name || '?',
      title: `${n.name}\n${n.ip || ''}`,
      shape: 'image',
      image: makeIconImage(type, color),
      size: nodeSize(n),
      font: {
        color: THEME.fontColor,
        size: 12,
        face: 'sans-serif',
        strokeWidth: 3,
        strokeColor: THEME.bg,
      },
      borderWidth: 0,
      borderWidthSelected: 0,
      deviceType: type,
      deviceIp: n.ip || '',
      deviceVendor: n.vendor || '',
      deviceStatus: n.status || 'unknown',
      connectionCount: 0,
    }
  })

  const visEdges = props.links.map(l => ({
    from: l.source,
    to: l.target,
    label: l.sourcePort ? `${l.sourcePort || ''}` : '',
    color: {
      color: THEME.edgeColor,
      highlight: THEME.edgeHighlight,
      hover: THEME.edgeHighlight,
      opacity: 0.6,
    },
    width: l.confirmed ? 2 : 1.5,
    dashes: l.confirmed ? false : [6, 4],
    smooth: {
      type: 'curvedCW',
      roundness: 0.15,
    },
    font: {
      color: THEME.fontColor,
      size: 10,
      strokeWidth: 2,
      strokeColor: THEME.bg,
      align: 'middle',
    },
    chosen: false,
  }))

  nodesDataset = new DataSet(visNodes)
  edgesDataset = new DataSet(visEdges)

  // Update connection counts
  const counts = {}
  visEdges.forEach(e => {
    counts[e.from] = (counts[e.from] || 0) + 1
    counts[e.to] = (counts[e.to] || 0) + 1
  })
  nodesDataset.forEach(n => {
    nodesDataset.update({ id: n.id, connectionCount: counts[n.id] || 0 })
  })

  const options = {
    // ── Obsidian-like physics ──
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -60,
        centralGravity: 0.005,
        springLength: 200,
        springConstant: 0.05,
        damping: 0.5,
      },
      stabilization: {
        iterations: 100,
        updateInterval: 20,
        onlyDynamicEdges: false,
        fit: true,
      },
      maxVelocity: 30,
      minVelocity: 0.5,
    },

    // ── Layout ──
    layout: {
      improvedLayout: true,
      clusterThreshold: 150,
    },

    // ── Interaction ──
    interaction: {
      dragNodes: true,
      dragView: true,
      zoomView: true,
      hover: true,
      tooltipDelay: 200,
      hideEdgesOnDrag: false,
      hideEdgesOnZoom: false,
      selectable: true,
      selectConnectedEdges: false,
      hoverConnectedEdges: true,
      keyboard: true,
      navigationButtons: false,
    },

    // ── Visual ──
    nodes: {
      shape: 'dot',
      scaling: {
        min: 15,
        max: 50,
      },
      shadow: {
        enabled: true,
        color: THEME.glowColor,
        size: 8,
        x: 0,
        y: 0,
      },
    },
    edges: {
      arrows: { to: { enabled: false }, from: { enabled: false } },
    },

    // ── Groups ──
    groups: {
      router: { color: { background: THEME.nodeColors.router, border: THEME.nodeColors.router } },
      switch: { color: { background: THEME.nodeColors.switch, border: THEME.nodeColors.switch } },
      firewall: { color: { background: THEME.nodeColors.firewall, border: THEME.nodeColors.firewall } },
      server: { color: { background: THEME.nodeColors.server, border: THEME.nodeColors.server } },
      ap: { color: { background: THEME.nodeColors.ap, border: THEME.nodeColors.ap } },
      unknown: { color: { background: THEME.nodeColors.unknown, border: THEME.nodeColors.unknown } },
    },

    // ── Background ──
    background: {
      color: THEME.bg,
    },
  }

  network = new Network(containerRef.value, { nodes: nodesDataset, edges: edgesDataset }, options)

  // ── Events ──
  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      showNodePopup(nodeId, params.pointer.DOM)
    } else {
      selectedNode.value = null
    }
  })

  network.on('doubleClick', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const nodeData = nodesDataset.get(nodeId)
      emit('device-click', {
        id: nodeId,
        name: nodeData.label,
        type: nodeData.deviceType,
        ip: nodeData.deviceIp,
        vendor: nodeData.deviceVendor,
        status: nodeData.deviceStatus,
      })
    }
  })

  network.on('hoverNode', (params) => {
    document.body.style.cursor = 'pointer'
  })

  network.on('blurNode', () => {
    document.body.style.cursor = 'default'
  })

  network.on('dragEnd', () => {
    // Resume physics after drag
    if (network) {
      setTimeout(() => {
        if (network) network.setOptions({ physics: { enabled: true } })
      }, 2000)
    }
  })
}

function nodeSize(n) {
  const sizes = { router: 30, switch: 25, firewall: 28, server: 22, ap: 20, unknown: 18 }
  return sizes[n.type] || 18
}

function showNodePopup(nodeId, pos) {
  const nodeData = nodesDataset.get(nodeId)
  if (!nodeData) return

  selectedNode.value = {
    id: nodeId,
    label: nodeData.label,
    type: nodeData.deviceType,
    ip: nodeData.deviceIp,
    vendor: nodeData.deviceVendor,
    status: nodeData.deviceStatus,
    connectionCount: nodeData.connectionCount,
  }

  // Position popup near clicked node
  const rect = containerRef.value?.getBoundingClientRect()
  if (rect) {
    popupStyle.value = {
      left: Math.min(pos.x - rect.left + 20, rect.width - 220) + 'px',
      top: Math.max(pos.y - rect.top - 50, 10) + 'px',
    }
  }
}

function focusNode(nodeId) {
  if (!network) return
  network.focus(nodeId, { scale: 1.5, animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
  // Highlight connected
  network.selectNodes([nodeId], false)
  // Dim others
  const connected = network.getConnectedNodes(nodeId)
  const allNodes = nodesDataset.getIds()
  allNodes.forEach(id => {
    if (id !== nodeId && !connected.includes(id)) {
      nodesDataset.update({ id, opacity: 0.3 })
    } else {
      nodesDataset.update({ id, opacity: 1.0 })
    }
  })
  setTimeout(() => {
    allNodes.forEach(id => nodesDataset.update({ id, opacity: 1.0 }))
  }, 3000)
}

function resetView() {
  selectedNode.value = null
  if (network) network.unselectAll()
  fitView()
}

function fitView() {
  if (network) network.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
}

function restartPhysics() {
  if (!network) return
  network.setOptions({ physics: { enabled: true } })
  network.stabilize(100)
}

function exportPNG() {
  if (!network) return
  const canvas = containerRef.value?.querySelector('canvas')
  if (!canvas) return
  const link = document.createElement('a')
  link.download = 'topology.png'
  link.href = canvas.toDataURL('image/png')
  link.click()
  ElMessage.success('拓扑图已导出')
}

// ── Watchers ──
watch(() => [props.nodes, props.links], () => {
  // Rebuild on data change (simple approach: destroy and recreate)
  if (network) {
    network.destroy()
    network = null
  }
  nextTick(() => initNetwork())
}, { deep: true })

// Watch for theme changes — update colors without rebuilding
const themeObserver = new MutationObserver(() => {
  if (!network || !nodesDataset || !edgesDataset) return
  const THEME = getTheme()
  // Update all node images with new theme colors
  nodesDataset.forEach(node => {
    const type = node.deviceType || 'unknown'
    const color = THEME.nodeColors[type] || THEME.nodeColors.unknown
    nodesDataset.update({
      id: node.id,
      image: makeIconImage(type, color),
      font: { ...node.font, color: THEME.fontColor, strokeColor: THEME.bg },
    })
  })
  // Update edges
  edgesDataset.forEach(edge => {
    edgesDataset.update({
      id: edge.id,
      color: { color: THEME.edgeColor, highlight: THEME.edgeHighlight, hover: THEME.edgeHighlight, opacity: 0.6 },
      font: { ...edge.font, color: THEME.fontColor, strokeColor: THEME.bg },
    })
  })
  // Update canvas background
  network.setOptions({ background: { color: THEME.bg } })
})

onMounted(() => {
  nextTick(() => initNetwork())
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onBeforeUnmount(() => {
  themeObserver.disconnect()
  if (network) {
    network.destroy()
    network = null
  }
})

// Expose methods for parent
defineExpose({ fitView, restartPhysics, resetView })
</script>

<style scoped>
.topo-graph {
  position: relative;
  width: 100%;
  height: 500px;
  background: var(--main-bg);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.graph-controls {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}

.graph-controls :deep(.el-button) {
  background: var(--card-bg);
  border-color: var(--border-color);
  color: var(--text-color);
  backdrop-filter: blur(4px);
}

.graph-controls :deep(.el-button:hover) {
  background: var(--border-color);
  border-color: var(--text-muted);
  color: var(--text-color);
}

/* ── Node popup ── */
.node-popup {
  position: absolute;
  z-index: 20;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
  width: 200px;
  backdrop-filter: blur(8px);
  box-shadow: var(--shadow-lg);
}

.popup-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-color);
  font-size: 13px;
}

.popup-header .el-button {
  margin-left: auto;
  color: var(--text-muted);
}

.popup-icon { font-size: 18px; }

.popup-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.popup-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-secondary);
}

.popup-row span:first-child { color: var(--text-muted); }

.popup-actions {
  display: flex;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

.popup-actions :deep(.el-button) {
  font-size: 11px;
  padding: 4px 10px;
  flex: 1;
}

/* ── 移动端 ── */
@media (max-width: 768px) {
  .topo-graph { height: 350px; }
  .node-popup { width: 160px; padding: 8px; }
  .graph-controls { top: 8px; right: 8px; }
  .graph-controls :deep(.el-button) { width: 28px; height: 28px; }
}
</style>
