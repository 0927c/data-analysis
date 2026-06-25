<template>
  <div class="chart-renderer" ref="containerRef">
    <div ref="chartRef" :style="{ height: height }" class="chart-dom"></div>

    <!-- Hover toolbar -->
    <div v-if="showToolbar" class="chart-toolbar">
      <button class="toolbar-btn" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏'">
        {{ isFullscreen ? '✖' : '⛶' }}
      </button>
      <button class="toolbar-btn" @click="downloadPNG" title="下载 PNG">
        &#x1F4BE;
      </button>
    </div>

    <!-- Fullscreen overlay -->
    <Teleport to="body">
      <div v-if="isFullscreen" class="fullscreen-overlay" @click.self="toggleFullscreen">
        <div class="fullscreen-chart">
          <div ref="fullscreenRef" class="fullscreen-dom"></div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const emit = defineEmits(['click'])

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '320px' },
  showToolbar: { type: Boolean, default: true },
})

const chartRef = ref(null)
const containerRef = ref(null)
const fullscreenRef = ref(null)
let chartInstance = null
let fullscreenInstance = null
const isFullscreen = ref(false)
const showToolbar = ref(props.showToolbar)

function initChart(el, option) {
  if (!el || !option) return
  const chart = echarts.init(el, 'complaint-light')
  chart.setOption(option, { notMerge: true })
  chart.on('click', (params) => emit('click', params))
  window.addEventListener('resize', () => chart.resize())
  return chart
}

onMounted(() => {
  if (chartRef.value && props.option) {
    chartInstance = initChart(chartRef.value, props.option)
  }
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    window.removeEventListener('resize', handleResize)
  }
  if (fullscreenInstance) {
    fullscreenInstance.dispose()
  }
})

watch(() => props.option, (newOption) => {
  if (chartInstance && newOption) {
    chartInstance.setOption(newOption, { notMerge: true })
  }
  if (fullscreenInstance && newOption && isFullscreen.value) {
    fullscreenInstance.setOption(newOption, { notMerge: true })
    nextTick(() => fullscreenInstance.resize())
  }
}, { deep: true })

function handleResize() {
  chartInstance?.resize()
}

async function toggleFullscreen() {
  if (!isFullscreen.value) {
    isFullscreen.value = true
    await nextTick()
    if (fullscreenRef.value && props.option) {
      fullscreenInstance = echarts.init(fullscreenRef.value, 'complaint-light')
      fullscreenInstance.setOption(props.option, { notMerge: true })
      fullscreenInstance.on('click', (params) => emit('click', params))
      await nextTick()
      fullscreenInstance.resize()
    }
  } else {
    if (fullscreenInstance) {
      fullscreenInstance.dispose()
      fullscreenInstance = null
    }
    isFullscreen.value = false
  }
}

function downloadPNG() {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#ffffff',
  })
  const a = document.createElement('a')
  a.href = url
  a.download = 'chart.png'
  a.click()
}
</script>

<style scoped>
.chart-renderer {
  position: relative;
  width: 100%;
  min-height: 200px;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.chart-dom {
  width: 100%;
}

/* Hover toolbar */
.chart-toolbar {
  position: absolute;
  top: var(--space-sm);
  right: var(--space-sm);
  display: flex;
  gap: var(--space-xs);
  background: var(--bg-overlay);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: var(--space-xs);
  opacity: 0;
  transform: translateY(-4px);
  transition: all var(--transition-base) var(--ease-out);
  z-index: var(--z-dropdown);
}

.chart-renderer:hover .chart-toolbar {
  opacity: 1;
  transform: translateY(0);
}

.toolbar-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: var(--space-xs) var(--space-sm);
  font-size: var(--font-size-sm);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  line-height: 1;
}

.toolbar-btn:hover {
  color: var(--accent);
  background: var(--accent-glow);
}

/* Fullscreen */
.fullscreen-overlay {
  position: fixed;
  inset: 0;
  background: rgba(245, 247, 250, 0.92);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  cursor: zoom-out;
  animation: fadeIn var(--transition-base);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.fullscreen-chart {
  width: 85vw;
  height: 80vh;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-xl);
  padding: var(--space-xl);
  box-shadow: var(--card-shadow-hover);
  animation: scaleIn var(--transition-base) var(--ease-out);
}

@keyframes scaleIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.fullscreen-dom {
  width: 100%;
  height: 100%;
}
</style>
