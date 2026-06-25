<template>
  <nav class="page-nav-bar">
    <div class="nav-left">
      <router-link to="/" class="nav-home" title="返回对话首页">
        <span class="nav-logo">Mi</span>
        <span class="nav-title">ITSM 智能分析</span>
      </router-link>
    </div>
    <div class="nav-links">
      <router-link to="/" class="nav-link" active-class="active">
        <span class="nav-icon">💬</span> 对话分析
      </router-link>
      <router-link to="/reports" class="nav-link" active-class="active">
        <span class="nav-icon">📊</span> 我的报表
      </router-link>
      <router-link v-if="isAdmin" to="/admin/datasources" class="nav-link" active-class="active">
        <span class="nav-icon">🗂️</span> 数据源
      </router-link>
      <router-link v-if="isAdmin" to="/admin/skills" class="nav-link" active-class="active">
        <span class="nav-icon">🔧</span> Skills
      </router-link>
    </div>
    <div class="nav-right">
      <span class="nav-user">{{ displayName }}</span>
      <button class="btn-logout-nav" @click="handleLogout">退出</button>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/index.js'

const router = useRouter()
const authStore = useAuthStore()

const isAdmin = computed(() => authStore.user?.role === 'admin')
const displayName = computed(() => authStore.user?.display_name || authStore.user?.username || '')

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.page-nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: var(--card-bg, #fff);
  border-bottom: 1px solid var(--card-border, #e5e7eb);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left {
  display: flex;
  align-items: center;
}

.nav-home {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--text, #111);
  font-weight: 600;
  font-size: 15px;
}

.nav-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #4f8cf7, #6366f1);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.nav-title {
  white-space: nowrap;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  text-decoration: none;
  color: var(--text-secondary, #6b7280);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.nav-link:hover {
  background: rgba(79, 140, 247, 0.08);
  color: var(--accent, #4f8cf7);
}

.nav-link.active {
  background: rgba(79, 140, 247, 0.12);
  color: var(--accent, #4f8cf7);
  font-weight: 600;
}

.nav-icon {
  font-size: 15px;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-user {
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}

.btn-logout-nav {
  padding: 5px 14px;
  border: 1px solid var(--card-border, #e5e7eb);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-logout-nav:hover {
  border-color: #ff6464;
  color: #ff6464;
  background: rgba(255, 100, 100, 0.06);
}
</style>
