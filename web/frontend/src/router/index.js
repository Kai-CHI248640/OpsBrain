import { createRouter, createWebHashHistory } from 'vue-router'

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
        meta: { title: '设置', requiresRole: 'admin' },
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
        path: 'topology/tasks',
        name: 'TopologyTasks',
        meta: { title: '定时任务' },
        component: () => import('@/views/TaskList.vue'),
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

router.beforeEach(async (to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - OpsBrain` : 'OpsBrain'

  const requiresAuth = to.meta.requiresAuth
  const isGuest = to.meta.guest

  const token = localStorage.getItem('opsbrain-token')
  const savedUser = localStorage.getItem('opsbrain-user')

  if (isGuest) {
    if (token && savedUser) {
      next('/dashboard')
      return
    }
    next()
    return
  }

  if (requiresAuth && !token) {
    next('/login')
    return
  }

  if (to.meta.requiresRole && savedUser) {
    try {
      const user = JSON.parse(savedUser)
      if (user.role !== to.meta.requiresRole) {
        next('/dashboard')
        return
      }
    } catch {
      next('/dashboard')
      return
    }
  }

  next()
})

export default router