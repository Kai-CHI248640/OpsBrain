<template>
  <div class="app-layout" :class="{ 'is-dark': isDark }">
    <div v-if="isMobile && mobileOpen" class="mobile-overlay" @click="mobileOpen = false" />
    <aside class="app-sidebar" :class="{ 'mobile-sidebar': isMobile, 'sidebar-visible': isMobile && mobileOpen }" :style="isMobile ? {} : { width: desktopSidebarWidth }">
      <div class="sidebar-header">
        <div class="sidebar-brand" v-if="!collapsed">
          <div class="brand-icon">OB</div>
          <span class="sidebar-title">OpsBrain</span>
        </div>
        <div v-else class="sidebar-brand-collapsed">
          <div class="brand-icon">OB</div>
        </div>
        <el-button :icon="collapsed ? Expand : Fold" text @click="toggleCollapse" class="collapse-btn" />
      </div>

      <el-menu :default-active="route.path" :collapse="collapsed" router class="sidebar-menu" @select="onMenuSelect">
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <template #title>控制台</template>
        </el-menu-item>
        <el-sub-menu index="/topology">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>网络拓扑</span>
          </template>
          <el-menu-item index="/topology">拓扑列表</el-menu-item>
          <el-menu-item index="/topology/wizard">拓扑嗅探</el-menu-item>
          <el-menu-item index="/topology/tasks">定时任务</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon>
          <template #title>知识库</template>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>设置</template>
        </el-menu-item>
      </el-menu>

      <div v-if="!collapsed" class="sidebar-stats">
        <div class="stats-title">实时状态</div>
        <div class="stat-item clickable" @click="goTopologyList">
          <span class="stat-icon">🔗</span>
          <span class="stat-label">拓扑</span>
          <span class="stat-value">{{ stats.topology_count ?? '--' }}</span>
        </div>
        <div class="stat-item" :class="{ 'has-warn': (stats.faulty_devices ?? 0) > 0 }">
          <span class="stat-icon">⚠️</span>
          <span class="stat-label">故障</span>
          <span class="stat-value">{{ stats.faulty_devices ?? '--' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-icon">📡</span>
          <span class="stat-label">设备</span>
          <span class="stat-value">{{ stats.total_devices ?? '--' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-icon">🌐</span>
          <span class="stat-label">API</span>
          <span class="stat-value">
            <el-tag v-if="!apiConfigured" size="small" type="info" effect="plain" class="status-tag">未配置</el-tag>
            <el-tag v-else-if="apiHealthy === null" size="small" type="warning" effect="plain" class="status-tag">检测中</el-tag>
            <el-tag v-else-if="apiHealthy" size="small" type="success" effect="plain" class="status-tag">正常</el-tag>
            <el-tag v-else size="small" type="danger" effect="plain" class="status-tag">异常</el-tag>
          </span>
        </div>
      </div>

      <div class="sidebar-footer">
        <el-button text class="logout-btn" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span v-if="!collapsed">退出</span>
        </el-button>
      </div>
    </aside>

    <div class="main-area">
      <header class="app-header">
        <div class="header-left">
          <el-button v-if="isMobile" :icon="Operation" text class="mobile-menu-btn" @click="mobileOpen = !mobileOpen" />
          <el-breadcrumb>
            <el-breadcrumb-item to="/dashboard">OpsBrain</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta?.title && route.path !== '/dashboard'">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tooltip :content="isDark ? '切换浅色' : '切换深色'" placement="bottom">
            <el-button :icon="isDark ? Sunny : Moon" circle text class="theme-btn" @click="toggleTheme" />
          </el-tooltip>
        </div>
      </header>
      <main class="app-main"><router-view /></main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Fold, Expand, Monitor, Connection, Setting, SwitchButton, Sunny, Moon, Operation, Collection } from '@element-plus/icons-vue'
import { useAuthStore, api } from '@/stores/auth'

const route = useRoute(); const router = useRouter(); const auth = useAuthStore()
const collapsed = ref(false); const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')
const mobileOpen = ref(false); const isMobile = ref(window.innerWidth < 768)
function checkMobile() { isMobile.value = window.innerWidth < 768; if (!isMobile.value) mobileOpen.value = false }
const desktopSidebarWidth = computed(() => collapsed.value ? '64px' : '240px')

const stats = reactive({ topology_count: null, faulty_devices: null, api_status: null, total_devices: null })
const apiHealthy = ref(null); const apiConfigured = ref(false)
let pollTimer = null

async function fetchStats() { try { Object.assign(stats, await api.get('/dashboard/stats')) } catch {} }
async function checkApiHealth() {
  try {
    const d = await api.get('/dashboard/api-health')
    apiConfigured.value = d.total > 0
    apiHealthy.value = d.total > 0 ? d.unhealthy === 0 : null
  } catch {
    apiConfigured.value = stats.api_status?.configured ?? false
    apiHealthy.value = apiConfigured.value ? false : null
  }
}
async function refreshAll() { await Promise.all([fetchStats(), checkApiHealth()]) }
function toggleCollapse() { collapsed.value = !collapsed.value }
function onMenuSelect() { if (isMobile.value) mobileOpen.value = false }
function goTopologyList() { router.push('/topology'); if (isMobile.value) mobileOpen.value = false }
onMounted(() => { refreshAll(); pollTimer = setInterval(refreshAll, 30000); window.addEventListener('resize', checkMobile) })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer); window.removeEventListener('resize', checkMobile) })
function toggleTheme() { isDark.value = !isDark.value; document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light'); localStorage.setItem('opsbrain-theme', isDark.value ? 'dark' : 'light') }
function handleLogout() { auth.logout(); ElMessage.success('已退出'); router.push('/login') }
</script>

<style scoped>
.app-layout { display: flex; height: 100vh; background: var(--bg-color); }

.mobile-overlay { position: fixed; inset: 0; z-index: 998; background: rgba(0,0,0,0.5); backdrop-filter: blur(2px); animation: fadeIn .2s ease; }
@keyframes fadeIn { from{opacity:0} to{opacity:1} }

.app-sidebar {
  flex-shrink: 0; background: var(--sidebar-bg); border-right: 1px solid var(--border-color);
  display: flex; flex-direction: column; overflow: hidden; z-index: 1; transition: width .25s ease;
}

.sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 14px; border-bottom: 1px solid var(--border-color); height: 60px; flex-shrink: 0;
}

.sidebar-brand { display: flex; align-items: center; gap: 10px; }
.sidebar-brand-collapsed { display: flex; justify-content: center; width: 100%; }
.brand-icon {
  width: 32px; height: 32px; border-radius: 8px;
  background: linear-gradient(135deg, var(--primary-color), #8b5cf6);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 800; font-size: 12px; letter-spacing: -0.5px;
}
.sidebar-title { font-size: 18px; font-weight: 800; color: var(--text-color); letter-spacing: 1px; }
.collapse-btn { font-size: 16px; color: var(--text-secondary); }

.sidebar-menu { border: none; padding: 8px 8px; flex-shrink: 0; }
.sidebar-menu .el-menu-item {
  border-radius: var(--radius-sm); margin-bottom: 2px; height: 42px; line-height: 42px;
  color: var(--text-secondary); font-size: 14px; transition: all 0.15s;
}
.sidebar-menu .el-menu-item:hover {
  background: var(--primary-light); color: var(--primary-color);
}
.sidebar-menu .el-menu-item.is-active {
  background: var(--primary-light); color: var(--primary-color); font-weight: 600;
}

.sidebar-stats {
  flex: 1; padding: 12px 14px; overflow-y: auto; border-top: 1px solid var(--border-color); min-height: 0;
}
.stats-title { font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px; }
.stat-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 8px; border-radius: var(--radius-sm);
  font-size: 13px; transition: background .15s; margin-bottom: 2px;
}
.stat-item:hover { background: var(--primary-light); }
.stat-item.clickable { cursor: pointer; }
.stat-item.clickable:hover .stat-value { color: var(--primary-color); }
.stat-icon { font-size: 14px; width: 20px; text-align: center; flex-shrink: 0; }
.stat-label { color: var(--text-secondary); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 13px; }
.stat-value { font-weight: 700; font-size: 13px; color: var(--text-color); min-width: 20px; text-align: right; }
.stat-item.has-warn .stat-value { color: var(--danger-color); animation: warnPulse 1.5s infinite; }
@keyframes warnPulse { 0%,100%{opacity:1} 50%{opacity:.5} }
.status-tag { font-size: 10px; padding: 0 6px; line-height: 18px; height: 18px; }

.sidebar-footer { padding: 12px; border-top: 1px solid var(--border-color); flex-shrink: 0; }
.logout-btn { color: var(--text-secondary); font-size: 13px; width: 100%; justify-content: flex-start; }
.logout-btn:hover { color: var(--danger-color); background: var(--danger-light); }

.main-area { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; }

.app-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 56px; background: var(--header-bg);
  border-bottom: 1px solid var(--border-color); flex-shrink: 0;
}
.mobile-menu-btn { margin-right: 8px; font-size: 20px; color: var(--text-secondary); }
.header-left { display: flex; align-items: center; min-width: 0; }
.header-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.theme-btn { font-size: 18px; color: var(--text-secondary); }

.app-main { flex: 1; background: var(--main-bg); padding: 24px; overflow-y: auto; min-height: 0; }

@media (max-width:768px) {
  .app-sidebar {
    position: fixed; left: 0; top: 0; bottom: 0; width: 260px; z-index: 999;
    transform: translateX(-100%); transition: transform .25s ease; box-shadow: none;
  }
  .app-sidebar.sidebar-visible { transform: translateX(0); box-shadow: var(--shadow-lg); }
  .app-header { padding: 0 12px; height: 48px; }
  .sidebar-header { height: 48px; padding: 12px; }
  .sidebar-title { font-size: 16px; }
  .app-main { padding: 12px !important; }
}
</style>
