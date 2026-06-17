<template>
  <div class="datasource-page">
    <header class="page-header">
      <h1>数据源管理</h1>
    </header>

    <!-- Upload Zone -->
    <div
      class="upload-zone"
      :class="{ 'drag-over': isDragOver, 'uploading': uploading }"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="handleDrop"
      @click="$refs.fileInput.click()"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".xlsx,.xls"
        class="hidden-input"
        @change="handleFileSelect"
      />
      <div class="upload-icon">&#x1F4C1;</div>
      <div class="upload-text">拖拽 Excel 文件到此处，或点击选择</div>
      <div class="upload-hint">支持 .xlsx / .xls 格式，上传后自动解析生成报表</div>
    </div>

    <!-- Upload progress -->
    <div v-if="uploading" class="upload-progress">
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
      </div>
      <div class="progress-info">
        <span>{{ uploadProgress < 100 ? '解析中...' : '解析完成，即将跳转' }}</span>
        <span class="progress-pct">{{ uploadProgress }}%</span>
      </div>
    </div>

    <!-- Upload error -->
    <div v-if="uploadError" class="upload-error">
      <span class="error-icon">&#x2717;</span>
      <span>{{ uploadError }}</span>
      <button class="btn-dismiss" @click="uploadError = ''">关闭</button>
    </div>

    <!-- Mapping Preview Modal -->
    <DataSourceMappingPreview
      :visible="showPreviewModal"
      :data="previewData"
      @cancel="handlePreviewCancel"
      @confirm="handleConfirmImport"
    />

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="datasource-list">
      <div
        v-for="ds in datasources"
        :key="ds.id"
        class="datasource-card"
      >
        <div class="ds-header">
          <h3>{{ ds.name }}</h3>
          <span class="status-badge" :class="ds.status">{{ ds.status === 'active' ? '活跃' : '未激活' }}</span>
        </div>
        <div class="ds-meta">
          <p>类型: {{ ds.type }}</p>
          <p>记录数: {{ ds.record_count || 0 }}</p>
          <p>最后更新: {{ formatDate(ds.last_updated) }}</p>
          <p>创建时间: {{ formatDate(ds.created_at) }}</p>
        </div>
        <div class="ds-actions">
          <button class="btn-refresh" @click="handleRefresh(ds.id)" :disabled="ds.refreshing">
            {{ ds.refreshing ? '刷新中...' : '刷新数据' }}
          </button>
          <button class="btn-delete" @click="handleDelete(ds.id)">删除</button>
        </div>
      </div>

      <div v-if="datasources.length === 0" class="empty">暂无数据源</div>
    </div>

    <!-- Edit form -->
    <div class="edit-form">
      <h3>编辑数据源</h3>
      <form @submit.prevent="handleSave">
        <div class="field">
          <label>名称</label>
          <input v-model="form.name" placeholder="数据源名称" required />
        </div>
        <div class="field">
          <label>类型</label>
          <select v-model="form.type">
            <option value="excel">Excel 文件</option>
            <option value="csv">CSV 文件</option>
            <option value="database">数据库</option>
            <option value="api">API 接口</option>
          </select>
        </div>
        <div class="field">
          <label>配置 (JSON)</label>
          <textarea v-model="form.configStr" rows="4" placeholder='{"path": "E:/data/complaints.xlsx"}'></textarea>
        </div>
        <button type="submit" class="btn-save">保存</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import apiClient from '@/api/client.js'
import { useReportStore } from '@/store/index.js'
import DataSourceMappingPreview from '@/components/DataSourceMappingPreview.vue'

const router = useRouter()
const reportStore = useReportStore()

const datasources = ref([])
const loading = ref(false)
const form = ref({
  name: '',
  type: 'excel',
  configStr: '',
})

// Upload state
const isDragOver = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')

// Preview state (两阶段上传)
const showPreviewModal = ref(false)
const previewData = ref({})

onMounted(async () => {
  await fetchDatasources()
})

async function fetchDatasources() {
  loading.value = true
  try {
    const { data } = await apiClient.get('/datasources')
    datasources.value = data
  } finally {
    loading.value = false
  }
}

async function handleRefresh(id) {
  const ds = datasources.value.find((d) => d.id === id)
  if (ds) ds.refreshing = true
  try {
    await apiClient.post(`/datasources/${id}/refresh`)
    await fetchDatasources()
  } finally {
    if (ds) ds.refreshing = false
  }
}

async function handleDelete(id) {
  const ds = datasources.value.find((d) => d.id === id)
  const name = ds ? ds.name : '此数据源'
  if (!confirm(`确定删除数据源「${name}」？\n\n关联的报表也会被一并删除。`)) return
  try {
    await apiClient.delete(`/datasources/${id}`)
    await fetchDatasources()
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

async function handleSave() {
  let config = {}
  if (form.value.configStr) {
    try {
      config = JSON.parse(form.value.configStr)
    } catch {
      alert('配置 JSON 格式错误')
      return
    }
  }
  await apiClient.post('/datasources', {
    name: form.value.name,
    type: form.value.type,
    config,
  })
  form.value = { name: '', type: 'excel', configStr: '' }
  await fetchDatasources()
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// ── Upload handlers ──────────────────────────────────────

function handleDrop(e) {
  isDragOver.value = false
  const file = e.dataTransfer.files[0]
  if (file) uploadFile(file)
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) uploadFile(file)
  // Reset input so the same file can be uploaded again
  e.target.value = ''
}

async function uploadFile(file) {
  if (!file.name.match(/\.(xlsx|xls)$/i)) {
    uploadError.value = '请上传 Excel 文件 (.xlsx / .xls)'
    return
  }

  uploading.value = true
  uploadProgress.value = 10
  uploadError.value = ''

  try {
    // 阶段1：上传获取预览
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post('/datasources/upload/preview', formData, {
      timeout: 60000,
      onUploadProgress: (e) => {
        uploadProgress.value = Math.round(e.loaded / e.total * 80)
      },
    })

    uploadProgress.value = 0
    uploading.value = false

    // 显示映射预览弹窗
    previewData.value = data
    showPreviewModal.value = true
  } catch (err) {
    uploadError.value = err.response?.data?.detail || err.message || '上传失败'
    uploading.value = false
    uploadProgress.value = 0
  }
}

function handlePreviewCancel() {
  showPreviewModal.value = false
  previewData.value = {}
}

async function handleConfirmImport(confirmedMapping) {
  uploading.value = true
  uploadProgress.value = 50

  try {
    const { data } = await apiClient.post('/datasources/upload/confirm', {
      temp_path: previewData.value.temp_path,
      filename: previewData.value.filename,
      field_mapping: confirmedMapping,
      datasource_name: previewData.value.filename.replace(/\.(xlsx|xls)$/i, ''),
    })

    uploadProgress.value = 100
    showPreviewModal.value = false
    previewData.value = {}
    await fetchDatasources()

    setTimeout(() => {
      router.push(`/reports/${data.report_id}`)
    }, 500)
  } catch (err) {
    uploadError.value = err.response?.data?.detail || err.message || '导入失败'
    showPreviewModal.value = false
  } finally {
    uploading.value = false
    setTimeout(() => { uploadProgress.value = 0 }, 1000)
  }
}
</script>

<style scoped>
.datasource-page {
  min-height: 100vh;
  padding: var(--space-2xl) var(--space-2xl);
  max-width: 1280px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: var(--space-xl);
}

.page-header h1 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
}

/* Upload Zone */
.upload-zone {
  border: 2px dashed var(--card-border);
  border-radius: var(--radius-lg);
  padding: var(--space-3xl) var(--space-2xl);
  text-align: center;
  cursor: pointer;
  background: var(--card-bg);
  transition: all var(--transition-base) var(--ease-out);
  margin-bottom: var(--space-xl);
}

.upload-zone:hover {
  border-color: var(--accent);
  background: rgba(79, 140, 247, 0.03);
}

.upload-zone.drag-over {
  border-color: var(--accent);
  background: rgba(79, 140, 247, 0.06);
  transform: scale(1.01);
  box-shadow: 0 0 24px var(--accent-glow);
}

.upload-zone.uploading {
  cursor: default;
  border-style: solid;
  border-color: var(--accent);
}

.hidden-input {
  display: none;
}

.upload-icon {
  font-size: var(--font-size-2xl);
  margin-bottom: var(--space-sm);
  opacity: 0.7;
}

.upload-text {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  color: var(--text);
  margin-bottom: var(--space-xs);
}

.upload-hint {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}

/* Upload Progress */
.upload-progress {
  margin-bottom: var(--space-lg);
  animation: fadeIn var(--transition-fast);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.progress-track {
  height: 4px;
  background: var(--bg-elevated);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: var(--space-xs);
}

.progress-fill {
  height: 100%;
  background: var(--gradient1);
  border-radius: var(--radius-full);
  transition: width var(--transition-slow) var(--ease-out);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.progress-pct {
  font-weight: var(--font-weight-semibold);
  color: var(--accent);
}

/* Upload Error */
.upload-error {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  background: rgba(255, 107, 107, 0.08);
  border: 1px solid rgba(255, 107, 107, 0.2);
  border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md);
  margin-bottom: var(--space-lg);
  font-size: var(--font-size-sm);
  color: var(--accent2);
  animation: fadeIn var(--transition-fast);
}

.error-icon {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-bold);
}

.btn-dismiss {
  margin-left: auto;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-sm);
}

.btn-dismiss:hover {
  color: var(--text);
  background: rgba(0, 0, 0, 0.04);
}

/* Loading */
.loading {
  text-align: center;
  padding: var(--space-3xl);
  color: var(--text-secondary);
}

/* Datasource List */
.datasource-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--space-md);
  margin-bottom: var(--space-2xl);
}

.datasource-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  transition: all var(--transition-base) var(--ease-out);
}

.datasource-card:hover {
  border-color: var(--card-border-hover);
  box-shadow: var(--card-shadow-hover);
}

.ds-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}

.ds-header h3 {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
}

.status-badge {
  font-size: var(--font-size-xs);
  padding: 2px var(--space-sm);
  border-radius: var(--radius-full);
}

.status-badge.active {
  background: rgba(0, 212, 100, 0.15);
  color: #00d464;
}

.status-badge.inactive {
  background: rgba(255, 100, 100, 0.15);
  color: #ff6464;
}

.ds-meta p {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: var(--space-xs) 0;
}

.ds-actions {
  display: flex;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.btn-refresh {
  background: var(--gradient1);
  color: white;
  font-size: var(--font-size-sm);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-refresh:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(79, 140, 247, 0.2);
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-delete {
  background: transparent;
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-delete:hover {
  border-color: var(--accent2);
  color: var(--accent2);
}

.btn-save {
  background: var(--gradient1);
  color: white;
  font-weight: var(--font-weight-semibold);
  padding: var(--space-sm) var(--space-lg);
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  font-size: var(--font-size-base);
  margin-top: var(--space-sm);
  transition: all var(--transition-fast);
}

.btn-save:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(79, 140, 247, 0.2);
}

/* Edit Form */
.edit-form {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  max-width: 600px;
}

.edit-form h3 {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-md);
}

.field {
  margin-bottom: var(--space-sm);
}

.field label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
}

.field input, .field select, .field textarea {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--card-border);
  color: var(--text);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: var(--font-size-base);
}

.field input:focus, .field select:focus, .field textarea:focus {
  outline: none;
  box-shadow: 0 0 0 3px var(--accent-glow);
  border-color: var(--accent);
}

.empty {
  text-align: center;
  padding: var(--space-3xl);
  color: var(--text-secondary);
  grid-column: 1 / -1;
}
</style>
