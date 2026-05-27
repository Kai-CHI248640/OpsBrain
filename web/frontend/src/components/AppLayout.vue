<template>
  <div class="app-layout" :class="{ 'is-dark': isDark }">
    <div v-if="isMobile && mobileOpen" class="mobile-overlay" @click="mobileOpen = false" />
    <aside class="app-sidebar" :class="{ 'mobile-sidebar': isMobile, 'sidebar-visible': isMobile && mobileOpen }" :style="isMobile ? {} : { width: desktopSidebarWidth }">
      <div class="sidebar-header">
        <span v-if="!collapsed" class="sidebar-title">OpsBrain</span>
        <el-button :icon="collapsed ? Expand : Fold" text @click="toggleCollapse" style="font-size: 18px" />
      </div>
      <el-menu :default-active="route.path" :collapse="collapsed" router class="sidebar-menu" @select="onMenuSelect">
        <el-menu-item index="/dashboard"><el-icon><Monitor /></el-icon><template #title>控制台</template></el-menu-item>
        <el-menu-item index="/topology"><el-icon><Connection /></el-icon><template #title>网络拓扑</template></el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon><template #title>设置</template></el-menu-item>
        <el-menu-item index="/knowledge"><el-icon><Collection /></el-icon><template #title>知识库</template></el-menu-item>
      </el-menu>
      <div v-if="!collapsed" class="sidebar-stats">
        <div class="stats-title">实时状态</div>
        <div class="stat-item clickable" @click="goTopologyList"><span class="stat-icon">🔗</span><span class="stat-label">拓扑</span><span class="stat-value">{{ stats.topology_count ?? '--' }}</span></div>
        <div class="stat-item" :class="{ 'has-warn': (stats.faulty_devices ?? 0) > 0 }"><span class="stat-icon">⚠️</span><span class="stat-label">故障设备</span><span class="stat-value">{{ stats.faulty_devices ?? '--' }}</span></div>
        <div class="stat-item"><span class="stat-icon">🌐</span><span class="stat-label">API</span><span class="stat-value">
          <el-tag v-if="!apiConfigured" size="small" type="info" effect="plain" class="status-tag">未配置</el-tag>
          <el-tag v-else-if="apiHealthy === null" size="small" type="warning" effect="plain" class="status-tag">检测中</el-tag>
          <el-tag v-else-if="apiHealthy" size="small" type="success" effect="plain" class="status-tag">正常</el-tag>
          <el-tag v-else size="small" type="danger" effect="plain" class="status-tag">异常</el-tag>
        </span></div>
        <div class="stat-item"><span class="stat-icon">🤖</span><span class="stat-label">Subagent</span><span class="stat-value">{{ stats.subagent_tasks?.working ?? 0 }}/{{ stats.subagent_tasks?.total ?? 0 }}</span></div>
      </div>
      <div class="sidebar-footer">
        <el-dropdown trigger="click" @command="handleCommand" placement="right">
          <div class="user-info"><el-avatar :size="28" style="background: #409eff">{{ (auth.user?.username || 'U').charAt(0).toUpperCase() }}</el-avatar><span v-if="!collapsed" class="user-name">{{ auth.user?.display_name || auth.user?.username || 'User' }}</span></div>
          <template #dropdown><el-dropdown-menu><el-dropdown-item command="profile"><el-icon><User /></el-icon> 个人信息</el-dropdown-item><el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon> 退出登录</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </aside>
    <div class="main-area">
      <header class="app-header">
        <div class="header-left"><el-button v-if="isMobile" :icon="Operation" text class="mobile-menu-btn" @click="mobileOpen = !mobileOpen" /><el-breadcrumb><el-breadcrumb-item to="/dashboard">OpsBrain</el-breadcrumb-item><el-breadcrumb-item v-if="route.meta?.title && route.path !== '/dashboard'">{{ route.meta.title }}</el-breadcrumb-item></el-breadcrumb></div>
        <div class="header-right"><el-tooltip :content="isDark ? '切换浅色' : '切换深色'" placement="bottom"><el-button :icon="isDark ? Sunny : Moon" circle text @click="toggleTheme" /></el-tooltip></div>
      </header>
      <main class="app-main"><router-view /></main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Fold, Expand, Monitor, Connection, Setting, User, SwitchButton, Sunny, Moon, Operation, Collection } from '@element-plus/icons-vue'
import { useAuthStore, api } from '@/stores/auth'

const route = useRoute(); const router = useRouter(); const auth = useAuthStore()
const collapsed = ref(false); const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')
const mobileOpen = ref(false); const isMobile = ref(window.innerWidth < 768)
function checkMobile() { isMobile.value = window.innerWidth < 768; if (!isMobile.value) mobileOpen.value = false }
const desktopSidebarWidth = computed(() => collapsed.value ? '64px' : '220px')

const stats = reactive({ topology_count: null, faulty_devices: null, api_status: null, subagent_tasks: { working: 0, idle: 0, total: 0 } })
const apiHealthy = ref(null); const apiConfigured = ref(false)
let pollTimer = null

async function fetchStats() { try { Object.assign(stats, (await api.get('/dashboard/stats')).data) } catch {} }
async function checkApiHealth() {
  try { const d = (await api.get('/dashboard/api-health')).data; apiConfigured.value = d.total > 0; apiHealthy.value = d.total > 0 ? d.unhealthy === 0 : null } catch { apiHealthy.value = false }
}
async function refreshAll() { await Promise.all([fetchStats(), checkApiHealth()]) }
function toggleCollapse() { collapsed.value = !collapsed.value }
function onMenuSelect() { if (isMobile.value) mobileOpen.value = false }
function goTopologyList() { router.push('/topology'); if (isMobile.value) mobileOpen.value = false }
onMounted(() => { refreshAll(); pollTimer = setInterval(refreshAll, 30000); window.addEventListener('resize', checkMobile) })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer); window.removeEventListener('resize', checkMobile) })
function toggleTheme() { isDark.value = !isDark.value; document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light'); localStorage.setItem('opsbrain-theme', isDark.value ? 'dark' : 'light') }
function handleCommand(cmd) { if (cmd === 'logout') { auth.logout(); ElMessage.success('已退出'); router.push('/login') } }
</script>

<style scoped>
.app-layout { display: flex; height: 100vh; background: var(--bg-color); }
.mobile-overlay { position: fixed; inset: 0; z-index: 998; background: rgba(0,0,0,0.5); animation: fadeIn .2s ease; }
@keyframes fadeIn { from{opacity:0} to{opacity:1} }
.app-sidebar { flex-shrink: 0; background: var(--sidebar-bg); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; overflow: hidden; z-index: 1; transition: width .25s ease; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 14px; border-bottom: 1px solid var(--border-color); height: 56px; flex-shrink: 0; }
.sidebar-title { font-size: 20px; font-weight: 800; color: #409eff; white-space: nowrap; letter-spacing: 2px; }
.sidebar-menu { border: none; padding: 8px 0; flex-shrink: 0; }
.sidebar-stats { flex: 1; padding: 8px 14px 12px; overflow-y: auto; border-top: 1px solid var(--border-color); min-height: 0; }
.stats-title { font-size: 11px; font-weight: 600; color: #909399; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.stat-item { display: flex; align-items: center; gap: 6px; padding: 6px 4px; border-radius: 6px; font-size: 13px; transition: background .15s; }
.stat-item:hover { background: #409eff10; } .stat-item.clickable { cursor: pointer; } .stat-item.clickable:hover .stat-value { color: #409eff; }
.stat-icon { font-size: 14px; width: 20px; text-align: center; flex-shrink: 0; }
.stat-label { color: var(--text-secondary,#909399); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat-value { font-weight: 700; font-size: 14px; color: var(--text-color); min-width: 20px; text-align: right; }
.stat-item.has-warn .stat-value { color: #f56c6c; animation: warnPulse 1.5s infinite; }
@keyframes warnPulse { 0%,100%{opacity:1} 50%{opacity:.5} } .status-tag { font-size: 10px; padding: 0 4px; line-height: 18px; height: 18px; }
.sidebar-footer { padding: 12px; border-top: 1px solid var(--border-color); flex-shrink: 0; }
.user-info { display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 4px; border-radius: 8px; transition: background .2s; }
.user-info:hover { background: #409eff15; } .user-name { font-size: 14px; color: var(--text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.main-area { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.app-header { display: flex; align-items: center; justify-content: space-between; padding: 0 24px; height: 56px; background: var(--header-bg); border-bottom: 1px solid var(--border-color); flex-shrink: 0; }
.mobile-menu-btn { margin-right: 8px; font-size: 20px; } .header-left { display: flex; align-items: center; min-width: 0; } .header-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.app-main { flex: 1; background: var(--main-bg); padding: 24px; overflow-y: auto; min-height: 0; }
@media (max-width:768px) {
  .app-sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: 220px; z-index: 999; transform: translateX(-100%); transition: transform .25s ease; box-shadow: none; }
  .app-sidebar.sidebar-visible { transform: translateX(0); box-shadow: 4px 0 16px rgba(0,0,0,.2); }
  .app-header { padding: 0 12px; height: 48px; } .sidebar-header { height: 48px; padding: 12px; } .sidebar-title { font-size: 18px; } .app-main { padding: 12px!important; }
}
</style>
