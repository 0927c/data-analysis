<template>
  <div class="kpi-card" @mouseenter="isHovered = true" @mouseleave="isHovered = false">
    <div v-if="icon" class="kpi-icon" :style="{ background: iconGradient }">
      {{ icon }}
    </div>
    <div class="kpi-value" :style="{ color: animatedColor }">
      {{ displayValue }}
    </div>
    <div class="kpi-label">{{ label }}</div>
    <div v-if="trend !== null" class="kpi-trend" :class="trendClass">
      <span class="trend-pill" :class="trendDirection">
        {{ trend > 0 ? '↑' : '↓' }} {{ Math.abs(trend) }}%
      </span>
    </div>
    <div v-if="sparklineData && sparklineData.length" class="kpi-sparkline">
      <div
        v-for="(val, i) in sparklineData"
        :key="i"
        class="spark-bar"
        :style="{ height: sparkHeight(val) + '%' }"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  value: { type: [Number, String], required: true },
  label: { type: String, required: true },
  color: { type: String, default: 'var(--accent)' },
  trend: { type: Number, default: null },
  icon: { type: String, default: '' },
  iconGradient: { type: String, default: 'var(--gradient1)' },
  sparklineData: { type: Array, default: null },
})

const displayValue = ref(0)
const isHovered = ref(false)

const animatedColor = computed(() => {
  if (typeof props.value !== 'number') return props.color
  return props.color
})

const trendClass = computed(() => {
  if (props.trend === null) return ''
  // For complaints: going up is bad (red), going down is good (green)
  return props.trend > 0 ? 'trend-up-bad' : 'trend-down-good'
})

const trendDirection = computed(() => {
  return props.trend > 0 ? 'up' : 'down'
})

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3)
}

function animateValue(target) {
  if (typeof target !== 'number') {
    displayValue.value = target
    return
  }
  const start = typeof displayValue.value === 'number' ? displayValue.value : 0
  const duration = 800
  const startTime = performance.now()

  function update(currentTime) {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = easeOutCubic(progress)
    displayValue.value = Math.round(start + (target - start) * eased)
    if (progress < 1) {
      requestAnimationFrame(update)
    }
  }
  requestAnimationFrame(update)
}

function sparkHeight(val) {
  const max = Math.max(...props.sparklineData, 1)
  return (val / max) * 100
}

watch(() => props.value, animateValue, { immediate: true })
onMounted(() => animateValue(props.value))
</script>

<style scoped>
.kpi-card {
  position: relative;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  text-align: center;
  overflow: hidden;
  transition: all var(--transition-base) var(--ease-out);
}

.kpi-card::before {
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

.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--card-shadow-hover);
  border-color: var(--card-border-hover);
}

.kpi-card:hover::before {
  transform: scaleX(1);
}

.kpi-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-lg);
  margin-bottom: var(--space-sm);
}

.kpi-value {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-tight);
  transition: color var(--transition-fast);
}

.kpi-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: var(--space-xs);
  font-weight: var(--font-weight-medium);
}

.kpi-trend {
  margin-top: var(--space-sm);
}

.trend-pill {
  display: inline-block;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  padding: 2px var(--space-sm);
  border-radius: var(--radius-full);
}

.trend-pill.up {
  background: rgba(255, 107, 107, 0.15);
  color: var(--accent2);
}

.trend-pill.down {
  background: rgba(107, 203, 119, 0.15);
  color: var(--accent4);
}

/* Sparkline */
.kpi-sparkline {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
  height: 24px;
  margin-top: var(--space-sm);
}

.spark-bar {
  width: 4px;
  border-radius: 2px 2px 0 0;
  background: var(--accent);
  opacity: 0.6;
  transition: all var(--transition-fast);
}

.kpi-card:hover .spark-bar {
  opacity: 1;
}
</style>
