"""Skill 执行引擎：注册、分发、执行报表分析技能。"""

import json
import os
import re
from typing import Callable, Optional

from backend.services.complaint_processor import ComplaintProcessor
from backend.services.chart_renderer import (
    render_pie, render_bar, render_stacked_bar, render_horizontal_bar, render_rose,
)

# harness/skills/ 目录路径
SKILLS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'harness', 'skills')


def _parse_skill_md(filepath: str) -> Optional[dict]:
    """解析 SKILL.md 的 YAML frontmatter，返回元数据字典。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return None

    # 提取 --- ... --- 之间的 frontmatter
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return None

    meta = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()
            # 只取顶层简单字段，嵌套结构忽略
            if val and key in ('id', 'name', 'description', 'category', 'enabled', 'priority'):
                if val.lower() == 'true':
                    val = True
                elif val.lower() == 'false':
                    val = False
                elif val.isdigit():
                    val = int(val)
                meta[key] = val
    return meta if meta.get('id') else None


class SkillEngine:
    """Skill 注册与执行分发器。"""

    def __init__(self, processor: ComplaintProcessor, llm_provider=None):
        self.processor = processor
        self.llm = llm_provider
        self._skills: dict[str, dict] = {}
        self._handlers: dict[str, Callable] = {
            'complaint_analysis': self._handle_complaint_analysis,
            'data_query': self._handle_data_query,
            'report_export': self._handle_report_export,
        }
        # 从 harness/skills/ 目录自动扫描并注册
        self._auto_discover_skills()
        # 内置 skill（无 harness 文件）
        self._register_chitchat()

    def _auto_discover_skills(self):
        """扫描 harness/skills/ 目录，自动注册所有 SKILL.md 定义的 skill。"""
        if not os.path.isdir(SKILLS_DIR):
            # 目录不存在时 fallback 到硬编码
            self._register_complaint_analysis()
            return

        for entry in sorted(os.listdir(SKILLS_DIR)):
            skill_dir = os.path.join(SKILLS_DIR, entry)
            skill_md = os.path.join(skill_dir, 'SKILL.md')
            if not os.path.isfile(skill_md):
                continue

            meta = _parse_skill_md(skill_md)
            if not meta:
                continue

            sid = meta['id']
            handler = self._handlers.get(sid)
            if not handler:
                # 无对应 handler 的 skill 跳过
                continue

            self.register_skill(sid, {
                'name': meta.get('name', sid),
                'description': meta.get('description', ''),
                'enabled': meta.get('enabled', True),
                'category': meta.get('category', ''),
                'priority': meta.get('priority', 99),
                'handler': handler,
            })

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

    # ===== 客诉分析 Skill =====

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

    # ===== 数据检索查询 Skill =====

    async def _handle_data_query(self, intent: dict) -> dict:
        """数据检索查询 skill 处理器：精确检索客诉数据。"""
        if not self.processor:
            return {
                'message': '暂无可用的数据源，请先上传 Excel 文件。',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        filters = intent.get('filters', {})
        query_type = intent.get('query_type', 'summary_kpis')

        charts = []
        data_table = None
        summary = ''

        if query_type == 'key_customers':
            kc = self.processor.get_key_customers(filters)
            charts.append({
                'id': 'chart_key_customers',
                'title': '大客户投诉排名',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(kc['labels'], kc['values'], color=('#9b59b6', '#c39bd3')),
            })
            rows = [[l, str(v)] for l, v in zip(kc['labels'], kc['values'])]
            data_table = {'headers': ['客户', '投诉数'], 'rows': rows}
            summary = f'大客户投诉排名查询完成，共 {len(kc["labels"])} 个客户。'

        elif query_type == 'defect_top15':
            top = self.processor.get_defect_top15(filters)
            charts.append({
                'id': 'chart_defect_top15',
                'title': '不良类型 TOP15',
                'type': 'bar',
                'option': render_bar(top['labels'], top['values']),
            })
            total = sum(top['values'])
            rows = [[l, str(v), f'{round(v / total * 100, 1) if total else 0}%'] for l, v in zip(top['labels'], top['values'])]
            data_table = {'headers': ['不良类型', '数量', '占比'], 'rows': rows}
            summary = f'不良类型 TOP15 查询完成。'

        elif query_type == 'product_line_distribution':
            dist = self.processor.get_product_line_distribution(filters)
            charts.append({
                'id': 'chart_pl_dist',
                'title': '产品线分布',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            total = sum(dist['values'])
            rows = [[l, str(v), f'{round(v / total * 100, 1) if total else 0}%'] for l, v in zip(dist['labels'], dist['values'])]
            data_table = {'headers': ['产品线', '数量', '占比'], 'rows': rows}
            summary = f'产品线分布查询完成，共 {len(dist["labels"])} 条产品线。'

        elif query_type == 'cross_table':
            ct = self.processor.get_cross_table(filters)
            charts.append({
                'id': 'chart_cross',
                'title': '产品线×原因交叉表',
                'type': 'stacked_bar',
                'option': render_stacked_bar(ct['categories'], ct['series']),
            })
            summary = '产品线×原因交叉查询完成。'

        else:
            # summary_kpis fallback
            kpis = self.processor.get_summary_kpis(filters)
            rows = [
                ['总投诉数', str(kpis['total'])],
                ['产品线数', str(kpis['product_line_count'])],
                ['原因不明', f'{kpis["unknown_count"]}件 ({kpis["unknown_ratio"]}%)'],
                ['大客户投诉', f'{kpis["key_customer_count"]}件 ({kpis["key_customer_ratio"]}%)'],
            ]
            data_table = {'headers': ['指标', '值'], 'rows': rows}
            summary = f'KPI 汇总：总投诉 {kpis["total"]} 件，涉及 {kpis["product_line_count"]} 条产品线。'

        insights = self.processor.generate_insights(filters)

        return {
            'message': summary,
            'charts': charts,
            'insights': insights,
            'data_table': data_table,
        }

    # ===== 报告导出 Skill =====

    async def _handle_report_export(self, intent: dict) -> dict:
        """报告导出 skill 处理器：组装分析结果并导出。"""
        if not self.processor:
            return {
                'message': '暂无可用的数据源，请先上传 Excel 文件。',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        # 收集全部分析数据
        filters = intent.get('filters', {})
        kpis = self.processor.get_summary_kpis(filters)
        rc_dist = self.processor.get_root_cause_distribution(filters)
        pl_dist = self.processor.get_product_line_distribution(filters)
        defect_top = self.processor.get_defect_top15(filters)
        insights = self.processor.generate_insights(filters)

        charts = [
            {
                'id': 'chart_root_cause',
                'title': '原因大类分布',
                'type': 'pie',
                'option': render_pie(rc_dist['labels'], rc_dist['values']),
            },
            {
                'id': 'chart_pl_dist',
                'title': '产品线投诉分布',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(pl_dist['labels'], pl_dist['values']),
            },
            {
                'id': 'chart_defect_top15',
                'title': '不良类型 TOP15',
                'type': 'bar',
                'option': render_bar(defect_top['labels'], defect_top['values']),
            },
        ]

        summary = (
            f'报告数据已组装完成：总投诉 {kpis["total"]} 件，'
            f'{len(charts)} 张图表，{len(insights)} 条洞察。'
            f'请使用报表中心的导出功能下载 HTML 或 Excel 格式报告。'
        )

        return {
            'message': summary,
            'charts': charts,
            'insights': insights,
            'data_table': None,
        }

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
                defect_top = self.processor.get_defect_top15(filters=None, top_n=15)
                mfg = self.processor.get_mfg_defect_breakdown()
                rnd = self.processor.get_rnd_defect_breakdown()
                cli = self.processor.get_cli_defect_breakdown()
                wh = self.processor.get_wh_defect_breakdown()

                cause_details = []
                for label, value in zip(rc_dist['labels'], rc_dist['values']):
                    cause_details.append(f"{label}: {value}件")

                # 大客户数据
                key_customers = self.processor.get_key_customers()
                key_customer_list = ', '.join([f'{l}({v}件)' for l, v in zip(key_customers['labels'][:10], key_customers['values'][:10])])
                key_customer_names = '、'.join(self.processor.KEY_CUSTOMERS)

                # 各原因大类下的全部不良类型细分（用于交叉查询）
                def _fmt_breakdown(data):
                    return ', '.join([f'{l}({v}件)' for l, v in zip(data['labels'], data['values'])]) or '无'

                # TOP 5 不良类型的跨原因大类分布（解决“54件颜色波动怎么分布”的问题）
                defect_cross_lines = []
                try:
                    df = self.processor.df
                    cause_col = '原因大类'
                    defect_col = '二级不良'
                    top5_defects = defect_top['labels'][:5]
                    # rc_dist['labels'] 已包含所有原因大类（含原因不明）
                    all_causes = rc_dist['labels']
                    for defect_name in top5_defects:
                        total_cnt = 0
                        parts = []
                        for cause_label in all_causes:
                            cnt = len(df[(df[defect_col] == defect_name) & (df[cause_col] == cause_label)])
                            if cnt > 0:
                                parts.append(f'{cause_label}{cnt}件')
                                total_cnt += cnt
                        if parts:
                            defect_cross_lines.append(f'  {defect_name}(总{total_cnt}件): {", ".join(parts)}')
                except Exception:
                    defect_cross_lines = []
                defect_cross_str = '\n'.join(defect_cross_lines) if defect_cross_lines else '无交叉数据'

                data_context = f"""\n当前客诉数据摘要：
- 总投诉数: {kpis['total']}件
- 产品线数: {kpis['product_line_count']}条
- 原因大类分布: {', '.join(cause_details)}
- 产品线投诉排名: {', '.join([f'{l}({v}件)' for l, v in zip(pl_dist['labels'], pl_dist['values'])])}
- 不良类型TOP15: {', '.join([f'{l}({v}件)' for l, v in zip(defect_top['labels'], defect_top['values'])])}
- TOP5不良类型的原因大类分布：
{defect_cross_str}
- 制造原因下不良类型: {_fmt_breakdown(mfg)}
- 研发原因下不良类型: {_fmt_breakdown(rnd)}
- 客户原因下不良类型: {_fmt_breakdown(cli)}
- 仓储原因下不良类型: {_fmt_breakdown(wh)}
- 原因不明: {kpis['unknown_count']}件 ({kpis['unknown_ratio']}%)
- 大客户投诉: {kpis['key_customer_count']}件 ({kpis['key_customer_ratio']}%)
- 大客户投诉排名: {key_customer_list}
- 大客户名单(预定义): {key_customer_names}

分析方法：
1. 原因分类：根据“初步调查”列的文本，使用46条正则规则提取原因关键词（如“标签贴错”→仓储原因，“配色/混色不均”→制造原因），再映射到5大类：制造原因、研发原因、客户原因、仓储原因、原料原因。无法匹配的归为“原因不明”。
2. 大客户识别：系统预定义了{len(self.processor.KEY_CUSTOMERS)}家大客户名单（{key_customer_names}），通过在“初步调查”文本中匹配这些关键词来识别大客户投诉记录。如果Excel中包含“大客户体系”列则直接使用该列数据。
3. 不良类型统计：基于“二级不良”列进行分组计数。同一不良类型可能出现在不同原因大类下（如“颜色波动”可能同时存在于制造原因和客户原因中），各原因大类下的数量之和等于该不良类型的总投诉数。
回答规则：
- 当用户询问某个不良类型的分布时，优先引用“TOP5不良类型的原因大类分布”数据，完整列出所有原因大类及对应数量，不要只说“主要分布”而省略部分类别。
- 当用户提到某个具体数字时，请先在上述数据中查找匹配项（包括各原因大类细分和交叉分布），不要仅看总数就否定用户的说法。
- 如果找不到精确匹配，说明可能来自特定的筛选条件组合（如某产品线+某原因大类），请诚实告知无法确认具体来源并建议用户指明筛选条件。"""
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
        ]

        # 加入对话历史（保持上下文连贯性）
        chat_history = intent.get('chat_history', [])
        if chat_history:
            # 只取最近的对话轮次，避免token过长
            for msg in chat_history[-6:]:
                if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                    messages.append({"role": msg['role'], "content": msg['content']})

        # 当前用户消息
        messages.append({"role": "user", "content": user_message})

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
