import { defineStore } from 'pinia'
import apiClient from '@/api/client.js'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token') || null,
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin',
  },

  actions: {
    async login(username, password) {
      const { data } = await apiClient.post('/auth/login', { username, password })
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))
    },

    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      apiClient.post('/auth/logout').catch(() => {})
    },
  },
})

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [],
    currentSessionId: null,
    messages: [],
    loading: false,
  }),

  actions: {
    async fetchSessions() {
      const { data } = await apiClient.get('/chat/sessions')
      this.sessions = data
    },

    async fetchMessages(sessionId) {
      const { data } = await apiClient.get(`/chat/sessions/${sessionId}/messages`)
      this.messages = data
    },

    async sendMessage(message, sessionId = null) {
      this.loading = true
      try {
        const { data } = await apiClient.post('/chat', { message, session_id: sessionId })
        // 新会话时从响应中获取 session_id
        if (!this.currentSessionId && data.session_id) {
          this.currentSessionId = data.session_id
        }
        // 用户消息已由 Chat.vue 添加，这里只添加 AI 响应
        this.messages.push({
          role: 'assistant',
          content: data.message,
          has_report: !!data.report_id,
          report_id: data.report_id,
          charts: data.charts,
          insights: data.insights,
          data_table: data.data_table,
          created_at: new Date().toISOString(),
        })
        return data
      } finally {
        this.loading = false
      }
    },

    async sendWithFile(file, message = '请帮我分析这个文件的数据', sessionId = null) {
      this.loading = true
      try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('message', message)
        if (sessionId) formData.append('session_id', sessionId)

        const { data } = await apiClient.post('/chat/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120000,
        })

        // 用户消息已由 Chat.vue 添加，这里只添加 AI 响应
        this.messages.push({
          role: 'assistant',
          content: data.message,
          has_report: !!data.report_id,
          report_id: data.report_id,
          charts: data.charts,
          insights: data.insights,
          data_table: data.data_table,
          created_at: new Date().toISOString(),
        })
        return data
      } finally {
        this.loading = false
      }
    },

    async deleteSession(sessionId) {
      await apiClient.delete(`/chat/sessions/${sessionId}`)
      this.sessions = this.sessions.filter((s) => s.id !== sessionId)
      if (this.currentSessionId === sessionId) {
        this.currentSessionId = null
        this.messages = []
      }
    },

    async resetContext(sessionId) {
      await apiClient.post(`/chat/sessions/${sessionId}/reset`)
    },
  },
})

export const useReportStore = defineStore('report', {
  state: () => ({
    reports: [],
    total: 0,
    currentReport: null,
    exportProgress: 0,
    isExporting: false,
  }),

  actions: {
    async fetchReports(page = 1, pageSize = 20, search = '') {
      const { data } = await apiClient.get('/reports', {
        params: { page, page_size: pageSize, search },
      })
      this.reports = data.items
      this.total = data.total
    },

    async fetchReport(id) {
      const { data } = await apiClient.get(`/reports/${id}`)
      this.currentReport = data
    },

    async deleteReport(id) {
      await apiClient.delete(`/reports/${id}`)
    },

    async exportHtml(id) {
      this.isExporting = true
      this.exportProgress = 10
      try {
        const response = await apiClient.get(`/reports/${id}/export/html`, { responseType: 'blob' })
        this.exportProgress = 80
        // 检查是否返回了错误 JSON（而非 HTML blob）
        if (response.data.type === 'application/json') {
          const errText = await response.data.text()
          throw new Error(JSON.parse(errText).detail || '导出失败')
        }
        const blob = new Blob([response.data], { type: 'text/html' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'report.html'
        a.click()
        URL.revokeObjectURL(url)
        this.exportProgress = 100
      } catch (err) {
        alert('导出 HTML 失败：' + (err.message || '未知错误'))
      } finally {
        this.isExporting = false
        setTimeout(() => { this.exportProgress = 0 }, 500)
      }
    },

    async exportExcel(id) {
      this.isExporting = true
      this.exportProgress = 10
      try {
        const response = await apiClient.get(`/reports/${id}/export/excel`, { responseType: 'blob' })
        this.exportProgress = 80
        if (response.data.type === 'application/json') {
          const errText = await response.data.text()
          throw new Error(JSON.parse(errText).detail || '导出失败')
        }
        const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'report.xlsx'
        a.click()
        URL.revokeObjectURL(url)
        this.exportProgress = 100
      } catch (err) {
        alert('导出 Excel 失败：' + (err.message || '未知错误'))
      } finally {
        this.isExporting = false
        setTimeout(() => { this.exportProgress = 0 }, 500)
      }
    },

    async uploadExcel(file, onProgress) {
      this.isExporting = true
      this.exportProgress = 0
      try {
        const formData = new FormData()
        formData.append('file', file)
        const { data } = await apiClient.post('/datasources/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120000,
          onUploadProgress: (e) => {
            this.exportProgress = Math.round(e.loaded / e.total * 80)
            if (onProgress) onProgress(this.exportProgress)
          },
        })
        this.exportProgress = 100
        return data
      } finally {
        this.isExporting = false
        setTimeout(() => { this.exportProgress = 0 }, 1000)
      }
    },
  },
})

export const useAnalyticsStore = defineStore('analytics', {
  state: () => ({
    summary: null,
    loading: false,
  }),

  actions: {
    async fetchSummary() {
      this.loading = true
      try {
        const { data } = await apiClient.get('/analytics/summary')
        this.summary = data
      } finally {
        this.loading = false
      }
    },

    async fetchData(endpoint, params = {}) {
      const { data } = await apiClient.get(`/analytics/${endpoint}`, { params })
      return data
    },
  },
})
