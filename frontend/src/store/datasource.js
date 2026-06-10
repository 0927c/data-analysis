import { defineStore } from 'pinia'
import apiClient from '@/api/client.js'

export const useDatasourceStore = defineStore('datasource', {
  state: () => ({
    datasources: [],           // 所有数据源
    primaryDatasourceId: null, // 当前活跃数据源 ID
    metadataCache: {},         // ds_id -> metadata
    loading: false,
  }),

  getters: {
    primaryDatasource: (state) =>
      state.datasources.find(ds => ds.id === state.primaryDatasourceId),
    activeDatasources: (state) => state.datasources,
    canSwitch: (state) => state.datasources.length > 1,
  },

  actions: {
    async fetchDatasources() {
      this.loading = true
      try {
        const { data } = await apiClient.get('/datasources/with-metadata')
        this.datasources = data
        // 如果没有设置 primary，默认选第一个
        if (!this.primaryDatasourceId && data.length > 0) {
          this.primaryDatasourceId = data[0].id
        }
      } catch (err) {
        console.error('获取数据源列表失败:', err)
      } finally {
        this.loading = false
      }
    },

    async fetchMetadata(datasourceId) {
      if (this.metadataCache[datasourceId]) {
        return this.metadataCache[datasourceId]
      }
      try {
        const { data } = await apiClient.get(`/datasources/${datasourceId}/metadata`)
        this.metadataCache[datasourceId] = data
        return data
      } catch (err) {
        console.error('获取元数据失败:', err)
        return null
      }
    },

    switchPrimary(datasourceId) {
      this.primaryDatasourceId = datasourceId
    },

    async switchPrimaryRemote(sessionId, datasourceId) {
      try {
        const { data } = await apiClient.post(
          `/chat/sessions/${sessionId}/switch-datasource?datasource_id=${datasourceId}`
        )
        this.primaryDatasourceId = datasourceId
        return data
      } catch (err) {
        console.error('切换数据源失败:', err)
        throw err
      }
    },
  },
})
