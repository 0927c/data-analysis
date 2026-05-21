<template>
  <div class="chat-input-area">
    <textarea
      ref="textareaEl"
      v-model="inputText"
      class="chat-textarea"
      placeholder="请输入你的问题... (Enter 发送，Shift+Enter 换行)"
      @keydown="handleKeydown"
      rows="1"
    ></textarea>
    <button
      class="btn-send"
      :disabled="!inputText.trim() || disabled"
      @click="handleSend"
    >
      发送
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])
const inputText = ref('')
const textareaEl = ref(null)

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text || props.disabled) return
  emit('send', text)
  inputText.value = ''
  nextTick(() => {
    if (textareaEl.value) {
      textareaEl.value.style.height = 'auto'
    }
  })
}
</script>

<style scoped>
.chat-input-area {
  padding: 16px 40px;
  border-top: 1px solid var(--card-border);
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background: var(--bg);
}

.chat-textarea {
  flex: 1;
  resize: none;
  min-height: 42px;
  max-height: 120px;
  line-height: 1.5;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--text);
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
}

.chat-textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.btn-send {
  background: var(--gradient1);
  color: white;
  font-weight: 600;
  padding: 10px 24px;
  border-radius: 8px;
  height: 42px;
  border: none;
  cursor: pointer;
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
