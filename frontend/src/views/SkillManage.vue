<template>
  <div class="skill-page">
    <header class="page-header">
      <h1>Skill 管理</h1>
    </header>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="skill-list">
      <div
        v-for="skill in skills"
        :key="skill.id"
        class="skill-card"
      >
        <div class="skill-header">
          <h3>{{ skill.name }}</h3>
          <label class="toggle-switch">
            <input type="checkbox" :checked="skill.enabled" @change="handleToggle(skill)" />
            <span class="slider">{{ skill.enabled ? '已启用' : '已禁用' }}</span>
          </label>
        </div>
        <p class="skill-desc">{{ skill.description }}</p>
        <div class="skill-meta">
          <span>数据源: {{ skill.datasource_name || '默认' }}</span>
          <span>图表: {{ (skill.supported_chart_types || []).join(', ') || '无' }}</span>
        </div>
      </div>

      <div v-if="skills.length === 0" class="empty">暂无 Skill</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import apiClient from '@/api/client.js'

const skills = ref([])
const loading = ref(false)

onMounted(async () => {
  await fetchSkills()
})

async function fetchSkills() {
  loading.value = true
  try {
    const { data } = await apiClient.get('/skills')
    skills.value = data
  } finally {
    loading.value = false
  }
}

async function handleToggle(skill) {
  const newEnabled = !skill.enabled
  await apiClient.put(`/skills/${skill.id}/toggle`, { enabled: newEnabled })
  skill.enabled = newEnabled
}
</script>

<style scoped>
.skill-page {
  min-height: 100vh;
  padding: 24px 40px;
  background: var(--bg);
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
}

.loading {
  text-align: center;
  padding: 48px;
  color: var(--text-secondary);
}

.skill-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.skill-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 20px;
}

.skill-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.skill-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.toggle-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
}

.toggle-switch input {
  display: none;
}

.slider {
  background: var(--bg);
  border: 1px solid var(--card-border);
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  transition: all 0.2s;
}

.toggle-switch input:checked + .slider {
  background: rgba(0, 212, 100, 0.15);
  border-color: #00d464;
  color: #00d464;
}

.skill-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  line-height: 1.5;
}

.skill-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

.empty {
  text-align: center;
  padding: 48px;
  color: var(--text-secondary);
  grid-column: 1 / -1;
}
</style>
