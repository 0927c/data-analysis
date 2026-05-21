"""Skill 执行引擎：注册、分发、执行报表分析技能。"""

import json
from typing import Callable, Optional

from backend.services.complaint_processor import ComplaintProcessor
from backend.services.chart_renderer import (
    render_pie, render_bar, render_stacked_bar, render_horizontal_bar, render_rose,
)


class SkillEngine:
    """Skill 注册与执行分发器。"""

    def __init__(self, processor: ComplaintProcessor, llm_provider=None):
        self.processor = processor
        self.llm = llm_provider
        self._skills: dict[str, dict] = {}
        self._register_complaint_analysis()
        self._register_chitchat()

    def register_skill(self, skill_id: str, metadata: dict):
        self._skills[skill_id] = metadata

    def get_available_skills(self) -> list[dict]:
        return [
            {'id': sid, 'name': s['name'], 'description': s.get('description', ''), 'enabled': s.get('enabled', True)}
            for sid, s in self._skills.items()
        ]

    async def execute_skill(self, skill_id: str, intent: dict) -> dict:
        """执行指定 skill，返回报告数据。"""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill 不存在: {skill_id}")
        if not skill.get('enabled', True):
            raise ValueError(f"Skill 已禁用: {skill.get('name', skill_id)}")

        handler = skill['handler']
        return await handler(intent)

    def _register_complaint_analysis(self):
        """注册客诉分析 skill。"""
        self.register_skill('complaint_analysis', {
            'name': '客诉分析',
            'description': '支持按产品线、原因分类、时间等维度分析客诉数据',
            'enabled': True,
            'handler': self._handle_complaint_analysis,
        })

    async def _handle_complaint_analysis(self, intent: dict) -> dict:
        """客诉分析 skill 处理器。"""
        if not self.processor:
            return {
                'message': '暂无可用的数据源，请先上传 Excel 文件或配置数据源路径。',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        filters = intent.get('filters', {})
        group_by = intent.get('group_by', 'cause_category')
        chart_type = intent.get('chart_type', 'pie')

        # 根据 group_by 和 chart_type 选择数据和方法
        charts = []
        insights = []
        data_table = None
        summary = ''

        kpis = self.processor.get_summary_kpis(filters)

        if group_by == 'cause_category' or chart_type == 'pie':
            # 原因大类分布
            dist = self.processor.get_root_cause_distribution(filters)
            charts.append({
                'id': 'chart_root_cause',
                'title': '原因大类分布',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件投诉，原因大类分布如上。'

        elif group_by == 'product_line' or chart_type == 'bar':
            # 产品线分布
            dist = self.processor.get_product_line_distribution(filters)
            charts.append({
                'id': 'chart_product_line',
                'title': '产品线投诉分布',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件投诉，覆盖 {kpis["product_line_count"]} 条产品线。'

        elif group_by == 'defect_type':
            # 不良类型 TOP
            top = self.processor.get_defect_top15(filters)
            charts.append({
                'id': 'chart_defect_top',
                'title': '不良类型 TOP',
                'type': 'bar',
                'option': render_bar(top['labels'], top['values']),
            })
            summary = f'共 {kpis["total"]} 件投诉，不良类型分布如上。'

        elif chart_type == 'stacked_bar':
            # 产品线 × 原因交叉
            ct = self.processor.get_cross_table(filters)
            charts.append({
                'id': 'chart_cross',
                'title': '产品线 × 原因交叉分析',
                'type': 'stacked_bar',
                'option': render_stacked_bar(ct['products'], ct['causes']),
            })
            summary = f'共 {kpis["total"]} 件投诉，各产品线原因结构对比如上。'

        elif chart_type == 'rose':
            # 根据当前 filter 选择细分图表
            if filters.get('cause_category') == '制造原因':
                data = self.processor.get_mfg_defect_breakdown(filters)
            elif filters.get('cause_category') == '研发原因':
                data = self.processor.get_rnd_defect_breakdown(filters)
            elif filters.get('cause_category') == '客户原因':
                data = self.processor.get_cli_defect_breakdown(filters)
            elif filters.get('cause_category') == '仓储原因':
                data = self.processor.get_wh_defect_breakdown(filters)
            else:
                data = self.processor.get_mfg_defect_breakdown(filters)

            charts.append({
                'id': 'chart_rose',
                'title': f'{filters.get("cause_category", "制造原因")}细分',
                'type': 'rose',
                'option': render_rose(data['labels'], data['values']),
            })
            summary = f'{filters.get("cause_category", "制造原因")}细分如上。'

        elif group_by == 'customer':
            kc = self.processor.get_key_customers(filters)
            charts.append({
                'id': 'chart_key_customers',
                'title': '大客户投诉排名',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(
                    kc['labels'], kc['values'],
                    color=('#9b59b6', '#c39bd3'),
                ),
            })
            summary = f'大客户投诉共 {kpis["key_customer_count"]} 件，占总投诉 {kpis["key_customer_ratio"]}%。'

        # 生成洞察
        insights = self.processor.generate_insights(filters)

        # 数据表
        data_table = self._build_data_table(group_by, filters)

        return {
            'message': summary,
            'charts': charts,
            'insights': insights,
            'data_table': data_table,
        }

    def _build_data_table(self, group_by: str, filters: dict) -> dict:
        """构建数据明细表格。"""
        if group_by == 'cause_category':
            dist = self.processor.get_root_cause_distribution(filters)
            total = sum(dist['values'])
            rows = [
                [label, str(value), f'{round(value / total * 100, 1) if total else 0}%']
                for label, value in zip(dist['labels'], dist['values'])
            ]
            return {'headers': ['原因分类', '数量', '占比'], 'rows': rows}

        elif group_by == 'product_line':
            dist = self.processor.get_product_line_distribution(filters)
            total = sum(dist['values'])
            rows = [
                [label, str(value), f'{round(value / total * 100, 1) if total else 0}%']
                for label, value in zip(dist['labels'], dist['values'])
            ]
            return {'headers': ['产品线', '数量', '占比'], 'rows': rows}

        elif group_by == 'defect_type':
            top = self.processor.get_defect_top15(filters)
            total = sum(top['values'])
            rows = [
                [label, str(value), f'{round(value / total * 100, 1) if total else 0}%']
                for label, value in zip(top['labels'], top['values'])
            ]
            return {'headers': ['不良类型', '数量', '占比'], 'rows': rows}

        elif group_by == 'customer':
            kc = self.processor.get_key_customers(filters)
            rows = [[label, str(value)] for label, value in zip(kc['labels'], kc['values'])]
            return {'headers': ['客户', '投诉数'], 'rows': rows}

        kpis = self.processor.get_summary_kpis(filters)
        return {'headers': ['指标', '值'], 'rows': [
            ['总投诉数', str(kpis['total'])],
            ['产品线数', str(kpis['product_line_count'])],
            ['原因不明', f'{kpis["unknown_count"]}件 ({kpis["unknown_ratio"]}%)'],
            ['大客户投诉', f'{kpis["key_customer_count"]}件 ({kpis["key_customer_ratio"]}%)'],
        ]}

    # ===== 闲聊 Skill =====

    def _register_chitchat(self):
        """注册闲聊 skill。"""
        self.register_skill('chitchat', {
            'name': '闲聊助手',
            'description': '回答与客诉数据无关的通用问题',
            'enabled': True,
            'handler': self._handle_chitchat,
        })

    async def _handle_chitchat(self, intent: dict) -> dict:
        """闲聊/数据问答 skill 处理器：转发给 LLM，带数据上下文。"""
        user_message = intent.get('message', '')

        if not self.llm:
            return {
                'message': '你好！我是客诉数据分析助手，主要负责分析投诉数据。如果你有数据分析相关的问题，我很乐意帮忙！',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        # 构建数据上下文
        data_context = ""
        if self.processor:
            try:
                kpis = self.processor.get_summary_kpis()
                rc_dist = self.processor.get_root_cause_distribution()
                pl_dist = self.processor.get_product_line_distribution()
                defect_top = self.processor.get_defect_top15(filters=None, top_n=5)
                mfg = self.processor.get_mfg_defect_breakdown()
                rnd = self.processor.get_rnd_defect_breakdown()
                cli = self.processor.get_cli_defect_breakdown()
                wh = self.processor.get_wh_defect_breakdown()

                cause_details = []
                for label, value in zip(rc_dist['labels'], rc_dist['values']):
                    cause_details.append(f"{label}: {value}件")

                data_context = f"""\n当前客诉数据摘要：
- 总投诉数: {kpis['total']}件
- 产品线数: {kpis['product_line_count']}条
- 原因大类分布: {', '.join(cause_details)}
- 产品线投诉TOP5: {', '.join([f'{l}({v}件)' for l, v in zip(pl_dist['labels'][:5], pl_dist['values'][:5])])}
- 不良类型TOP5: {', '.join([f'{l}({v}件)' for l, v in zip(defect_top['labels'][:5], defect_top['values'][:5])])}
- 制造原因细分: {', '.join([f'{l}({v}件)' for l, v in zip(mfg['labels'][:5], mfg['values'][:5])])}
- 研发原因细分: {', '.join([f'{l}({v}件)' for l, v in zip(rnd['labels'][:5], rnd['values'][:5])])}
- 客户原因细分: {', '.join([f'{l}({v}件)' for l, v in zip(cli['labels'][:5], cli['values'][:5])])}
- 仓储原因细分: {', '.join([f'{l}({v}件)' for l, v in zip(wh['labels'][:5], wh['values'][:5])])}
- 原因不明: {kpis['unknown_count']}件 ({kpis['unknown_ratio']}%)

分析方法：根据"初步调查"列的文本，使用46条正则规则提取原因关键词（如"标签贴错"→仓储原因，"配色/混色不均"→制造原因），再映射到5大类：制造原因、研发原因、客户原因、仓储原因、原料原因。无法匹配的归为"原因不明"。"""
            except Exception:
                data_context = ""

        system_prompt = (
            "你是金发集团的客诉数据分析助手。你可以回答通用问题，"
            "但你的专长是客诉数据分析。回答要准确、简洁，不超过200字。"
            "如果用户问的数据相关问题，请基于提供的数据摘要回答。"
            "如果用户问分析方法，请解释正则规则提取+大类映射的方法论。"
            f"{data_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            reply = await self.llm.chat_completion(messages, temperature=0.7, max_tokens=512)
        except Exception:
            reply = '抱歉，我暂时无法回答，请稍后再试。'

        return {
            'message': reply,
            'charts': [],
            'insights': [],
            'data_table': None,
        }
