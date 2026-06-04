import { createApp } from 'vue'
import { createPinia } from 'pinia'
import * as echarts from 'echarts'
import App from './App.vue'
import router from './router/index.js'
import './assets/theme.css'

// ECharts 浅色主题
echarts.registerTheme('complaint-light', {
  color: ['#4f8cf7', '#e8634a', '#f5a623', '#4caf7d', '#8b6cd6', '#26a69a', '#ef6c9e', '#5c6bc0'],
  backgroundColor: 'transparent',
  textStyle: { color: '#1a2332' },
  tooltip: {
    backgroundColor: 'rgba(255, 255, 255, 0.96)',
    borderColor: '#e2e6ed',
    borderWidth: 1,
    textStyle: { color: '#1a2332', fontSize: 13 },
    padding: [10, 14],
    extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-radius: 8px;',
  },
  axisLine: { lineStyle: { color: '#e2e6ed' } },
  axisLabel: { color: '#5a6a7a' },
  splitLine: { lineStyle: { color: '#eef1f5' } },
  legend: { textStyle: { color: '#1a2332' } },
  grid: { containLabel: true },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
