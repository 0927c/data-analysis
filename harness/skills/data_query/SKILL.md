---
id: data_query
name: 数据检索查询
description: 精确检索和筛选客诉数据，回答具体数据查询问题
category: query
input_schema:
  filters:
    customer: string
    date_range: string
    product_line: string
    defect_type: string
  limit: number
output_schema:
  records: list
  total: number
  filters: dict
supported_tools:
  - complaint_query
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
enabled: true
priority: 2
---

# 数据检索查询 Skill

## 功能
对 2,170 条客诉记录进行精确检索和筛选，返回符合条件的原始数据和统计汇总。

## 支持的查询类型
| 查询类型 | 说明 | 返回格式 |
|---------|------|---------|
| summary_kpis | KPI 汇总指标 | 总数、月均、趋势 |
| key_customers | 大客户排名 | 客户名称、投诉量、占比 |
| defect_top15 | 不良类型 TOP15 | 类型名称、数量、占比 |
| product_line_distribution | 产品线分布 | 产品线名称、数量 |
| cross_table | 产品线×原因交叉表 | 二维矩阵 |
| raw_records | 原始记录查询 | 数据明细列表 |

## 筛选条件
- `customer`: 客户名称（模糊匹配）
- `product_line`: 产品线名称
- `date_range`: 日期范围（YYYY-MM-DD ~ YYYY-MM-DD）
- `defect_type`: 不良类型
- `cause_category`: 原因大类（制造工艺/研发设计/客户因素/仓储物流/原料问题/原因不明）

## 使用流程
1. 通过 `complaint_query` 工具执行查询
2. 对结果进行筛选、排序、分页
3. 返回结构化数据和摘要统计
