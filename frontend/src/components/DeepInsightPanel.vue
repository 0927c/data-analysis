<template>
  <div class="deep-insight-panel">
    <div class="panel-header">
      <span class="panel-icon">&#x1F9E0;</span>
      <span class="panel-title">数据分析大师 &mdash; 深度洞察</span>
    </div>

    <div class="insight-cards">
      <div
        v-for="(card, idx) in insights"
        :key="idx"
        class="insight-card"
        :class="`severity-${card.severity}`"
      >
        <div class="card-tag" :class="`tag-${card.severity}`">
          {{ card.tag }}
        </div>
        <div class="card-title">{{ card.title }}</div>
        <div class="card-content" v-html="formatContent(card.content)"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'

const props = defineProps({
  insights: {
    type: Array,
    default: () => [],
  },
})

function formatContent(text) {
  if (!text) return ''
  // 将 Markdown 粗体转为 HTML
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped>
.deep-insight-panel {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  margin: var(--space-md) 0;
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
}

.panel-icon {
  font-size: var(--font-size-lg);
}

.panel-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-bold);
  color: #e2e8f0;
  letter-spacing: 0.5px;
}

.insight-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.insight-card {
  background: rgba(30, 41, 59, 0.8);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  border-left: 4px solid;
  transition: all var(--transition-fast);
}

.insight-card:hover {
  transform: translateX(4px);
  background: rgba(30, 41, 59, 1);
}

/* 严重程度配色 */
.severity-danger { border-left-color: #ef4444; }
.severity-warning { border-left-color: #f59e0b; }
.severity-success { border-left-color: #10b981; }
.severity-info { border-left-color: #6366f1; }

.card-tag {
  display: inline-block;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  padding: 2px var(--space-sm);
  border-radius: var(--radius-full);
  margin-bottom: var(--space-xs);
  letter-spacing: 0.5px;
}

.tag-danger {
  background: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
}

.tag-warning {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
}

.tag-success {
  background: rgba(16, 185, 129, 0.2);
  color: #6ee7b7;
}

.tag-info {
  background: rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
}

.card-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: #f1f5f9;
  margin-bottom: var(--space-xs);
}

.card-content {
  font-size: var(--font-size-sm);
  color: #cbd5e1;
  line-height: 1.6;
}

.card-content :deep(strong) {
  color: #f8fafc;
  font-weight: var(--font-weight-semibold);
}
</style>
