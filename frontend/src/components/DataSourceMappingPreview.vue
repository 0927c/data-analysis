<template>
  <div class="mapping-preview-overlay" v-if="visible" @click.self="$emit('cancel')">
    <div class="mapping-preview-modal">
      <header class="modal-header">
        <h2>字段映射确认</h2>
        <p class="subtitle">系统已自动识别字段映射，请检查并调整。低置信度映射标有 ⚠️。</p>
        <button class="btn-close" @click="$emit('cancel')">&times;</button>
      </header>

      <!-- 文件信息 -->
      <div class="file-info">
        <span class="file-name">{{ data.filename }}</span>
        <span class="file-rows">共 {{ data.total_rows }} 行</span>
      </div>

      <!-- 告警 -->
      <div v-if="data.warnings && data.warnings.length" class="warnings-section">
        <div v-for="(w, i) in data.warnings" :key="i" class="warning-item">
          <span class="warn-icon">⚠️</span> {{ w }}
        </div>
      </div>

      <!-- 映射表 -->
      <div class="mapping-table-wrapper">
        <table class="mapping-table">
          <thead>
            <tr>
              <th class="col-source">Excel 列名</th>
              <th class="col-arrow"></th>
              <th class="col-target">映射到系统字段</th>
              <th class="col-confidence">置信度</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(col, idx) in mappingList" :key="idx"
                :class="{ 'low-confidence': col.confidence < 0.8 && col.field, 'unmapped': !col.field }">
              <td class="col-source">
                <span class="source-name">{{ col.source }}</span>
                <span class="col-type">{{ getColumnStat(col.source, 'dtype') }}</span>
              </td>
              <td class="col-arrow">→</td>
              <td class="col-target">
                <select v-model="col.field" class="field-select">
                  <option value="">-- 跳过此列 --</option>
                  <option v-for="f in data.available_fields" :key="f.key" :value="f.key">
                    {{ f.label }}
                  </option>
                </select>
              </td>
              <td class="col-confidence">
                <span v-if="col.field" class="confidence-badge" :class="confidenceClass(col.confidence)">
                  {{ Math.round(col.confidence * 100) }}%
                </span>
                <span v-else class="confidence-skip">跳过</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 样本数据预览 -->
      <div v-if="data.sample_data && data.sample_data.length" class="sample-section">
        <h3>数据预览（前 {{ Math.min(3, data.sample_data.length) }} 行）</h3>
        <div class="sample-table-wrapper">
          <table class="sample-table">
            <thead>
              <tr>
                <th v-for="col in mappedColumns" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in data.sample_data.slice(0, 3)" :key="ri">
                <td v-for="col in mappedColumns" :key="col">{{ row[col] || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 操作按钮 -->
      <footer class="modal-footer">
        <button class="btn-cancel" @click="$emit('cancel')">取消</button>
        <button class="btn-confirm" @click="handleConfirm" :disabled="confirming">
          {{ confirming ? '导入中...' : '确认导入' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  visible: Boolean,
  data: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['cancel', 'confirm'])
const confirming = ref(false)

const mappingList = computed(() => {
  if (!props.data.suggested_mapping) return []
  return Object.entries(props.data.suggested_mapping).map(([source, info]) => ({
    source,
    field: info.field || '',
    confidence: info.confidence || 0,
  }))
})

const mappedColumns = computed(() => {
  return mappingList.value.filter(m => m.field).map(m => m.source)
})

function getColumnStat(col, key) {
  if (!props.data.column_stats || !props.data.column_stats[col]) return ''
  const stat = props.data.column_stats[col]
  if (key === 'dtype') return stat.dtype || ''
  return ''
}

function confidenceClass(confidence) {
  if (confidence >= 0.9) return 'high'
  if (confidence >= 0.7) return 'medium'
  return 'low'
}

async function handleConfirm() {
  confirming.value = true
  const confirmedMapping = {}
  for (const item of mappingList.value) {
    if (item.field) {
      confirmedMapping[item.source] = item.field
    }
  }
  emit('confirm', confirmedMapping)
  // 不在这里重置 confirming，由父组件控制
}
</script>

<style scoped>
.mapping-preview-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.mapping-preview-modal {
  background: var(--card-bg, #fff);
  border-radius: 12px;
  width: 90vw;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

.modal-header {
  padding: 20px 24px 12px;
  border-bottom: 1px solid var(--card-border, #e5e7eb);
  position: relative;
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
  margin: 4px 0 0;
}

.btn-close {
  position: absolute;
  top: 16px; right: 16px;
  background: none;
  border: none;
  font-size: 24px;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  width: 32px; height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.btn-close:hover {
  background: rgba(0, 0, 0, 0.06);
}

.file-info {
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  background: rgba(79, 140, 247, 0.04);
}

.file-name {
  font-weight: 600;
  color: var(--text, #111);
}

.file-rows {
  color: var(--text-secondary, #6b7280);
}

.warnings-section {
  padding: 8px 24px;
}

.warning-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #b45309;
  padding: 4px 0;
}

.warn-icon {
  font-size: 14px;
}

.mapping-table-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px;
  max-height: 300px;
}

.mapping-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.mapping-table th {
  text-align: left;
  padding: 8px 8px;
  font-weight: 600;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 2px solid var(--card-border, #e5e7eb);
  position: sticky;
  top: 0;
  background: var(--card-bg, #fff);
}

.mapping-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--card-border, #e5e7eb);
  vertical-align: middle;
}

.mapping-table tr.low-confidence {
  background: rgba(251, 191, 36, 0.06);
}

.mapping-table tr.unmapped {
  opacity: 0.6;
}

.col-source {
  width: 35%;
}

.col-arrow {
  width: 30px;
  text-align: center;
  color: var(--text-secondary, #6b7280);
}

.col-target {
  width: 40%;
}

.col-confidence {
  width: 80px;
  text-align: center;
}

.source-name {
  font-weight: 500;
}

.col-type {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
}

.field-select {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--card-border, #e5e7eb);
  border-radius: 4px;
  font-size: 13px;
  background: var(--bg, #f9fafb);
  color: var(--text, #111);
}

.field-select:focus {
  outline: none;
  border-color: var(--accent, #4f8cf7);
  box-shadow: 0 0 0 2px rgba(79, 140, 247, 0.15);
}

.confidence-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.confidence-badge.high {
  background: rgba(16, 185, 129, 0.15);
  color: #059669;
}

.confidence-badge.medium {
  background: rgba(245, 158, 11, 0.15);
  color: #d97706;
}

.confidence-badge.low {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}

.confidence-skip {
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
}

.sample-section {
  padding: 12px 24px;
  border-top: 1px solid var(--card-border, #e5e7eb);
}

.sample-section h3 {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--text-secondary, #6b7280);
}

.sample-table-wrapper {
  overflow-x: auto;
  max-height: 120px;
}

.sample-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.sample-table th, .sample-table td {
  padding: 4px 8px;
  border: 1px solid var(--card-border, #e5e7eb);
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sample-table th {
  background: var(--bg, #f9fafb);
  font-weight: 600;
  position: sticky;
  top: 0;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--card-border, #e5e7eb);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel {
  padding: 8px 20px;
  border: 1px solid var(--card-border, #e5e7eb);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary, #6b7280);
  font-size: 14px;
  cursor: pointer;
}

.btn-cancel:hover {
  background: rgba(0, 0, 0, 0.04);
}

.btn-confirm {
  padding: 8px 24px;
  border: none;
  border-radius: 6px;
  background: linear-gradient(135deg, #4f8cf7, #6366f1);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-confirm:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 140, 247, 0.3);
}

.btn-confirm:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
