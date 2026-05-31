"""LLM 驱动的意图解析器 + 规则引擎 fallback — 工单分析版本。"""

import json
import re
from typing import Optional

from backend.llm.base import LLMProvider
from backend.services.conversation_manager import ContextState


# 意图关键词 → 图表类型
INTENT_CHART_MAP = {
    '分布': 'pie', '占比': 'pie', '比例': 'pie', '结构': 'pie', '构成': 'pie',
    '排名': 'bar', '最多': 'bar', '最少': 'bar', 'TOP': 'bar', '排行': 'bar',
    '对比': 'stacked_bar', '交叉': 'stacked_bar', '比较': 'stacked_bar',
    '趋势': 'line', '变化': 'line', '走势': 'line',
    '细分': 'rose', '详情': 'rose',
}

# 意图关键词 → 工单 group_by 维度
INTENT_GROUP_MAP = {
    '状态': 'status', '工单状态': 'status',
    '服务组': 'service_group',
    '责任人': 'assignee', '处理人': 'assignee', '谁处理': 'assignee',
    '部门': 'department', '请求部门': 'department',
    '来源': 'source_channel', '渠道': 'source_channel',
    '故障原因': 'fault_group', '故障分组': 'fault_group',
    '原因类别': 'cause_category', '原因': 'cause_category',
    '业务系统': 'business_system', '模块': 'business_system',
    '解决人': 'resolver', '解决': 'resolver',
    '挂起': 'suspended', '挂起原因': 'suspended',
    '性质': 'nature',
    '处理方式': 'resolution_method',
    '周': 'weekly', '每周': 'weekly', '周报': 'weekly',
    '月': 'monthly', '每月': 'monthly', '月报': 'monthly',
    'SLA': 'sla', '时效': 'resolution_time', '解决时效': 'resolution_time',
    # 新增：故障根因与问题分类
    '根因': 'root_cause', '故障根因': 'root_cause', '深层原因': 'root_cause', '根本原因': 'root_cause',
    # 新增：重复工单/高频故障
    '重复': 'recurring', '反复': 'recurring', '高频': 'recurring', '同类工单': 'recurring', '相似工单': 'recurring',
    # 新增：运维质量
    '运维质量': 'ops_quality', '质量指标': 'ops_quality', '退回率': 'ops_quality', '一次解决率': 'ops_quality',
    # 新增：症状方案聚类
    '症状': 'symptom_solution', '方案': 'symptom_solution', '解决方式': 'symptom_solution', '聚类': 'symptom_solution',
    # 新增：请求人行为/组织
    '请求人': 'requester', '请求机构': 'requester', '请求部门': 'requester', '组织分布': 'requester',
    '谁提': 'requester', '高频用户': 'requester', '提工单最多': 'requester',
    # 新增：性质趋势
    '性质分布': 'nature_trend', '性质占比': 'nature_trend', '性质趋势': 'nature_trend',
}


class IntentParser:

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm = llm_provider
        self._use_llm = llm_provider is not None

    async def parse(
        self,
        user_message: str,
        context: ContextState,
        available_skills: list[dict] | None = None,
    ) -> dict:
        if self._use_llm:
            try:
                return await self._parse_with_llm(user_message, context, available_skills)
            except Exception:
                pass

        return self._parse_with_rules(user_message, context)

    async def _parse_with_llm(
        self,
        user_message: str,
        context: ContextState,
        available_skills: list[dict] | None = None,
    ) -> dict:
        system_prompt = f"""你是一个工单数据分析意图解析器。根据用户问题，提取结构化的查询意图，仅返回 JSON。

可用技能: {json.dumps(available_skills or [{"id": "ticket_analysis", "name": "工单分析"}], ensure_ascii=False)}
可用维度: status(状态), service_group(服务组), assignee(责任人), department(部门),
  source_channel(来源渠道), fault_group(故障原因分组), cause_category(原因类别),
  business_system(业务系统), nature(性质/各类性质占比), resolver(解决人),
  resolution_method(处理方式), weekly(周趋势), monthly(月趋势), sla(SLA趋势),
  resolution_time(解决时效), suspended(挂起),
  root_cause(故障根因分析), recurring(重复工单/高频故障挖掘),
  ops_quality(运维质量指标:退回率/挂起率/撤单率), symptom_solution(症状→方案聚类),
  requester(请求人行为与组织分布), nature_trend(性质趋势)
可选图表: bar(排名), pie(占比/分布), line(趋势), stacked_bar(交叉对比), horizontal_bar(横向排名)

当前上下文筛选条件: {json.dumps(context.active_filters, ensure_ascii=False)}

返回 JSON 格式:
{{
  "skill_id": "ticket_analysis" | "chitchat",
  "filters": {{"status": "...", "service_group": "...", "assignee": "..."}},
  "group_by": "status | service_group | root_cause | recurring | ops_quality | symptom_solution | requester | nature_trend",
  "chart_type": "bar | pie | line | stacked_bar | horizontal_bar | rose",
  "action": "query" | "chitchat"
}}

注意:
- 用户询问故障根因、深层原因 → group_by="root_cause", chart_type="bar"
- 用户询问重复问题、高频故障、同类工单 → group_by="recurring", chart_type="bar"
- 用户询问运维质量、退回率、挂起率 → group_by="ops_quality", chart_type="line"
- 用户询问症状对应方案、解决方案聚类 → group_by="symptom_solution", chart_type="bar"
- 用户询问请求人行为、谁提交最多、组织分布 → group_by="requester", chart_type="horizontal_bar"
- 用户询问各类性质占比 → group_by="nature_trend", chart_type="pie"
- 如果用户问题与工单数据无关（闲聊、问天气等），skill_id 设为 "chitchat"
- 仅返回 JSON，不要任何额外文字"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self.llm.chat_completion(messages, temperature=0.3, max_tokens=512)
        return self._extract_json(response)

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith('{'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"skill_id": "ticket_analysis", "filters": {}, "group_by": "status", "chart_type": "pie"}

    def _parse_with_rules(self, user_message: str, context: ContextState) -> dict:
        msg = user_message.lower()
        filters = dict(context.active_filters)

        # 检测 group_by
        group_by = 'status'
        for kw, gb in sorted(INTENT_GROUP_MAP.items(), key=lambda x: -len(x[0])):
            if kw in msg:
                group_by = gb
                break

        # 检测图表类型
        chart_type = 'pie'
        for kw, ct in INTENT_CHART_MAP.items():
            if kw in msg:
                chart_type = ct
                break

        # 趋势类自动用 line
        if group_by in ('weekly', 'monthly', 'sla'):
            chart_type = 'line'
            group_by = 'weekly' if group_by == 'weekly' else group_by

        # 重置上下文检测
        if any(kw in msg for kw in ['重新开始', '新对话', '重置', '清空', '换一个']):
            return {
                'action': 'reset_context',
                'skill_id': 'ticket_analysis',
                'filters': {},
                'group_by': 'status',
                'chart_type': 'pie',
            }

        # 闲聊/数据问答检测
        explain_keywords = ['为什么', '怎么', '如何', '解释', '凭什么', '根据什么',
                           '多少件', '多少个', '有几件', '有几个', '是多少', '有多少']
        ticket_keywords = ['工单', '状态', '服务组', '责任人', '部门', '来源', '故障',
                          'SLA', '挂起', '评价', '解决', '趋势', '排名', '占比', '分布',
                          '分析', '报表', '周报', '月报']
        is_explain_question = any(kw in msg for kw in explain_keywords)
        is_ticket = any(kw in msg for kw in ticket_keywords)

        if is_explain_question and is_ticket:
            return {
                'skill_id': 'chitchat',
                'action': 'chitchat',
                'filters': filters,
                'group_by': '',
                'chart_type': '',
            }

        if not is_ticket and not filters:
            return {
                'skill_id': 'chitchat',
                'action': 'chitchat',
                'filters': {},
                'group_by': '',
                'chart_type': '',
            }

        return {
            'skill_id': 'ticket_analysis',
            'filters': filters,
            'group_by': group_by,
            'chart_type': chart_type,
            'action': 'query',
        }
