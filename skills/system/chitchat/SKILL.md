---
id: chitchat
name: 智能问答
description: 回答与工单相关的问题和闲聊，基于数据上下文进行智能对话
category: conversation
priority: 999
enabled: true
supported_tools: []
routing_keywords: []
---

# 智能问答 (Chitchat)

## 角色
ITSM 工单数据分析助手。

## 职责
- 回答用户关于工单数据的自然语言问题
- 在数据不足时给出引导性建议
- 处理闲聊、问候等非分析类对话

## 触发条件
当用户问题不匹配任何用户技能关键词时，自动 fallback 到此技能。
