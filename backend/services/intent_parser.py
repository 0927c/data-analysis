"""LLM 驱动的意图解析器 + 规则引擎 fallback。"""

import json
import re
from typing import Optional

from backend.config import settings
from backend.llm.base import create_llm_provider, LLMProvider
from backend.services.conversation_manager import ContextState


# 产品线关键词映射（18 条）
PRODUCT_LINES = [
    'APP', 'HPP', 'ABS', 'APA', 'PA', 'PC', 'AEP', 'PBT',
    'HIP', 'PPE', 'FE', 'RJ', 'AAB', 'PVC', 'LFT', 'DS', 'POM', 'GD4',
]

# 意图关键词 → 图表类型
INTENT_CHART_MAP = {
    '分布': 'pie', '占比': 'pie', '比例': 'pie', '结构': 'pie', '构成': 'pie',
    '排名': 'bar', '最多': 'bar', '最少': 'bar', 'TOP': 'bar', '排行': 'bar',
    '对比': 'stacked_bar', '交叉': 'stacked_bar', '比较': 'stacked_bar',
    '趋势': 'line', '变化': 'line',
    '细分': 'rose', '详情': 'rose',
}

# 意图关键词 → group_by
INTENT_GROUP_MAP = {
    '产品线': 'product_line', '产品': 'product_line',
    '原因': 'cause_category', '根因': 'cause_category',
    '不良': 'defect_type', '缺陷': 'defect_type',
    '客户': 'customer', '大客户': 'customer',
}

# 原因大类关键词
CAUSE_CATEGORIES = ['制造原因', '研发原因', '客户原因', '仓储原因', '原料原因', '原因不明', '市场原因', '销管原因']


class IntentParser:
    """意图解析器：优先 LLM，不可用时降级规则引擎。"""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm = llm_provider
        self._use_llm = llm_provider is not None

    async def parse(
        self,
        user_message: str,
        context: ContextState,
        available_skills: list[dict] | None = None,
    ) -> dict:
        """解析用户意图，返回结构化结果。"""
        if self._use_llm:
            try:
                return await self._parse_with_llm(user_message, context, available_skills)
            except Exception:
                # LLM 不可用，降级到规则引擎
                pass

        return self._parse_with_rules(user_message, context)

    async def _parse_with_llm(
        self,
        user_message: str,
        context: ContextState,
        available_skills: list[dict] | None = None,
    ) -> dict:
        system_prompt = f"""你是一个报表分析意图解析器。根据用户问题，提取结构化的查询意图，仅返回 JSON。

可用技能: {json.dumps(available_skills or [{"id": "complaint_analysis", "name": "客诉分析"}], ensure_ascii=False)}
可用维度: product_line, cause_category, defect_type, customer, time_range
可选产品线: {', '.join(PRODUCT_LINES)}
可选原因大类: {', '.join(CAUSE_CATEGORIES)}
可选图表: bar(排名), pie(占比/分布), stacked_bar(交叉对比), horizontal_bar(横向排名), rose(细分详情)

当前上下文筛选条件: {json.dumps(context.active_filters, ensure_ascii=False)}

返回 JSON 格式:
{{
  "skill_id": "complaint_analysis" | "chitchat",
  "filters": {{"product_line": "...", "cause_category": "..."}},
  "group_by": "cause_category | product_line | defect_type | customer",
  "chart_type": "bar | pie | stacked_bar | horizontal_bar | rose",
  "action": "query" | "chitchat"
}}

注意:
- 如果用户要查看数据的分布、排名、对比等，skill_id 设为 "complaint_analysis"，action 设为 "query"
- 如果用户问题与客诉数据无关（如闲聊、问天气、问知识等），skill_id 设为 "chitchat"，action 设为 "chitchat"
- **如果用户在询问数据背后的原因、解释分析结果、问“为什么”、“怎么分析出来的”、“如何得出”等问题，skill_id 设为 "chitchat"，action 设为 "chitchat"**（这类解释性问题需要 AI 结合数据上下文回答，不是简单出图表）
- **如果用户在询问具体数量、数字答案（如“XX有多少件”、“XX是多少”、“XX有几个”），skill_id 设为 "chitchat"，action 设为 "chitchat"**（这类简单数据查询用文字直接回答，不需要生成报表图表）
- **如果用户提到具体的不良类型名称（如“颜色波动”、“标签贴错”、“黑点”等）并询问数量、分布、原因，skill_id 设为 "chitchat"，action 设为 "chitchat"**（具体不良类型的问答由 AI 结合数据上下文回答更全面）
- 如果用户提到具体产品线（如 APP），在 filters 中设置 product_line
- 如果用户说"所有产品线"或不指定，filters 中不包含 product_line（用上下文中已有的）
- 如果用户说"只看XX"或"排除XX"，更新对应 filter
- 仅返回 JSON，不要任何额外文字"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self.llm.chat_completion(messages, temperature=0.3, max_tokens=512)
        return self._extract_json(response)

    def _extract_json(self, text: str) -> dict:
        """从 LLM 响应中提取 JSON。"""
        text = text.strip()
        # 尝试直接解析
        if text.startswith('{'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        # 尝试找 JSON 块
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # 兜底
        return {"skill_id": "complaint_analysis", "filters": {}, "group_by": "cause_category", "chart_type": "pie"}

    def _parse_with_rules(self, user_message: str, context: ContextState) -> dict:
        """规则引擎 fallback：关键词 + 正则匹配。"""
        msg = user_message.lower()
        filters = dict(context.active_filters)  # copy current context

        # 检测产品线
        for pl in PRODUCT_LINES:
            if pl.lower() in msg:
                # 检查是否是排除
                if f'不看{pl}' in msg or f'不看{pl.lower()}' in msg:
                    filters.pop('product_line', None)
                elif f'只看{pl}' in msg or f'只看{pl.lower()}' in msg or pl.lower() in msg:
                    filters['product_line'] = pl
                break

        # 检查是否清除所有筛选
        if any(kw in msg for kw in ['所有产品线', '全部产品', '整体', '汇总']):
            filters.pop('product_line', None)

        # 检测原因大类
        for cc in CAUSE_CATEGORIES:
            if cc in msg:
                filters['cause_category'] = cc
                break

        # 检测 group_by
        group_by = 'cause_category'  # default
        for kw, gb in INTENT_GROUP_MAP.items():
            if kw in msg:
                group_by = gb
                break

        # 检测图表类型
        chart_type = 'pie'  # default
        for kw, ct in INTENT_CHART_MAP.items():
            if kw in msg:
                chart_type = ct
                break

        # 重置上下文检测
        if any(kw in msg for kw in ['重新开始', '新对话', '重置', '清空', '换一个']):
            return {
                'action': 'reset_context',
                'skill_id': 'complaint_analysis',
                'filters': {},
                'group_by': 'cause_category',
                'chart_type': 'pie',
            }

    # 闲聊/数据问答检测
        # "为什么/怎么/如何/解释" + 数据关键词 = 数据问答，走 chitchat（带数据上下文）
        explain_keywords = ['为什么', '怎么', '如何', '解释', '为什么', '凭什么', '根据什么', '分析出',
                           '多少件', '多少个', '有几件', '有几个', '是多少', '有多少']
        is_explain_question = any(kw in msg for kw in explain_keywords)
        complaint_keywords = ['投诉', '客诉', '产品线', '不良', '原因', '缺陷', '客户', '制造', '研发', '仓储', '分析', '报表', '排名', '占比', '分布', 'TOP', 'top', '交叉', '对比', '大客户']
        is_complaint = any(kw in msg for kw in complaint_keywords)

        # 具体不良类型名称 → 直接走 chitchat（数量查询/分布问答由AI文字回答）
        defect_names = ['颜色波动', '标签贴错', '黑点', '色差', '外观', '性能不达标', '重量不达标',
                        '混色不均', '配色不均', '杂质', '缩水', '变形', '气泡', '划痕']
        has_defect_name = any(name in msg for name in defect_names)

        if (is_explain_question and is_complaint) or has_defect_name:
            # 数据解释类问题 → chitchat（带数据上下文让 LLM 回答）
            return {
                'skill_id': 'chitchat',
                'action': 'chitchat',
                'filters': filters,
                'group_by': '',
                'chart_type': '',
            }

        if not is_complaint and not filters and group_by == 'cause_category' and chart_type == 'pie':
            # 既无筛选条件，也匹配不到投诉关键词 → 纯闲聊
            return {
                'skill_id': 'chitchat',
                'action': 'chitchat',
                'filters': {},
                'group_by': '',
                'chart_type': '',
            }

        return {
            'skill_id': 'complaint_analysis',
            'filters': filters,
            'group_by': group_by,
            'chart_type': chart_type,
            'action': 'query',
        }
