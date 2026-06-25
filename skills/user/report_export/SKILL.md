---
id: report_export
name: 报告导出
description: 生成五章节结构化分析报告，支持 HTML 和 Excel 格式导出
category: export
input_schema:
  format: html|excel
  title: string
  filters: object
output_schema:
  format: string
  file_path: string
  file_size: number
  report_sections: list
routing_keywords:
  - 导出
  - 报告
  - 生成报告
  - 下载报告
  - HTML报告
  - Excel报告
  - 完整报告
  - 分析报告
enabled: true
priority: 2
---

# 报告导出 Skill

## 功能
调用系统全量数据接口，生成五章节结构化分析报告，支持导出为 HTML（含 ECharts 交互图表）或 Excel 格式。

## 报告章节结构
| 章节 | 内容 | 数据来源 |
|------|------|---------|
| 1. 摘要概览 | KPI 指标、工单趋势、关键发现 | `get_summary_kpis` + `get_weekly_trend` + `generate_insights` |
| 2. 产品线分析 | 各服务组工单量、故障原因分布、TOP 原因类别 | `get_service_group_distribution` + `get_fault_group_distribution` + `get_cause_category_distribution` + `get_business_system_distribution` |
| 3. 原因分析 | 故障根因细分、重复故障、症状→方案聚类 | `get_fault_root_cause_analysis` + `get_recurring_tickets` + `get_symptom_solution_mapping` |
| 4. 大客户分析 | 高频请求人 TOP 客户、部门/机构分布 | `get_requester_behavior` + `get_department_distribution` |
| 5. 洞察建议 | 运维质量指标、数据驱动改进建议 | `get_ops_quality_metrics` + `generate_insights` |

## 导出格式
| 格式 | 说明 | 特点 |
|------|------|------|
| HTML | 交互式网页报告 | 内嵌 ECharts 图表、目录导航、响应式布局 |
| Excel | 电子表格报告 | 多 Sheet（封面、KPI、数据明细、洞察建议、图表数据） |

## 触发方式
用户说"导出报告"、"生成分析报告"、"下载HTML报告"等关键词时触发。
