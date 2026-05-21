---
id: complaint_analysis
name: 客诉数据分析
description: 分析客诉 Excel 数据，按产品线、原因类别、不良类型等维度生成统计图表
category: analysis
input_schema:
  filters:
    product_line: string
    cause_category: string
    defect_type: string
  group_by: product_line
output_schema:
  data: distribution data with labels and values
  chart_type: pie
  insights: list
supported_tools:
  - complaint_query
  - chart_render
routing_keywords:
  - 产品线
  - 原因
  - 分布
  - 占比
  - 排名
  - 不良
  - 交叉
  - 细分
  - 洞察
  - KPI
  - 汇总
enabled: true
priority: 1
---

# 客诉数据分析 Skill

## 功能
对 2,170 条客诉记录进行多维度分析，生成 ECharts 可视化图表和洞察建议。

## 支持的分析维度
| 维度 | 查询类型 | 图表类型 |
|------|---------|---------|
| 产品线分布 | product_line_distribution | horizontal_bar |
| 原因大类占比 | root_cause_distribution | pie |
| 不良类型 TOP15 | defect_top15 | bar |
| 产品线×原因交叉表 | cross_table | stacked_bar |
| 大客户排名 | key_customers | horizontal_bar |
| 制造原因细分 | mfg_defect_breakdown | rose |
| 研发原因细分 | rnd_defect_breakdown | rose |
| 客户原因细分 | cli_defect_breakdown | rose |
| 仓储原因细分 | wh_defect_breakdown | rose |
| KPI 汇总 | summary_kpis | - |
| 洞察建议 | insights | - |

## 原因大类定义
| 类别 | 子类别数 | 说明 |
|------|---------|------|
| 制造工艺 | 14 | 封口/缝包、配色/混色、清洗、碳化等 |
| 研发设计 | 5 | 配方变更、标准不清、研发不稳定等 |
| 客户因素 | 6 | 检测方法差异、加工参数、沟通偏差等 |
| 仓储物流 | 11 | 标签错误、包装混淆、防护不足等 |
| 原料问题 | 2 | 原料不良、色板老化 |
| 原因不明 | 1 | 无法归类到上述类别 |

## 使用流程
1. 通过 `complaint_query` 工具获取结构化数据
2. 通过 `chart_render` 工具生成 ECharts option
3. 组装响应：message + charts[] + insights[] + data_table
