<template>
  <div class="chat-message" :class="message.role">
    <div class="message-content">
      <!-- User message -->
      <p v-if="message.role === 'user'" class="user-text">{{ message.content }}</p>

      <!-- Agent message -->
      <template v-else>
        <p class="agent-text">{{ message.content }}</p>

        <!-- Charts -->
        <div v-for="(chart, idx) in message.charts" :key="idx" class="chart-wrapper">
          <div class="chart-header">
            <span class="chart-title">{{ chart.title }}</span>
          </div>
          <ChartRenderer :option="chart.option" height="320px" />
        </div>

        <!-- Insights -->
        <div v-if="message.insights?.length" class="insights">
          <div v-for="(insight, i) in message.insights" :key="i" class="insight-chip">
            💡 {{ insight }}
          </div>
        </div>

        <!-- Data Table -->
        <div v-if="message.data_table" class="data-table">
          <table>
            <thead>
              <tr>
                <th v-for="h in message.data_table.headers" :key="h">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in message.data_table.rows" :key="ri">
                <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Action buttons -->
        <div v-if="message.report_id" class="message-actions">
          <button class="btn-save" @click="$emit('save', message.report_id)">保存报表</button>
          <router-link :to="`/reports/${message.report_id}`" class="btn-view">查看详情</router-link>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import ChartRenderer from './ChartRenderer.vue'

defineProps({
  message: { type: Object, required: true },
})

defineEmits(['save'])
</script>

<style scoped>
.chat-message {
  margin-bottom: 20px;
  display: flex;
}

.chat-message.user {
  justify-content: flex-end;
}

.message-content {
  max-width: 70%;
}

.user-text {
  background: rgba(79, 140, 247, 0.1);
  border: 1px solid rgba(79, 140, 247, 0.18);
  padding: 12px 16px;
  border-radius: 12px 12px 0 12px;
  font-size: 14px;
}

.agent-text {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  padding: 12px 16px;
  border-radius: 12px 12px 12px 0;
  font-size: 14px;
  margin-bottom: 8px;
}

.chart-wrapper {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 16px;
  margin: 8px 0;
}

.chart-header {
  margin-bottom: 8px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
}

.insights {
  margin: 8px 0;
}

.insight-chip {
  background: rgba(79, 140, 247, 0.06);
  border-left: 3px solid var(--accent);
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 0 8px 8px 0;
  font-size: 13px;
}

.data-table {
  margin: 8px 0;
  overflow-x: auto;
}

.data-table table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th, .data-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--card-border);
  font-size: 13px;
}

.data-table th {
  color: var(--text-secondary);
  font-weight: 600;
}

.message-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.btn-save {
  background: var(--gradient4);
  color: white;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
}

.btn-view {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--text);
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 6px;
}
</style>
