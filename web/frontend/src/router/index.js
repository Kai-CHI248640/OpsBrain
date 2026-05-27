import { createRouter, createWebHashHistory } from 'vue-router'

/**
 * 使用 hash 路由 (#/login, #/settings 等)
 * 避免 SPA 刷新时服务器返回 404
 */
const routes = [
  {
    path: '/setup',
    name: 'Setup',
    meta: { title: '初始化部署', guest: true },
    component: () => import('@/views/SetupView.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    meta: { title: '登录', guest: true },
    component: () => import('@/views/LoginView.vue'),
  },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    meta: { requiresAuth: true, title: 'OpsBrain' },
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        meta: { title: '控制台' },
        component: () => import('@/views/DashboardView.vue'),
      },
      {
        path: 'settings',
        name: 'Settings',
        meta: { title: '设置' },
        component: () => import('@/views/SettingsView.vue'),
      },
      {
        path: 'topology',
        name: 'TopologyList',
        meta: { title: '网络拓扑' },
        component: () => import('@/views/TopologyListView.vue'),
      },
      {
        path: 'topology/wizard',
        name: 'TopologyWizard',
        meta: { title: '拓扑嗅探' },
        component: () => import('@/views/TopologyView.vue'),
      },
      {
        path: 'topology/:id',
        name: 'TopologyDetail',
        meta: { title: '拓扑详情' },
        component: () => import('@/views/TopologyDetail.vue'),
      },
      {
        path: 'knowledge',
        name: 'KnowledgeBase',
        meta: { title: '知识库' },
        component: () => import('@/views/KnowledgeBaseView.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    meta: { title: '页面不存在' },
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
