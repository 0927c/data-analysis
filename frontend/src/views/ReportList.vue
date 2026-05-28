<template>
  <div class="report-list-page">
    <header class="page-header">
      <div>
        <h1>报表中心</h1>
        <p class="page-subtitle">管理和查看历史分析报表</p>
      </div>
      <div class="header-actions">
        <div class="search-wrapper">
          <span class="search-icon">&#x1F50D;</span>
          <input
            v-model="search"
            class="search-input"
            placeholder="搜索报表..."
            @input="onSearch"
          />
        </div>
        <router-link to="/" class="btn-new">+ 新建报表</router-link>
      </div>
    </header>

    <!-- Filter chips -->
    <div class="filter-bar">
      <button
        v-for="chip in filterChips"
        :key="chip.value"
        class="filter-chip"
        :class="{ active: activeFilter === chip.value }"
        @click="setFilter(chip.value)"
      >
        {{ chip.label }}
      </button>
    </div>

    <div v-if="loading" class="loading">
      <LoadingIndicator text="加载报表中..." skeleton :skeletonLines="6" :skeletonWidths="['80%', '60%', '90%', '70%', '50%', '85%']" />
    </div>

    <div v-else-if="reports.length === 0" class="empty">
      <div class="empty-icon">📊</div>
      <p>暂无报表</p>
      <router-link to="/" class="btn-new">开始第一次对话</router-link>
    </div>

    <div v-else class="report-grid">
      <div
        v-for="report in reports"
        :key="report.id"
        class="report-card"
      >
        <div class="card-header">
          <h3 class="card-title">{{ report.title || '未命名报表' }}</h3>
          <button class="btn-delete" @click="handleDelete(report.id)">&times;</button>
        </div>
        <div class="card-meta">
          <span class="meta-tag">{{ report.datasource_name || '客诉数据' }}</span>
          <span class="meta-tag">{{ report.skill_name || '客诉分析' }}</span>
        </div>
        <div class="card-stats">
          <span>{{ report.chart_count || 0 }} 张图表</span>
          <span class="divider">&middot;</span>
          <span>{{ formatDate(report.created_at) }}</span>
        </div>
        <div class="card-actions">
          <router-link :to="`/reports/${report.id}`" class="btn-view">查看详情</router-link>
          <button class="btn-export" @click="exportHtml(report.id)">导出 HTML</button>
          <button class="btn-export" @click="exportExcel(report.id)">导出 Excel</button>
        </div>
      </div>
    </div>

    <div v-if="total > pageSize" class="pagination">
      <button :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页（共 {{ total }} 条）</span>
      <button :disabled="page * pageSize >= total" @click="goPage(page + 1)">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useReportStore } from '@/store/index.js'
import LoadingIndicator from '@/components/LoadingIndicator.vue'

const reportStore = useReportStore()
const reports = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const loading = ref(false)
const activeFilter = ref('all')

const totalPages = computed(() => Math.ceil(total.value / pageSize) || 1)

const filterChips = [
  { label: '全部', value: 'all' },
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
]

onMounted(async () => {
  await fetchReports()
})

async function fetchReports() {
  loading.value = true
  try {
    await reportStore.fetchReports(page.value, pageSize, search.value)
    reports.value = reportStore.reports
    total.value = reportStore.total
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  fetchReports()
}

function setFilter(value) {
  activeFilter.value = value
  page.value = 1
  fetchReports()
}

function goPage(p) {
  page.value = p
  fetchReports()
}

async function handleDelete(id) {
  if (!confirm('确定删除此报表？')) return
  await reportStore.deleteReport(id)
  await fetchReports()
}

async function exportHtml(id) {
  await reportStore.exportHtml(id)
}

async function exportExcel(id) {
  await reportStore.exportExcel(id)
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  // SQLite CURRENT_TIMESTAMP 返回 UTC 时间但无时区标记，需追加 'Z' 让 JS 按 UTC 解析后转本地时间
  const str = String(dateStr)
  const normalized = /[Zz]|[+-]\d{2}:?\d{2}$/.test(str) ? str : str + 'Z'
  return new Date(normalized).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}
</script>

<style scoped>
.report-list-page {
  min-height: 100vh;
  padding: var(--space-2xl) var(--space-2xl);
  max-width: 1280px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-2xl);
}

.page-header h1 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
}

.page-subtitle {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: var(--space-xs);
}

.header-actions {
  display: flex;
  gap: var(--space-lg);
  align-items: center;
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: var(--space-md);
  font-size: 14px;
  pointer-events: none;
  z-index: 1;
}

.search-input {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--text);
  padding: var(--space-sm) var(--space-md) var(--space-sm) 36px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  width: 220px;
  transition: all var(--transition-base) var(--ease-out);
}

.search-input:focus {
  width: 300px;
  box-shadow: 0 0 0 3px var(--accent-glow);
  border-color: var(--accent);
}

.btn-new {
  background: var(--gradient1);
  color: white;
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-md);
  text-decoration: none;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  box-shadow: 0 2px 8px rgba(0, 212, 255, 0.2);
  transition: all var(--transition-base) var(--ease-out);
}

.btn-new:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(0, 212, 255, 0.3);
}

/* Filter chips */
.filter-bar {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-2xl);
}

.filter-chip {
  background: transparent;
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-full);
  font-size: var(--font-size-sm);
  transition: all var(--transition-fast);
}

.filter-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.filter-chip.active {
  background: rgba(0, 212, 255, 0.1);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: var(--font-weight-medium);
}

.loading {
  padding: var(--space-3xl) 0;
}

.empty {
  text-align: center;
  padding: var(--space-3xl) 0;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--space-lg);
  opacity: 0.5;
}

.empty p {
  margin-bottom: var(--space-lg);
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-lg);
}

.report-card {
  position: relative;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  overflow: hidden;
  transition: all var(--transition-base) var(--ease-out);
}

.report-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--gradient1);
  transform: scaleX(0);
  transform-origin: center;
  transition: transform var(--transition-slow) var(--ease-out);
}

.report-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--card-shadow-hover);
  border-color: var(--card-border-hover);
}

.report-card:hover::before {
  transform: scaleX(1);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}

.card-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  flex: 1;
  line-height: var(--line-height-tight);
}

.btn-delete {
  background: transparent;
  color: var(--text-tertiary);
  font-size: 20px;
  padding: 0 var(--space-xs);
  line-height: 1;
  border-radius: var(--radius-full);
  transition: color var(--transition-fast);
}

.btn-delete:hover {
  color: var(--accent2);
  background: rgba(255, 107, 107, 0.1);
}

.card-meta {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
  flex-wrap: wrap;
}

.meta-tag {
  font-size: var(--font-size-xs);
  background: rgba(0, 212, 255, 0.08);
  color: var(--accent);
  padding: 2px var(--space-sm);
  border-radius: var(--radius-sm);
  font-weight: var(--font-weight-medium);
}

.card-stats {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-lg);
}

.divider {
  margin: 0 var(--space-xs);
}

.card-actions {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.btn-view, .btn-export {
  background: transparent;
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-decoration: none;
  transition: all var(--transition-fast);
}

.btn-view:hover, .btn-export:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: rgba(0, 212, 255, 0.05);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-lg);
  margin-top: var(--space-2xl);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
}

.pagination button {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--text);
  padding: var(--space-xs) var(--space-lg);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.pagination button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
