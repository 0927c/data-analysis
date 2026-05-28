<template>
  <div class="report-detail-page">
    <header class="page-header">
      <div>
        <button class="btn-back" @click="$router.push('/reports')">&#x2190; 返回列表</button>
        <h1>{{ report?.title || '报表详情' }}</h1>
      </div>
      <div class="header-actions">
        <button class="btn-export" @click="showExportModal = true" :disabled="!report">
          导出报表
        </button>
      </div>
    </header>

    <!-- Export progress bar -->
    <div v-if="reportStore.isExporting" class="export-progress">
      <div class="export-progress-bar" :style="{ width: reportStore.exportProgress + '%' }"></div>
    </div>

    <div v-if="loading" class="loading">
      <LoadingIndicator text="加载报表中..." skeleton :skeletonLines="5" />
    </div>

    <div v-else-if="!report" class="empty">报表不存在</div>

    <div v-else>
      <!-- Tab navigation -->
      <div class="report-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span class="tab-badge">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Charts tab -->
      <section v-show="activeTab === 'charts'" v-if="report.charts?.length" class="charts-section">
        <div
          v-for="(chart, idx) in report.charts"
          :key="idx"
          class="chart-block"
        >
          <div class="chart-header">
            <h3 class="chart-title">{{ chart.title }}</h3>
          </div>
          <div class="chart-wrapper">
            <ChartRenderer :option="chart.option" height="360px" />
          </div>
        </div>
      </section>

      <!-- Insights tab -->
      <section v-show="activeTab === 'insights'" v-if="report.insights?.length" class="insights-section">
        <div v-for="(insight, i) in report.insights" :key="i" class="insight-item" :class="'severity-' + (typeof insight === 'object' ? insight.severity : 'info')" :style="{ animationDelay: (i * 80) + 'ms' }">
          <span class="insight-severity-dot"></span>
          <div class="insight-content">
            <div class="insight-header">
              <span class="severity-badge" :class="typeof insight === 'object' ? insight.severity : 'info'">
                {{ severityLabel(typeof insight === 'object' ? insight.severity : 'info') }}
              </span>
              <span class="insight-title">{{ typeof insight === 'object' ? insight.title : String(insight) }}</span>
            </div>
            <p v-if="typeof insight === 'object' && insight.desc" class="insight-desc">{{ insight.desc }}</p>
          </div>
        </div>
      </section>

      <!-- Data tab -->
      <section v-show="activeTab === 'data'" v-if="report.data_table" class="table-section">
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th v-for="h in report.data_table.headers" :key="h">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in report.data_table.rows" :key="ri">
                <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- Export Modal -->
    <Teleport to="body">
      <div v-if="showExportModal" class="modal-overlay" @click.self="showExportModal = false">
        <div class="modal-content">
          <h2>导出报表</h2>
          <div class="modal-options">
            <label class="modal-option">
              <input type="checkbox" v-model="exportOpts.includeCharts" />
              <span>包含图表</span>
            </label>
            <label class="modal-option">
              <input type="checkbox" v-model="exportOpts.includeInsights" checked />
              <span>包含洞察建议</span>
            </label>
            <label class="modal-option">
              <input type="checkbox" v-model="exportOpts.includeData" checked />
              <span>包含数据明细</span>
            </label>
          </div>
          <div class="modal-preview">
            <span>预览：约 {{ previewCount }} 项内容</span>
          </div>
          <div class="modal-actions">
            <button class="btn-cancel" @click="showExportModal = false">取消</button>
            <button class="btn-html" @click="doExportHtml">导出 HTML</button>
            <button class="btn-excel" @click="doExportExcel">导出 Excel</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useReportStore } from '@/store/index.js'
import ChartRenderer from '@/components/ChartRenderer.vue'
import LoadingIndicator from '@/components/LoadingIndicator.vue'

const route = useRoute()
const reportStore = useReportStore()
const report = ref(null)
const loading = ref(false)
const activeTab = ref('charts')
const showExportModal = ref(false)
const exportOpts = ref({
  includeCharts: true,
  includeInsights: true,
  includeData: true,
})

const tabs = computed(() => {
  const r = report.value || {}
  return [
    { key: 'charts', label: '图表', count: (r.charts || []).length },
    { key: 'insights', label: '洞察', count: (r.insights || []).length },
    { key: 'data', label: '数据', count: (r.data_table?.rows || []).length },
  ]
})

const previewCount = computed(() => {
  let count = 0
  if (exportOpts.value.includeCharts) count += (report.value?.charts || []).length
  if (exportOpts.value.includeInsights) count += (report.value?.insights || []).length
  if (exportOpts.value.includeData) count += (report.value?.data_table?.rows || []).length
  return count
})

onMounted(async () => {
  loading.value = true
  try {
    await reportStore.fetchReport(route.params.id)
    const raw = reportStore.currentReport
    // Parse JSON strings from backend into usable objects
    report.value = {
      ...raw,
      charts: parseJSON(raw.chart_config, []),
      data_table: parseJSON(raw.data_payload, {}),
      insights: parseJSON(raw.insights, []),
    }
  } finally {
    loading.value = false
  }
})

function parseJSON(str, fallback) {
  if (!str) return fallback
  try { return JSON.parse(str) } catch { return fallback }
}

function severityLabel(sev) {
  const map = { critical: '严重', warning: '警告', info: '提示' }
  return map[sev] || sev || '提示'
}

async function doExportHtml() {
  showExportModal.value = false
  await reportStore.exportHtml(report.value.id)
}

async function doExportExcel() {
  showExportModal.value = false
  await reportStore.exportExcel(report.value.id)
}
</script>

<style scoped>
.report-detail-page {
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

.btn-back {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  cursor: pointer;
  margin-bottom: var(--space-sm);
  padding: var(--space-xs) 0;
  transition: color var(--transition-fast);
}

.btn-back:hover {
  color: var(--accent);
}

.page-header h1 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
}

.header-actions {
  display: flex;
  gap: var(--space-md);
  padding-top: var(--space-sm);
}

.btn-export {
  background: var(--gradient1);
  color: white;
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  box-shadow: 0 2px 8px rgba(0, 212, 255, 0.2);
  transition: all var(--transition-base) var(--ease-out);
}

.btn-export:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(0, 212, 255, 0.3);
}

.btn-export:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Export progress */
.export-progress {
  height: 3px;
  background: var(--card-bg);
  border-radius: var(--radius-full);
  margin-bottom: var(--space-lg);
  overflow: hidden;
}

.export-progress-bar {
  height: 100%;
  background: var(--gradient1);
  border-radius: var(--radius-full);
  transition: width var(--transition-slow) var(--ease-out);
}

.loading {
  text-align: center;
  padding: var(--space-3xl);
}

.empty {
  text-align: center;
  padding: var(--space-3xl) 0;
  color: var(--text-secondary);
}

/* Tabs */
.report-tabs {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-2xl);
  border-bottom: 1px solid var(--card-border);
  padding-bottom: 0;
}

.tab-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: var(--space-sm) var(--space-md);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  position: relative;
  border-radius: 0;
  transition: color var(--transition-fast);
}

.tab-btn:hover {
  color: var(--text);
  transform: none;
  box-shadow: none;
}

.tab-btn.active {
  color: var(--accent);
}

.tab-btn.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--accent);
}

.tab-badge {
  display: inline-block;
  font-size: var(--font-size-xs);
  background: rgba(0, 212, 255, 0.1);
  color: var(--accent);
  padding: 1px 6px;
  border-radius: var(--radius-full);
  margin-left: var(--space-xs);
  font-weight: var(--font-weight-normal);
}

/* Charts */
.charts-section {
  margin-bottom: var(--space-3xl);
}

.chart-block {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  margin-bottom: var(--space-xl);
  transition: border-color var(--transition-base);
}

.chart-header {
  margin-bottom: var(--space-md);
}

.chart-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
}

.chart-wrapper {
  border-radius: var(--radius-md);
  overflow: hidden;
}

/* Insights */
.insights-section {
  margin-bottom: var(--space-3xl);
}

.insight-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  margin-bottom: var(--space-sm);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  animation: insightSlideIn var(--transition-slow) var(--ease-out) both;
  background: rgba(0, 212, 255, 0.04);
  border: 1px solid var(--card-border);
  transition: border-color var(--transition-base);
}

.insight-item:hover {
  border-color: var(--accent);
}

.insight-item.severity-critical {
  border-left: 3px solid #ef4444;
  background: rgba(239, 68, 68, 0.04);
}

.insight-item.severity-warning {
  border-left: 3px solid #f59e0b;
  background: rgba(245, 158, 11, 0.04);
}

.insight-item.severity-info {
  border-left: 3px solid var(--accent);
  background: rgba(0, 212, 255, 0.04);
}

.insight-severity-dot {
  display: none;
}

.insight-content {
  flex: 1;
  min-width: 0;
}

.insight-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
}

.severity-badge {
  display: inline-block;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  letter-spacing: 0.02em;
}

.severity-badge.critical {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.severity-badge.warning {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.severity-badge.info {
  background: rgba(0, 212, 255, 0.12);
  color: var(--accent);
}

.insight-title {
  font-weight: var(--font-weight-semibold);
  color: var(--text);
  line-height: 1.4;
}

.insight-desc {
  margin: var(--space-xs) 0 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

@keyframes insightSlideIn {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

/* Table */
.table-section {
  margin-bottom: var(--space-3xl);
}

.table-wrapper {
  overflow-x: auto;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-lg);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: var(--space-sm) var(--space-lg);
  text-align: left;
  border-bottom: 1px solid var(--card-border);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

th {
  color: var(--text-secondary);
  font-weight: var(--font-weight-semibold);
  background: var(--bg-elevated);
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
}

tbody tr {
  transition: background var(--transition-fast);
}

tbody tr:hover {
  background: rgba(0, 212, 255, 0.04);
}

/* Export Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--bg-overlay);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  animation: fadeIn var(--transition-fast);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-content {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-xl);
  padding: var(--space-2xl);
  width: 400px;
  max-width: 90vw;
  animation: modalSlideIn var(--transition-base) var(--ease-out);
}

@keyframes modalSlideIn {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.modal-content h2 {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  margin-bottom: var(--space-lg);
}

.modal-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.modal-option {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-base);
  cursor: pointer;
  color: var(--text);
}

.modal-option input[type="checkbox"] {
  accent-color: var(--accent);
  width: 16px;
  height: 16px;
}

.modal-preview {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding: var(--space-sm) 0;
  border-top: 1px solid var(--card-border);
  border-bottom: 1px solid var(--card-border);
  margin-bottom: var(--space-lg);
}

.modal-actions {
  display: flex;
  gap: var(--space-sm);
  justify-content: flex-end;
}

.btn-cancel {
  background: transparent;
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-sm);
}

.btn-html {
  background: var(--card-bg);
  border: 1px solid var(--accent);
  color: var(--accent);
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-sm);
  font-weight: var(--font-weight-medium);
}

.btn-excel {
  background: var(--gradient1);
  color: white;
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-sm);
  font-weight: var(--font-weight-semibold);
}
</style>
