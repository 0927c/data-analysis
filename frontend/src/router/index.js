import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/index.js'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'Chat',
    component: () => import('@/views/Chat.vue'),
  },
  {
    path: '/reports',
    name: 'ReportList',
    component: () => import('@/views/ReportList.vue'),
  },
  {
    path: '/reports/:id',
    name: 'ReportDetail',
    component: () => import('@/views/ReportDetail.vue'),
  },
  {
    path: '/admin/datasources',
    name: 'DataSourceManage',
    component: () => import('@/views/DataSourceManage.vue'),
    meta: { admin: true },
  },
  {
    path: '/admin/skills',
    name: 'SkillManage',
    component: () => import('@/views/SkillManage.vue'),
    meta: { admin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.public) return

  const auth = useAuthStore()
  if (!auth.isLoggedIn) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (to.meta.admin && auth.user?.role !== 'admin') {
    return { name: 'Chat' }
  }
})

export default router
