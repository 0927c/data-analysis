---
id: ticket_analysis
name: 工单数据分析
description: 分析 ITSM 工单 Excel 数据，按状态、服务组、责任人、故障原因等维度生成统计图表
category: analysis
input_schema:
  filters:
    status: string
    assignee: string
    department: string
    service_group: string
    source: string
    cause_category: string
    fault_group: string
  group_by: status
output_schema:
  data: distribution data with labels and values
  chart_type: pie
  insights: list
supported_tools:
  - ticket_query
  - chart_render
routing_keywords:
  - 状态
  - 服务组
  - 责任人
  - 部门
  - 来源
  - 故障原因
  - 根因
  - 重复
  - 高频
  - 运维质量
  - 症状
  - 方案
  - 聚类
  - 请求人
  - 组织
  - 分布
  - 占比
  - 排名
  - 趋势
  - SLA
  - 挂起
  - 评价
  - 满意度
  - 解决时效
  - KPI
  - 汇总
  - 周报
  - 月报
  - 性质
enabled: true
priority: 1
---

# 工单数据分析 Skill

## 功能
对 ITSM 工单数据进行多维度分析，生成 ECharts 可视化图表和洞察建议。

## 支持的分析维度
| 维度 | 查询类型 | 图表类型 |
|------|---------|---------|
| 状态分布 | status_distribution | pie |
| 服务组工作量 | service_group_distribution | horizontal_bar |
| 责任人处理量 | assignee_distribution | horizontal_bar |
| 部门分布 | department_distribution | bar |
| 来源渠道分布 | source_channel_distribution | pie |
| 故障原因分组 | fault_group_distribution | pie |
| 每周趋势 | weekly_trend | line |
| 每月趋势 | monthly_trend | line |
| SLA 周趋势 | sla_weekly_trend | line |
| 挂起原因分析 | suspended_breakdown | horizontal_bar |
| 满意度分析 | evaluation_summary | bar |
| 解决时效分桶 | resolution_time_buckets | bar |
| 原因类别分布 | cause_category_distribution | pie |
| 业务系统分布 | business_system_distribution | horizontal_bar |
| 服务组×状态交叉 | status_by_service_group | stacked_bar |
| **故障根因深度分析** | fault_root_cause_analysis | horizontal_bar |
| **故障原因趋势** | fault_cause_trend | line |
| **症状→方案聚类** | symptom_solution_mapping | horizontal_bar |
| **重复工单挖掘** | recurring_tickets | horizontal_bar |
| **各类性质占比/趋势** | nature_trend | pie + line |
| **请求人行为与组织分析** | requester_behavior | horizontal_bar + bar |
| **运维质量指标** | ops_quality_metrics | horizontal_bar |
| KPI 汇总 | summary_kpis | table |
