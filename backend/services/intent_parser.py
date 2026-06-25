"""LLM 驱动的意图解析器 + 规则引擎 fallback — 工单分析版本。"""

from __future__ import annotations
import json
import re
from datetime import datetime, timedelta
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
    '业务系统': 'business_system', '模块': 'business_system', '系统': 'business_system',
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
        # ===== 本地 chitchat 预检测（快速路径，不走 LLM） =====
        if self._is_chitchat(user_message):
            return {
                'skill_id': 'chitchat',
                'action': 'chitchat',
                'filters': {},
                'group_by': '',
                'chart_type': '',
            }

        # 优先使用 FlueProvider 的专用意图识别端点
        if self.llm and hasattr(self.llm, 'parse_intent'):
            try:
                result = await self.llm.parse_intent(user_message)
                if result and result.get('skill_id'):
                    # 安全网：Flue 返回 chitchat 但消息包含明确分析关键词时，走规则引擎
                    if result.get('skill_id') == 'chitchat' and self._has_analysis_keywords(user_message):
                        print(f"[PARSER] Flue returned chitchat but message has analysis keywords, falling back to rules", flush=True)
                        return self._parse_with_rules(user_message, context)
                    return result
            except Exception as e:
                print(f"[PARSER] parse_intent failed: {e}, trying chat fallback", flush=True)

        # 其次用 LLM chat_completion（非 Flue 或 Flue 失败时）
        if self._use_llm:
            try:
                return await self._parse_with_llm(user_message, context, available_skills)
            except Exception as e:
                print(f"[PARSER] _parse_with_llm failed: {e}", flush=True)

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

**日期筛选（必须提取）**：
- 当用户提到具体时间（如"五月份"、"2026年5月"、"上周"、"最近一周"），必须在 filters 中添加 date_from 和 date_to
- "五月份"/"5月" → date_from="2026-05-01", date_to="2026-05-31"（用当前年份）
- "2026年5月" → date_from="2026-05-01", date_to="2026-05-31"
- "上周" → 计算上周一到上周日
- "最近一周" → 7天前到今天
- "上个月" → 上个月1号到上个月最后一天
- "本周" → 本周一到今天
- "今年" → 今年1月1号到今天

返回 JSON 格式:
{{
  "skill_id": "ticket_analysis" | "deep_analysis" | "report_export" | "chitchat",
  "filters": {{"status": "...", "service_group": "...", "date_from": "2026-05-01", "date_to": "2026-05-31"}},
  "group_by": "status | service_group | root_cause | recurring | ops_quality | symptom_solution | requester | nature_trend | business_system",
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
- 用户询问各系统/业务系统 → group_by="business_system", chart_type="bar"
- 如果用户问题与工单数据无关（闲聊、问天气等），skill_id 设为 "chitchat"
- 如果用户要求导出/生成完整分析报告（"导出报告"、"下载报告"），skill_id 设为 "report_export"
- **有日期时必须同时提取 date_from 和 date_to**
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

    # ===== 日期筛选提取 =====

    def _extract_date_filters(self, msg: str) -> dict:
        """从消息中提取日期范围筛选条件。"""
        now = datetime.now()
        year = now.year
        month = now.month

        # 中文月份映射
        cn_month_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
            '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12,
        }

        # 1. 匹配 "2026年5月" 或 "2026年五月"
        m = re.search(r'(\d{4})\s*年\s*(\d+|[一二三四五六七八九十]+)月', msg)
        if m:
            target_year = int(m.group(1))
            month_str = m.group(2)
            target_month = cn_month_map.get(month_str, int(month_str)) if month_str in cn_month_map else int(month_str)
            return self._month_range(target_year, target_month)

        # 2. 匹配 "5月" "五月份" "五月的" "5月份"
        m = re.search(r'(\d+|[一二三四五六七八九十]+)月[份的]?', msg)
        if m:
            month_str = m.group(1)
            target_month = cn_month_map.get(month_str, int(month_str)) if month_str in cn_month_map else int(month_str)
            return self._month_range(year, target_month)

        # 3. 匹配 "2026年5月1日" 到 "2026年5月31日" 或 "2026-05-01到2026-05-31"
        m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(?:到|至|-)\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})', msg)
        if m:
            return {
                'date_from': f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}',
                'date_to': f'{m.group(4)}-{int(m.group(5)):02d}-{int(m.group(6)):02d}',
            }

        # 4. 相对时间："上周" "上周的"
        if '上周' in msg:
            return self._last_week_range(now)

        # 5. "本周" "这周"
        if '本周' in msg or '这周' in msg:
            return self._this_week_range(now)

        # 6. "上个月" "上月"
        if '上个月' in msg or '上月' in msg:
            return self._last_month_range(year, month)

        # 7. "最近一周" "近一周" "最近7天" "近7天"
        if any(kw in msg for kw in ['最近一周', '近一周', '最近7天', '近7天']):
            return self._recent_days_range(now, 7)

        # 8. "最近一个月" "近一个月" "最近30天"
        if any(kw in msg for kw in ['最近一个月', '近一个月', '最近30天', '近30天']):
            return self._recent_days_range(now, 30)

        # 9. "今年" "本年度"
        if '今年' in msg or '本年度' in msg:
            return {'date_from': f'{year}-01-01', 'date_to': now.strftime('%Y-%m-%d')}

        # 10. "去年"
        if '去年' in msg or '上年度' in msg:
            return {'date_from': f'{year - 1}-01-01', 'date_to': f'{year - 1}-12-31'}

        return {}

    @staticmethod
    def _month_range(year: int, month: int) -> dict:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return {
            'date_from': f'{year}-{month:02d}-01',
            'date_to': f'{year}-{month:02d}-{last_day:02d}',
        }

    @staticmethod
    def _last_week_range(now: datetime) -> dict:
        # 上周一
        days_since_monday = now.weekday()  # 0=Monday
        this_monday = now - timedelta(days=days_since_monday)
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        return {
            'date_from': last_monday.strftime('%Y-%m-%d'),
            'date_to': last_sunday.strftime('%Y-%m-%d'),
        }

    @staticmethod
    def _this_week_range(now: datetime) -> dict:
        days_since_monday = now.weekday()
        this_monday = now - timedelta(days=days_since_monday)
        return {
            'date_from': this_monday.strftime('%Y-%m-%d'),
            'date_to': now.strftime('%Y-%m-%d'),
        }

    @staticmethod
    def _last_month_range(year: int, month: int) -> dict:
        if month == 1:
            return {'date_from': f'{year - 1}-12-01', 'date_to': f'{year - 1}-12-31'}
        import calendar
        last_day = calendar.monthrange(year, month - 1)[1]
        return {
            'date_from': f'{year}-{month - 1:02d}-01',
            'date_to': f'{year}-{month - 1:02d}-{last_day:02d}',
        }

    @staticmethod
    def _recent_days_range(now: datetime, days: int) -> dict:
        start = now - timedelta(days=days)
        return {
            'date_from': start.strftime('%Y-%m-%d'),
            'date_to': now.strftime('%Y-%m-%d'),
        }

    @staticmethod
    def _is_chitchat(message: str) -> bool:
        """本地快速检测：纯闲聊/问候/功能询问直接走 chitchat，不经过 LLM。

        两层判断：
        1. 命中明确的非数据意图模式 → chitchat
        2. 短消息（<=20字）且不含任何工单/数据关键词 → chitchat
        """
        msg = message.strip()
        msg_lower = msg.lower()

        # ===== 第一层：明确的非数据意图模式（无论长短） =====
        _definite_chitchat = [
            # 问候
            '你好', '您好', 'hi ', 'hello', 'hey',
            '在吗', '在不在', '有人吗',
            '早', '早上好', '晚上好', '中午好',
            '嗨', '哈喽',
            # 客套
            '谢谢', '感谢', 'thanks', 'thank you',
            '辛苦了',
            '再见', '拜拜', 'bye', 'goodbye',
            # 功能询问
            '你是谁', '你叫什么', '介绍下你自己',
            '你的功能', '你能做什么', '你能帮我', '你有什么用',
            '主要功能', '你会什么',
            # 无关话题
            '天气', '现在几点', '今天几号',
            '吃饭', '睡觉', '下班',
        ]
        if any(p in msg_lower for p in _definite_chitchat):
            # 确认不含工单关键词（防止 "你好，工单状态分布" 被误判）
            _ticket_keywords = [
                '工单', '状态', '分布', '趋势', '分析', '报表', '排名', '占比',
                '故障', 'SLA', '挂起', '解决', '部门', '来源', '渠道',
                '服务组', '责任人', '处理人', '评价', '退回', '撤单', '根因',
                '重复', '高频', '质量', '症状', '方案', '请求人', '性质',
                '数据', '图表', '统计', '总共', '一共',
            ]
            if not any(kw in msg_lower for kw in _ticket_keywords):
                return True

        # ===== 第二层：短消息 + 无工单关键词 =====
        if len(msg) > 20:
            return False

        _ticket_keywords_short = [
            '工单', '状态', '分布', '趋势', '分析', '报表', '排名', '占比',
            '故障', 'SLA', '挂起', '解决', '部门', '系统', '来源', '渠道',
            '服务组', '责任人', '处理人', '评价', '退回', '撤单', '根因',
            '重复', '高频', '质量', '症状', '方案', '请求人', '性质', '周', '月',
            '数据', '图表', '统计', '多少', '几个', '总共', '一共',
        ]
        if any(kw in msg_lower for kw in _ticket_keywords_short):
            return False

        # 短消息且无工单关键词 → 闲聊
        _short_chitchat = [
            '嗯', '哦', '好的', 'ok', 'okay', '好的呢',
            'yo',
        ]
        return any(p in msg_lower for p in _short_chitchat)

    @staticmethod
    def _has_analysis_keywords(message: str) -> bool:
        """检测消息是否包含明确的工单分析关键词（用于 Flue 误判 chitchat 时的安全网）。"""
        msg_lower = message.lower()
        _analysis_keywords = [
            '故障', '根因', '工单', 'SLA', '状态', '分布', '趋势', '分析',
            '排名', 'TOP', 'top', '占比', '服务组', '责任人', '部门', '系统',
            '挂起', '解决', '退回', '撤单', '重复', '高频', '质量', '症状',
            '方案', '请求人', '性质', '报表', '数据', '图表', '统计',
            '多少', '几个', '总共', '一共', '运维', '原因', '渠道', '来源',
        ]
        return any(kw in msg_lower for kw in _analysis_keywords)

    def _parse_with_rules(self, user_message: str, context: ContextState) -> dict:
        msg = user_message.lower()
        filters = dict(context.active_filters)

        # ===== 日期筛选提取 =====
        date_filters = self._extract_date_filters(msg)
        if date_filters:
            filters.update(date_filters)

        # 检测 group_by（先排除已匹配为日期关键词的 "月"）
        group_by = 'status'
        # 如果已提取日期筛选，跳过"月"/"每月"/"月报"等趋势类关键词
        skip_date_keywords = set()
        if date_filters:
            skip_date_keywords = {'月', '每月', '月报'}

        for kw, gb in sorted(INTENT_GROUP_MAP.items(), key=lambda x: -len(x[0])):
            if kw in skip_date_keywords:
                continue
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
                          '分析', '报表', '周报', '月报', '系统', '业务', '模块']
        is_explain_question = any(kw in msg for kw in explain_keywords)
        is_ticket = any(kw in msg for kw in ticket_keywords)

        # 包含工单相关关键词且有明确数据查询意图（多少/几个）→ 走工单分析，不走闲聊
        if is_explain_question and is_ticket:
            return {
                'skill_id': 'ticket_analysis',
                'filters': filters,
                'group_by': group_by,
                'chart_type': chart_type,
                'action': 'query',
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
