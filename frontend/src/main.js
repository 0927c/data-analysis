import { createApp } from 'vue'
import { createPinia } from 'pinia'
import * as echarts from 'echarts'
import App from './App.vue'
import router from './router/index.js'
import './assets/theme.css'

// ECharts 暗色主题
echarts.registerTheme('complaint-dark', {
  color: ['#00d4ff', '#ff6b6b', '#ffd93d', '#6bcb77', '#9b59b6', '#e67e22', '#1abc9c', '#e74c3c'],
  backgroundColor: 'transparent',
  textStyle: { color: '#e0e8f0' },
  tooltip: {
    backgroundColor: 'rgba(26, 40, 55, 0.95)',
    borderColor: '#2a3f54',
    borderWidth: 1,
    textStyle: { color: '#e0e8f0', fontSize: 13 },
    padding: [10, 14],
    extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.3); border-radius: 8px;',
  },
  axisLine: { lineStyle: { color: '#2a3f54' } },
  axisLabel: { color: '#8899aa' },
  splitLine: { lineStyle: { color: '#1a2f44' } },
  legend: { textStyle: { color: '#e0e8f0' } },
  grid: { containLabel: true },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
