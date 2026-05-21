<template>
  <div class="login-page">
    <div class="login-card">
      <h1>智能报表分析 <span>Agent 平台</span></h1>
      <p class="subtitle">通过自然语言对话，自助生成数据分析报告</p>
      <form @submit.prevent="handleLogin">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="请输入用户名" required />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" required />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" class="btn-login" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/index.js'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(ellipse 60% 50% at 30% 60%, rgba(0, 212, 255, 0.06) 0%, transparent 70%),
    radial-gradient(ellipse 50% 40% at 70% 30%, rgba(155, 89, 182, 0.04) 0%, transparent 70%),
    var(--bg);
  animation: bgShift 8s ease-in-out infinite alternate;
}

@keyframes bgShift {
  0% { background-position: 0% 0%, 100% 100%, center; }
  100% { background-position: 10% 5%, 90% 95%, center; }
}

.login-card {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-2xl);
  padding: var(--space-3xl) var(--space-2xl);
  width: 420px;
  max-width: 90vw;
  text-align: center;
  animation: cardSlideIn 0.6s var(--ease-out);
}

@keyframes cardSlideIn {
  from { opacity: 0; transform: translateY(24px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.login-card h1 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
}

.login-card h1 span {
  background: var(--gradient1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  margin-top: var(--space-sm);
  margin-bottom: var(--space-2xl);
}

.field {
  text-align: left;
  margin-bottom: var(--space-lg);
}

.field label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
  font-weight: var(--font-weight-medium);
}

.field input {
  width: 100%;
  padding: var(--space-md);
  border-radius: var(--radius-md);
  background: rgba(26, 40, 55, 0.5);
  transition: all var(--transition-fast);
}

.field input:focus {
  box-shadow: 0 0 0 3px var(--accent-glow);
  background: rgba(26, 40, 55, 0.7);
}

.error {
  color: var(--accent2);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-md);
  text-align: left;
  padding: var(--space-sm) var(--space-md);
  background: rgba(255, 107, 107, 0.08);
  border-radius: var(--radius-sm);
}

.btn-login {
  width: 100%;
  padding: var(--space-md);
  background: var(--gradient1);
  color: white;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-md);
  margin-top: var(--space-sm);
  box-shadow: 0 4px 16px rgba(0, 212, 255, 0.3);
  transition: all var(--transition-base) var(--ease-out);
}

.btn-login:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(0, 212, 255, 0.4);
}

.btn-login:disabled {
  opacity: 0.6;
  transform: none;
  box-shadow: none;
}
</style>
