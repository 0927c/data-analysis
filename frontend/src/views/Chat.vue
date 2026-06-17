<template>
  <div class="chat-layout">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <button v-if="!sidebarCollapsed" class="btn-new" @click="startNewChat">
          ＋ 新对话
        </button>
        <button class="btn-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '›' : '‹' }}
        </button>
      </div>

      <nav class="session-list" v-if="!sidebarCollapsed">
        <div
          v-for="session in chatStore.sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: chatStore.currentSessionId === session.id }"
          @click="loadSession(session.id)"
        >
          <div class="session-info">
            <div class="session-title">{{ session.title || '新对话' }}</div>
            <div class="session-time">{{ formatTime(session.updated_at) }}</div>
          </div>
          <button class="btn-delete-session" @click.stop="confirmDeleteSession(session.id, session.title)" title="删除会话">&#x2715;</button>
        </div>
        <div v-if="chatStore.sessions.length === 0" class="empty-tip">暂无历史对话</div>
      </nav>

      <div class="sidebar-footer" v-if="!sidebarCollapsed">
        <router-link to="/reports" class="nav-link">📊 我的报表</router-link>
        <router-link v-if="authStore.isAdmin" to="/admin/datasources" class="nav-link">⚙️ 数据源管理</router-link>
        <router-link v-if="authStore.isAdmin" to="/admin/skills" class="nav-link">🔧 Skill 管理</router-link>
        <div class="user-info">
          <span>{{ authStore.user?.display_name || authStore.user?.username }}</span>
          <button class="btn-logout" @click="handleLogout">退出</button>
        </div>
      </div>
    </aside>

    <!-- Main Chat Area -->
    <main class="chat-main">
      <!-- Dashboard header (empty state) -->
      <div v-if="chatStore.messages.length === 0 && !chatStore.loading" class="welcome-section">
        <div class="greeting-header">
          <h2 class="greeting-text">{{ greeting }}，{{ displayName }}</h2>
          <p class="greeting-date">{{ currentDate }}</p>
        </div>
        <p class="greeting-sub">我可以帮你分析工单数据，生成可视化报表</p>

        <!-- Quick stats -->
        <div v-if="analyticsStore.summary" class="quick-stats">
          <KPICard
            :value="analyticsStore.summary.total || 0"
            label="总工单数"
            color="var(--accent)"
          />
          <KPICard
            :value="analyticsStore.summary.sla_ratio || 0"
            label="SLA 达标率"
            color="var(--accent3)"
            suffix="%"
          />
          <KPICard
            :value="analyticsStore.summary.avg_resolution_days || 0"
            label="平均解决天数"
            color="var(--accent4)"
          />
        </div>

        <!-- Quick questions -->
        <div class="quick-questions">
          <button @click="askQuestion('各状态工单分布是怎样的？')">工单状态分布</button>
          <button @click="askQuestion('哪些故障原因在重复出现？')">重复故障挖掘</button>
          <button @click="askQuestion('故障根因 TOP10 排名')">故障根因排名</button>
          <button @click="askQuestion('运维质量指标：退回率、挂起率、SLA')">运维质量指标</button>
          <button @click="askQuestion('最近几周的工单趋势如何？')">工单周趋势</button>
          <button @click="askQuestion('哪个服务组的工单最多？')">服务组工作量</button>
        </div>
      </div>

      <!-- Messages -->
      <div ref="messageContainer" class="messages">
        <div
          v-for="(msg, idx) in chatStore.messages"
          :key="idx"
          class="message"
          :class="msg.role"
          :style="{ animationDelay: (idx * 50) + 'ms' }"
        >
          <!-- Avatar -->
          <div v-if="msg.role === 'assistant'" class="avatar avatar-assistant">AI</div>
          <div v-if="msg.role === 'user'" class="avatar avatar-user">{{ userInitial }}</div>

          <div class="message-content">
            <p v-if="msg.role === 'user'" class="user-text">{{ msg.content }}</p>
            <template v-else>
            <div class="agent-text" v-html="renderMarkdown(msg.content)"></div>
              <!-- Embedded Charts -->
              <div v-for="chart in (msg.charts || [])" :key="chart.id" class="chart-wrapper">
                <div class="chart-header">
                  <span class="chart-title">{{ chart.title }}</span>
                </div>
                <div class="chart-container" :data-chart-id="chart.id"></div>
              </div>
              <!-- Insights -->
              <div v-if="msg.insights && msg.insights.length" class="insights">
                <div v-for="(insight, i) in msg.insights" :key="i" class="insight-chip" :style="{ animationDelay: (i * 80) + 'ms' }">
                  <span class="insight-icon">&#x1F4A1;</span>
                  {{ insight }}
                </div>
              </div>
              <!-- Deep Insight Panel (数据分析大师) -->
              <DeepInsightPanel v-if="msg.deep_insights && msg.deep_insights.length" :insights="msg.deep_insights" />
              <!-- Data Table -->
              <div v-if="msg.data_table" class="data-table">
                <table>
                  <thead>
                    <tr>
                      <th v-for="h in msg.data_table.headers" :key="h">{{ h }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, ri) in msg.data_table.rows" :key="ri">
                      <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <!-- Action buttons -->
              <div v-if="msg.report_id" class="message-actions">
                <button class="btn-save" @click="saveReport(msg.report_id)">保存报表</button>
                <router-link :to="`/reports/${msg.report_id}`" class="btn-view">查看详情</router-link>
              </div>
            </template>
          </div>
        </div>

        <!-- Loading indicator -->
        <div v-if="chatStore.loading" class="message assistant">
          <div class="avatar avatar-assistant">AI</div>
          <div class="message-content">
            <div class="thinking">
              <span class="thinking-dots">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
              </span>
              分析中...
            </div>
          </div>
        </div>
      </div>

      <!-- Datasource Switcher -->
      <div v-if="dsStore.canSwitch" class="datasource-switcher">
        <span class="switch-label">当前数据源：</span>
        <div class="ds-chips">
          <button
            v-for="ds in dsStore.activeDatasources"
            :key="ds.id"
            :class="['ds-chip', { active: dsStore.primaryDatasourceId === ds.id }]"
            @click="handleDatasourceSwitch(ds.id)"
          >
            {{ ds.name }}
            <span class="ds-count">({{ ds.record_count }}条)</span>
          </button>
        </div>
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.xls"
          class="hidden-file-input"
          @change="handleFileSelect"
        />
        <button class="btn-attach" @click="$refs.fileInput.click()" title="上传 Excel 附件" :disabled="chatStore.loading">
          &#x1F4CE;
        </button>
        <div v-if="selectedFile" class="file-tag">
          <span class="file-name">{{ selectedFile.name }}</span>
          <button class="file-remove" @click="clearFile">&times;</button>
        </div>
        <textarea
          ref="inputEl"
          v-model="inputText"
          placeholder="请输入你的问题... (Enter 发送，Shift+Enter 换行)"
          @keydown="handleKeydown"
          rows="1"
        ></textarea>
        <button class="btn-send" :disabled="(!inputText.trim() && !selectedFile) || chatStore.loading" @click="handleSend">
          发送
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useAuthStore, useChatStore, useAnalyticsStore, useReportStore } from '@/store/index.js'
import { useDatasourceStore } from '@/store/datasource.js'
import KPICard from '@/components/KPICard.vue'
import DeepInsightPanel from '@/components/DeepInsightPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()
const analyticsStore = useAnalyticsStore()
const reportStore = useReportStore()
const dsStore = useDatasourceStore()

const inputText = ref('')
const sidebarCollapsed = ref(false)
const messageContainer = ref(null)
const inputEl = ref(null)
const fileInput = ref(null)
const selectedFile = ref(null)

// Markdown 轻量渲染器
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    // 转义 HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // 标题（从大到小，避免 #### 被 ### 先匹配）
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // 加粗（先处理，避免被列表误匹配）
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 行内代码
    .replace(/`(.+?)`/g, '<code>$1</code>')
    // 无序列表（支持缩进 + * 或 - 开头）
    .replace(/^[\s]*[*-] (.+)$/gm, '<li>$1</li>')
    // 水平线
    .replace(/^---+$/gm, '<hr>')
    // 换行
    .replace(/\n/g, '<br>')

  // 将连续的 <li> 包裹在 <ul> 中
  html = html.replace(/((?:<li>.*?<\/li><br>?)+)/g, '<ul>$1</ul>')
  // 清理多余的 <br> 在 ul 前后
  html = html.replace(/<ul><br>/g, '<ul>').replace(/<br><\/ul>/g, '</ul>')
  // 清理连续的 <br><br>
  html = html.replace(/(<br>){3,}/g, '<br><br>')

  return html
}

const chartInstances = new Map()

onBeforeUnmount(() => {
  chartInstances.forEach((chart) => chart.dispose())
  chartInstances.clear()
})

const initializedCharts = new Set()

function initChart(el, option) {
  if (!el) return
  // 用 DOM 元素做去重，避免重复初始化
  if (initializedCharts.has(el)) return
  initializedCharts.add(el)
  // 如果该 DOM 已有图表实例，先销毁
  if (chartInstances.has(el)) {
    chartInstances.get(el).dispose()
  }
  const chart = echarts.init(el, 'complaint-light')
  chart.setOption(option)
  chartInstances.set(el, chart)
  const resizeHandler = () => chart.resize()
  window.addEventListener('resize', resizeHandler)
  // 存储 resize handler 以便清理
  el._resizeHandler = resizeHandler
}

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const displayName = computed(() => {
  return authStore.user?.display_name || authStore.user?.username || ''
})

const userInitial = computed(() => {
  const name = displayName.value
  return name ? name.charAt(0).toUpperCase() : '?'
})

const currentDate = computed(() => {
  const now = new Date()
  const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${now.getMonth() + 1}月${now.getDate()}日 ${days[now.getDay()]}`
})

onMounted(async () => {
  await chatStore.fetchSessions()
  await analyticsStore.fetchSummary()
  await dsStore.fetchDatasources()
  // 恢复上次对话的会话
  const lastSessionId = localStorage.getItem('lastSessionId')
  if (lastSessionId) {
    const sid = parseInt(lastSessionId, 10)
    const exists = chatStore.sessions.some(s => s.id === sid)
    if (exists) {
      chatStore.currentSessionId = sid
      await chatStore.fetchMessages(sid)
      await nextTick()
      scrollToBottom()
    } else {
      localStorage.removeItem('lastSessionId')
    }
  }
})

async function loadSession(sessionId) {
  chatStore.currentSessionId = sessionId
  localStorage.setItem('lastSessionId', String(sessionId))
  await chatStore.fetchMessages(sessionId)
  scrollToBottom()
}

async function handleDatasourceSwitch(datasourceId) {
  if (dsStore.primaryDatasourceId === datasourceId) return

  try {
    const sessionId = chatStore.currentSessionId
    if (sessionId) {
      await dsStore.switchPrimaryRemote(sessionId, datasourceId)
    } else {
      dsStore.switchPrimary(datasourceId)
    }
    const ds = dsStore.datasources.find(d => d.id === datasourceId)
    // 添加系统消息提示
    chatStore.messages.push({
      role: 'system',
      content: `已切换到数据源: ${ds ? ds.name : datasourceId}`,
      created_at: new Date().toISOString(),
    })
  } catch (err) {
    console.error('切换数据源失败:', err)
  }
}

function startNewChat() {
  chatStore.currentSessionId = null
  chatStore.messages = []
  inputText.value = ''
  localStorage.removeItem('lastSessionId')
}

async function handleSend() {
  const text = inputText.value.trim()
  const file = selectedFile.value
  if ((!text && !file) || chatStore.loading) return

  inputText.value = ''

  // 有附件走上传路径
  if (file) {
    const displayText = text || `请帮我分析 ${file.name} 的数据`
    chatStore.messages.push({ role: 'user', content: `[上传文件] ${file.name}\n${displayText}`, created_at: new Date().toISOString() })
    clearFile()
    try {
      const wasNewSession = !chatStore.currentSessionId
      const data = await chatStore.sendWithFile(file, displayText, chatStore.currentSessionId)
      if (wasNewSession && data.session_id) {
        chatStore.currentSessionId = data.session_id
        localStorage.setItem('lastSessionId', String(data.session_id))
        await chatStore.fetchSessions()
      }
      await nextTick()
      scrollToBottom()
    } catch (e) {
      console.error('Upload + analysis failed:', e)
      chatStore.messages.push({
        role: 'assistant',
        content: '抱歉，文件解析失败，请检查文件格式后重试。',
        created_at: new Date().toISOString(),
      })
      await nextTick()
      scrollToBottom()
    }
    return
  }

  // 普通文本消息
  chatStore.messages.push({ role: 'user', content: text, created_at: new Date().toISOString() })

  try {
    const wasNewSession = !chatStore.currentSessionId
    const data = await chatStore.sendMessage(text, chatStore.currentSessionId)
    if (wasNewSession && data.session_id) {
      chatStore.currentSessionId = data.session_id
      localStorage.setItem('lastSessionId', String(data.session_id))
      await chatStore.fetchSessions()
    }
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error('Send message failed:', e)
    chatStore.messages.push({
      role: 'assistant',
      content: '抱歉，处理你的问题时出了点状况，请稍后重试。',
      created_at: new Date().toISOString(),
    })
    await nextTick()
    scrollToBottom()
  }
}

async function askQuestion(question) {
  inputText.value = question
  await handleSend()
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) {
    if (!file.name.match(/\.(xlsx|xls)$/i)) {
      alert('仅支持 .xlsx / .xls 格式文件')
      return
    }
    selectedFile.value = file
  }
  e.target.value = ''
}

function clearFile() {
  selectedFile.value = null
}

function scrollToBottom() {
  nextTick(() => {
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  })
}

async function saveReport(reportId) {
  try {
    await reportStore.fetchReport(reportId)
    alert('报表已保存，可在"我的报表"中查看')
  } catch (e) {
    alert('报表保存失败，请稍后重试')
  }
}

async function confirmDeleteSession(sessionId, title) {
  const name = title || '新对话'
  if (!confirm(`确定删除会话「${name}」吗？`)) return
  try {
    await chatStore.deleteSession(sessionId)
  } catch (e) {
    console.error('删除会话失败:', e)
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now - d
  if (diff < 86400000 && d.getDate() === now.getDate()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

// 当消息列表变化时，初始化新出现的图表
watch(() => chatStore.messages.length, () => {
  nextTick(() => {
    document.querySelectorAll('.chart-container[data-chart-id]:not([data-initialized])').forEach(el => {
      el.setAttribute('data-initialized', '1')
      const chartId = el.getAttribute('data-chart-id')
      // 在当前消息中找到对应的 chart option
      for (const msg of chatStore.messages) {
        if (msg.charts) {
          const chart = msg.charts.find(c => c.id == chartId)
          if (chart) {
            initChart(el, chart.option)
            break
          }
        }
      }
    })
    scrollToBottom()
  })
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: 260px;
  background: var(--bg-elevated);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border-right: 1px solid var(--card-border);
  display: flex;
  flex-direction: column;
  transition: width 0.3s var(--ease-out);
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 48px;
}

.sidebar-header {
  padding: var(--space-lg);
  display: flex;
  gap: var(--space-sm);
  border-bottom: 1px solid var(--card-border);
}

.btn-new {
  flex: 1;
  background: var(--gradient1);
  color: white;
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md);
  box-shadow: 0 2px 8px rgba(79, 140, 247, 0.2);
  transition: all var(--transition-base) var(--ease-out);
}

.btn-new:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(79, 140, 247, 0.3);
}

.btn-toggle {
  background: transparent;
  color: var(--text-secondary);
  font-size: 18px;
  padding: var(--space-sm);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.btn-toggle:hover {
  background: rgba(0, 0, 0, 0.04);
  color: var(--text);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-sm);
}

.session-item {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  cursor: pointer;
  margin-bottom: var(--space-xs);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.session-item:hover {
  background: rgba(0, 0, 0, 0.03);
  transform: translateX(2px);
}

.session-item.active {
  background: rgba(79, 140, 247, 0.08);
  border-color: rgba(79, 140, 247, 0.2);
  box-shadow: 0 0 12px var(--accent-glow);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: var(--font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: var(--font-weight-medium);
}

.session-time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}

.btn-delete-session {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  font-size: 12px;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all var(--transition-fast);
  cursor: pointer;
}

.session-item:hover .btn-delete-session {
  opacity: 1;
}

.btn-delete-session:hover {
  background: rgba(255, 107, 107, 0.15);
  color: var(--accent2);
}

.empty-tip {
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  padding: var(--space-2xl) 0;
}

.sidebar-footer {
  padding: var(--space-md) var(--space-lg);
  border-top: 1px solid var(--card-border);
}

.nav-link {
  display: block;
  padding: var(--space-sm) 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  transition: color var(--transition-fast);
}

.nav-link:hover {
  color: var(--accent);
}

.user-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-sm);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.btn-logout {
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-sm);
}

.btn-logout:hover {
  color: var(--accent2);
  background: rgba(255, 107, 107, 0.08);
}

/* Main Chat Area */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Welcome / Dashboard */
.welcome-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-3xl);
  animation: fadeInUp 0.6s var(--ease-out);
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.greeting-header {
  margin-bottom: var(--space-sm);
}

.greeting-text {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  background: var(--gradient1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.greeting-date {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}

.greeting-sub {
  color: var(--text-secondary);
  font-size: var(--font-size-md);
  margin-bottom: var(--space-2xl);
}

/* Quick stats */
.quick-stats {
  display: flex;
  gap: var(--space-lg);
  margin-bottom: var(--space-2xl);
  flex-wrap: wrap;
  justify-content: center;
}

.quick-stats > * {
  width: 160px;
}

/* Quick questions */
.quick-questions {
  display: flex;
  gap: var(--space-md);
  flex-wrap: wrap;
  justify-content: center;
}

.quick-questions button {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--text);
  padding: var(--space-md) var(--space-xl);
  border-radius: var(--radius-full);
  font-size: var(--font-size-base);
  transition: all var(--transition-base) var(--ease-out);
}

.quick-questions button:hover {
  border-color: var(--accent);
  background: rgba(79, 140, 247, 0.05);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(79, 140, 247, 0.1);
}

/* Messages */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xl) var(--space-2xl);
}

.message {
  display: flex;
  gap: var(--space-md);
  margin-bottom: var(--space-xl);
  animation: messageSlideIn var(--transition-base) var(--ease-out) both;
}

@keyframes messageSlideIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  justify-content: flex-end;
}

.message.user .message-content {
  display: flex;
  flex-direction: row-reverse;
}

/* Avatars */
.avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;
  margin-top: var(--space-xs);
}

.avatar-assistant {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--accent);
}

.avatar-user {
  background: var(--gradient1);
  color: white;
}

.message-content {
  max-width: 70%;
}

.user-text {
  background: rgba(79, 140, 247, 0.1);
  border: 1px solid rgba(79, 140, 247, 0.18);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg) var(--radius-lg) var(--space-xs) var(--radius-lg);
  font-size: var(--font-size-base);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.agent-text {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  padding: var(--space-lg) var(--space-xl);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--space-xs);
  font-size: var(--font-size-base);
  margin-bottom: var(--space-sm);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  line-height: 1.8;
  color: var(--text);
}

.agent-text :deep(h1) {
  font-size: 1.4em;
  font-weight: 700;
  margin: 1em 0 0.5em;
  padding-bottom: 0.3em;
  border-bottom: 2px solid var(--accent);
  color: var(--text);
}

.agent-text :deep(h2) {
  font-size: 1.25em;
  font-weight: 700;
  margin: 1em 0 0.5em;
  color: var(--text);
}

.agent-text :deep(h3) {
  font-size: 1.1em;
  font-weight: 700;
  margin: 0.8em 0 0.4em;
  color: var(--accent);
}

.agent-text :deep(h4) {
  font-size: 1em;
  font-weight: 700;
  margin: 0.6em 0 0.3em;
  color: var(--text);
  padding-left: 0.5em;
  border-left: 3px solid var(--accent);
}

.agent-text :deep(strong) {
  font-weight: 700;
  color: var(--text);
  background: rgba(79, 140, 247, 0.08);
  padding: 1px 4px;
  border-radius: 3px;
}

.agent-text :deep(em) {
  font-style: italic;
  color: var(--text-secondary);
}

.agent-text :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.9em;
}

.agent-text :deep(ul) {
  margin: 0.5em 0;
  padding-left: 1.5em;
  list-style-type: disc;
}

.agent-text :deep(li) {
  margin: 0.3em 0;
  line-height: 1.7;
}

.agent-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--card-border);
  margin: 1em 0;
}

.agent-text :deep(p) {
  margin: 0.5em 0;
}

.chart-wrapper {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  margin: var(--space-sm) 0;
  transition: border-color var(--transition-base);
}

.chart-wrapper:hover {
  border-color: var(--card-border-hover);
}

.chart-header {
  margin-bottom: var(--space-sm);
}

.chart-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
}

.chart-container {
  width: 100%;
  height: 320px;
}

/* Insights */
.insights {
  margin: var(--space-sm) 0;
}

.insight-chip {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  background: rgba(79, 140, 247, 0.04);
  border-left: 3px solid var(--accent);
  padding: var(--space-sm) var(--space-md);
  margin-bottom: var(--space-xs);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  font-size: var(--font-size-sm);
  animation: insightChipIn var(--transition-base) var(--ease-out) both;
}

@keyframes insightChipIn {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

.insight-icon {
  flex-shrink: 0;
}

/* Data table */
.data-table {
  margin: var(--space-sm) 0;
  overflow-x: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--card-border);
}

.data-table table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th, .data-table td {
  padding: var(--space-sm) var(--space-md);
  text-align: left;
  border-bottom: 1px solid var(--card-border);
  font-size: var(--font-size-sm);
}

.data-table th {
  color: var(--text-secondary);
  font-weight: var(--font-weight-semibold);
  background: var(--bg-elevated);
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
}

.data-table tbody tr {
  transition: background var(--transition-fast);
}

.data-table tbody tr:hover {
  background: rgba(79, 140, 247, 0.04);
}

/* Message actions */
.message-actions {
  margin-top: var(--space-sm);
  display: flex;
  gap: var(--space-sm);
}

.btn-save {
  background: var(--gradient4);
  color: white;
  font-size: var(--font-size-sm);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-sm);
  font-weight: var(--font-weight-medium);
  box-shadow: 0 2px 8px rgba(107, 203, 119, 0.2);
  transition: all var(--transition-base) var(--ease-out);
}

.btn-save:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(107, 203, 119, 0.3);
}

.btn-view {
  background: transparent;
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-sm);
  text-decoration: none;
  transition: all var(--transition-fast);
}

.btn-view:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* Thinking animation */
.thinking {
  color: var(--text-secondary);
  font-style: italic;
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-sm);
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--accent);
  animation: thinkingPulse 1.2s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes thinkingPulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
}

/* Datasource Switcher */
.datasource-switcher {
  padding: 8px var(--space-2xl);
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--card-border);
  background: rgba(79, 140, 247, 0.02);
}

.switch-label {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.ds-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ds-chip {
  padding: 4px 12px;
  border-radius: 16px;
  border: 1px solid var(--card-border);
  background: var(--card-bg);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.ds-chip:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.ds-chip.active {
  background: var(--gradient1);
  color: white;
  border-color: transparent;
}

.ds-count {
  font-size: 10px;
  opacity: 0.7;
}

/* Input Area */
.input-area {
  padding: var(--space-lg) var(--space-2xl);
  border-top: 1px solid var(--card-border);
  display: flex;
  gap: var(--space-md);
  align-items: flex-end;
  background: var(--bg);
  flex-wrap: wrap;
}

.hidden-file-input {
  display: none;
}

.btn-attach {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  color: var(--text-secondary);
  font-size: 18px;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-attach:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  background: rgba(79, 140, 247, 0.05);
}

.btn-attach:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-tag {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  background: rgba(79, 140, 247, 0.08);
  border: 1px solid rgba(79, 140, 247, 0.2);
  border-radius: var(--radius-md);
  padding: 4px 10px;
  font-size: var(--font-size-sm);
  color: var(--accent);
  max-width: 200px;
}

.file-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-remove {
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  font-size: 16px;
  padding: 0 2px;
  cursor: pointer;
  line-height: 1;
}

.file-remove:hover {
  color: var(--accent2);
}

.input-area textarea {
  flex: 1;
  resize: none;
  min-height: 42px;
  max-height: 120px;
  line-height: var(--line-height-base);
  font-family: inherit;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.input-area textarea:focus {
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.btn-send {
  background: var(--gradient1);
  color: white;
  font-weight: var(--font-weight-semibold);
  padding: var(--space-sm) var(--space-xl);
  border-radius: var(--radius-md);
  height: 42px;
  box-shadow: 0 2px 8px rgba(79, 140, 247, 0.2);
  transition: all var(--transition-base) var(--ease-out);
}

.btn-send:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(79, 140, 247, 0.3);
}

.btn-send:disabled {
  opacity: 0.5;
  transform: none;
  box-shadow: none;
}
</style>
