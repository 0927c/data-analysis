---
id: data_query
name: 工单数据检索查询
description: 精确检索和筛选 ITSM 工单数据，回答具体工单查询问题
category: query
input_schema:
  filters:
    status: string
    assignee: string
    service_group: string
    department: string
    source: string
    source_channel: string
    cause_category: string
    fault_group: string
    nature: string
    date_from: string
    date_to: string
  limit: number
output_schema:
  records: list
  total: number
  filters: dict
supported_tools:
  - ticket_query
routing_keywords:
  - 查询
  - 检索
  - 查找
  - 筛选
  - 核对
  - 具体
  - 记录
  - 明细
  - 数据
  - KPI
  - 汇总
  - 工单
  - ticket
enabled: true
priority: 2
---

# 工单数据检索查询 Skill

## 功能
对 ITSM 工单数据进行精确检索和筛选，返回符合条件的原始工单数据和统计汇总。

## 支持的查询类型
| 查询类型 | 说明 | 返回格式 |
|---------|------|---------|
| summary_kpis | KPI 汇总指标 | 总数、月均、趋势 |
| status_distribution | 工单状态分布 | 状态名称、数量、占比 |
| service_group_distribution | 服务组分布 | 服务组名称、工单量 |
| assignee_distribution | 责任人处理量排名 | 责任人、工单数 |
| department_distribution | 请求部门分布 | 部门名称、工单量 |
| source_channel_distribution | 来源渠道分布 | 渠道名称、工单量 |
| fault_group_distribution | 故障原因分组 | 故障类别、数量 |
| cause_category_distribution | 原因类别分布 | 原因类别、数量 |
| business_system_distribution | 业务系统分布 | 系统名称、工单量 |
| weekly_trend | 每周工单趋势 | 周次、工单数 |
| monthly_trend | 每月工单趋势 | 月份、工单数 |
| sla_weekly_trend | SLA 达标率周趋势 | 周次、达标率 |
| recurring_tickets | 重复工单挖掘 | 故障原因、标题、重复次数 |
| symptom_solution_mapping | 症状→解决方案聚类 | 症状、推荐方案、解决耗时 |
| requester_behavior | 请求人行为分析 | 高频请求人/部门/机构 |
| ops_quality_metrics | 运维质量指标 | 退回率/挂起率/撤单率/SLA |
| fault_root_cause_analysis | 故障根因深度分析 | 原因类别→故障分组→症状三层钻取 |
| nature_trend | 性质占比与趋势 | 各类性质的占比 + 周趋势堆叠 |
| evaluation_summary | 满意度评价摘要 | 服务态度/技术水平/响应时效评分 |

## 筛选条件
- `status`: 工单状态（如：待处理、处理中、已解决、已关闭）
- `assignee`: 责任人姓名（模糊匹配）
- `service_group`: 所属服务组
- `department`: 请求人部门
- `source`: 来源渠道
- `cause_category`: 原因类别
- `fault_group`: 故障原因分组
- `nature`: 工单性质
- `date_from / date_to`: 日期范围（YYYY-MM-DD）

## 使用流程
1. 通过 `ticket_query` 工具执行查询
2. 对结果进行筛选、排序、分页
3. 结合 `chart_render` 工具生成可视化图表
4. 返回结构化数据和摘要统计
