import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: inject JWT token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      // 用 router 跳转避免整页刷新丢失状态
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient

/**
 * 文件上传辅助方法（支持进度回调）。
 * 用法: apiClient.uploadFile('/datasources/upload', file, (p) => console.log(p))
 */
apiClient.uploadFile = (url, file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: onProgress,
  })
}
