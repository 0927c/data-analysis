<template>
  <div class="loading-indicator" :class="{ fullscreen: fullscreen }">
    <!-- Spinner mode (default) -->
    <template v-if="!skeleton">
      <div class="spinner"></div>
      <span class="loading-text">{{ text }}</span>
    </template>
    <!-- Skeleton mode -->
    <template v-else>
      <div class="skeleton-lines" :style="{ width: skeletonWidth }">
        <div
          v-for="i in skeletonLines"
          :key="i"
          class="skeleton-line"
          :style="{ width: skeletonWidths?.[i - 1] || '100%', height: i === 1 ? '18px' : '14px' }"
        ></div>
      </div>
    </template>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '加载中...' },
  fullscreen: { type: Boolean, default: false },
  skeleton: { type: Boolean, default: false },
  skeletonLines: { type: Number, default: 4 },
  skeletonWidth: { type: String, default: '100%' },
  skeletonWidths: { type: Array, default: null },
})
</script>

<style scoped>
.loading-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
}

.loading-indicator.fullscreen {
  justify-content: center;
  padding: var(--space-3xl);
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--card-border);
  border-top-color: var(--accent);
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  animation: textPulse 1.5s ease-in-out infinite;
}

@keyframes textPulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

/* Skeleton */
.skeleton-lines {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  width: 100%;
}

.skeleton-line {
  background: linear-gradient(
    90deg,
    var(--bg-deepest) 25%,
    var(--card-bg) 50%,
    var(--bg-deepest) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
