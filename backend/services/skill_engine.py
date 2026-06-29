"""Skill 执行引擎：注册、分发、执行工单分析技能。"""

from __future__ import annotations
import json
import os
import re
from typing import Callable, Optional

from backend.services.ticket_processor import TicketProcessor, TicketProcessorManager
from backend.services.chart_renderer import (
    render_pie, render_bar, render_stacked_bar, render_horizontal_bar, render_rose, render_line,
)

SKILLS_DIRS = [
    os.path.join(os.path.dirname(__file__), '..', '..', 'skills', 'user'),
    os.path.join(os.path.dirname(__file__), '..', '..', 'skills', 'system'),
]


def _parse_skill_md(filepath: str) -> Optional[dict]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return None

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

    def __init__(self, processor=None, llm_provider=None, processor_manager: TicketProcessorManager = None):
        self.processor = processor  # 向后兼容：单处理器模式
        self.processor_manager = processor_manager  # 新模式：多数据源管理器
        self.llm = llm_provider
        self._skills: dict[str, dict] = {}
        self._handlers: dict[str, Callable] = {
            'ticket_analysis': self._handle_ticket_analysis,
            'data_query': self._handle_data_query,
            'report_export': self._handle_report_export,
            'deep_analysis': self._handle_deep_analysis,
        }
        self._auto_discover_skills()
        self._register_chitchat()

    def _resolve_processor(self, intent: dict = None) -> Optional[TicketProcessor]:
        """解析当前应使用的 processor。

        优先级：intent['processor'] > processor_manager.get(primary) > self.processor
        """
        # 1. intent 中直接指定的 processor（从 chat router 传入）
        if intent and intent.get('processor'):
            return intent['processor']

        # 2. 从 processor_manager 获取 primary
        if self.processor_manager:
            mgr_proc = self.processor_manager.get_primary()
            if mgr_proc:
                return mgr_proc

        # 3. 向后兼容
        return self.processor

    def _auto_discover_skills(self):
        found_any = False
        for skills_dir in SKILLS_DIRS:
            if not os.path.isdir(skills_dir):
                continue
            for entry in sorted(os.listdir(skills_dir)):
                skill_dir = os.path.join(skills_dir, entry)
                skill_md = os.path.join(skill_dir, 'SKILL.md')
                if not os.path.isfile(skill_md):
                    continue

                meta = _parse_skill_md(skill_md)
                if not meta:
                    continue

                sid = meta['id']
                handler = self._handlers.get(sid)
                if not handler:
                    continue

                self.register_skill(sid, {
                    'name': meta.get('name', sid),
                    'description': meta.get('description', ''),
                    'enabled': meta.get('enabled', True),
                    'category': meta.get('category', ''),
                    'priority': meta.get('priority', 99),
                    'handler': handler,
                })
                found_any = True

        # fallback: 如果没有找到任何技能，注册内置的
        if not found_any:
            self._register_ticket_analysis()
            self._register_deep_analysis()

    def _register_ticket_analysis(self):
        self.register_skill('ticket_analysis', {
            'name': '工单数据分析',
            'description': '分析工单数据，生成统计图表',
            'enabled': True,
            'category': 'analysis',
            'priority': 1,
            'handler': self._handle_ticket_analysis,
        })

    def _register_deep_analysis(self):
        self.register_skill('deep_analysis', {
            'name': '深度分析大师',
            'description': '四阶段深度分析法：现状→根因→趋势→行动建议',
            'enabled': True,
            'category': 'analysis',
            'priority': 0,  # 比 ticket_analysis 优先级更高
            'handler': self._handle_deep_analysis,
        })

    def _register_chitchat(self):
        self.register_skill('chitchat', {
            'name': '智能问答',
            'description': '回答与工单相关的问题和闲聊',
            'enabled': True,
            'category': 'conversation',
            'priority': 999,
            'handler': self._handle_chitchat,
        })

    def register_skill(self, skill_id: str, metadata: dict):
        self._skills[skill_id] = metadata

    def get_available_skills(self) -> list[dict]:
        return [
            {'id': sid, 'name': s['name'], 'description': s.get('description', ''), 'enabled': s.get('enabled', True)}
            for sid, s in self._skills.items()
        ]

    async def execute_skill(self, skill_id: str, intent: dict) -> dict:
        skill = self._skills.get(skill_id) or self._skills.get('ticket_analysis')
        if not skill:
            raise ValueError(f"Skill 不存在: {skill_id}")

        handler = skill['handler']
        return await handler(intent)

    # ===== 工单分析 Handler =====

    async def _handle_ticket_analysis(self, intent: dict) -> dict:
        processor = self._resolve_processor(intent)
        if not processor:
            return {
                'message': '暂无可用的数据源，请先上传 Excel 文件或配置数据源路径。',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        filters = intent.get('filters', {})
        group_by = intent.get('group_by', 'status')
        chart_type = intent.get('chart_type', 'pie')

        charts = []
        insights = []
        data_table = None
        summary = ''

        kpis = processor.get_summary_kpis(filters)

        # ---- 状态分布（仅在未指定 group_by 或明确指定 status 时） ----
        if group_by == 'status' or (not group_by and chart_type == 'pie'):
            dist = processor.get_status_distribution(filters)
            charts.append({
                'id': 'chart_status',
                'title': '工单状态分布',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，状态分布如上。'
            if dist['labels']:
                rows = [[l, str(v), f'{round(v/kpis["total"]*100,1) if kpis["total"] else 0}%'] for l, v in zip(dist['labels'], dist['values'])]
                data_table = {'headers': ['状态', '数量', '占比'], 'rows': rows}

        # ---- 服务组工作量 ----
        elif group_by == 'service_group':
            dist = processor.get_service_group_distribution(filters)
            charts.append({
                'id': 'chart_sg',
                'title': '服务组工单量',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，覆盖 {len(dist["labels"])} 个服务组。'
            if dist['labels']:
                rows = [[l, str(v)] for l, v in zip(dist['labels'], dist['values'])]
                data_table = {'headers': ['服务组', '工单数'], 'rows': rows}

        # ---- 责任人处理量 ----
        elif group_by == 'assignee':
            dist = processor.get_assignee_distribution(filters)
            charts.append({
                'id': 'chart_assignee',
                'title': '责任人处理量 TOP15',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，责任人处理量如上。'
            if dist['labels']:
                rows = [[l, str(v)] for l, v in zip(dist['labels'], dist['values'])]
                data_table = {'headers': ['责任人', '工单数'], 'rows': rows}

        # ---- 部门分布 ----
        elif group_by == 'department':
            dist = processor.get_department_distribution(filters)
            charts.append({
                'id': 'chart_dept',
                'title': '请求部门分布',
                'type': 'bar',
                'option': render_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，涉及 {len(dist["labels"])} 个部门。'

        # ---- 请求人机构分布 ----
        elif group_by == 'org':
            dist = processor.get_org_distribution(filters)
            charts.append({
                'id': 'chart_org',
                'title': '请求人机构分布',
                'type': 'bar',
                'option': render_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，涉及 {len(dist["labels"])} 个机构。'
            if dist['labels']:
                rows = [[l, str(v)] for l, v in zip(dist['labels'], dist['values'])]
                data_table = {'headers': ['机构', '工单数'], 'rows': rows}

        # ---- 来源渠道分布 ----
        elif group_by == 'source_channel':
            dist = processor.get_source_channel_distribution(filters)
            charts.append({
                'id': 'chart_source',
                'title': '来源渠道分布',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，来源渠道分布如上。'

        # ---- 故障原因分组 ----
        elif group_by == 'fault_group':
            dist = processor.get_fault_group_distribution(filters)
            charts.append({
                'id': 'chart_fault',
                'title': '故障原因分组',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，故障原因分组如上。'

        # ---- 原因类别 ----
        elif group_by == 'cause_category':
            dist = processor.get_cause_category_distribution(filters)
            charts.append({
                'id': 'chart_cause',
                'title': '原因类别分布',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，原因类别分布如上。'

        # ---- 业务系统分布 ----
        elif group_by == 'business_system':
            dist = processor.get_business_system_distribution(filters)
            charts.append({
                'id': 'chart_sys',
                'title': '业务系统分布',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，覆盖 {len(dist["labels"])} 个业务系统。'

        # ---- 解决人 ----
        elif group_by == 'resolver':
            dist = processor.get_resolver_distribution(filters)
            charts.append({
                'id': 'chart_resolver',
                'title': '解决人处理量',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，解决人处理量如上。'

        # ---- 周趋势 ----
        elif group_by == 'weekly':
            trend = processor.get_weekly_trend(filters)
            charts.append({
                'id': 'chart_weekly',
                'title': '每周工单趋势',
                'type': 'line',
                'option': render_line(trend['labels'], [{'name': '工单数', 'data': trend['values']}]),
            })
            summary = f'每周工单趋势如上，共 {kpis["total"]} 件工单。'

        # ---- 月趋势 ----
        elif group_by == 'monthly':
            trend = processor.get_monthly_trend(filters)
            charts.append({
                'id': 'chart_monthly',
                'title': '每月工单趋势',
                'type': 'line',
                'option': render_line(trend['labels'], [{'name': '工单数', 'data': trend['values']}]),
            })
            summary = f'每月工单趋势如上，共 {kpis["total"]} 件工单。'

        # ---- SLA 趋势 ----
        elif group_by == 'sla':
            trend = processor.get_sla_weekly_trend(filters)
            charts.append({
                'id': 'chart_sla_trend',
                'title': 'SLA 达标率周趋势',
                'type': 'line',
                'option': render_line(trend['labels'], [{'name': 'SLA(%)', 'data': trend['values']}]),
            })
            summary = f'SLA 平均达标率 {kpis["sla_avg"]}%，趋势如上。'

        # ---- 解决时效 ----
        elif group_by == 'resolution_time':
            buckets = processor.get_resolution_time_buckets(filters)
            charts.append({
                'id': 'chart_res_time',
                'title': '解决时效分布',
                'type': 'bar',
                'option': render_bar(buckets['labels'], buckets['values']),
            })
            summary = f'平均解决时间 {kpis["avg_resolution_days"]} 天。'

        # ---- 挂起分析 ----
        elif group_by == 'suspended':
            sus = processor.get_suspended_breakdown(filters)
            charts.append({
                'id': 'chart_suspended',
                'title': '挂起原因分析',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(sus['labels'], sus['values']),
            })
            summary = f'共 {kpis["suspended_count"]} 件挂起工单（{kpis["suspended_ratio"]}%）。'

        # ---- 交叉分析：服务组×状态 ----
        elif chart_type == 'stacked_bar':
            ct = processor.get_status_by_service_group(filters)
            charts.append({
                'id': 'chart_cross',
                'title': '服务组×状态交叉分析',
                'type': 'stacked_bar',
                'option': render_stacked_bar(ct['groups'], ct['statuses']),
            })
            summary = f'各服务组工单状态结构如上。'

        # ---- 新增：故障根因深度分析 ----
        elif group_by == 'root_cause':
            rc = processor.get_fault_root_cause_analysis(filters)
            if rc.get('fault_top_n'):
                top = rc['fault_top_n'][:15]
                labels = [t['cause'] for t in top]
                values = [t['count'] for t in top]
                charts.append({
                    'id': 'chart_root_cause',
                    'title': '故障根因 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(labels, values),
                })
                summary = f'故障根因分析完成，共 {len(rc.get("fault_top_n", []))} 类故障原因。'
                rows = [[t['cause'], str(t['count'])] for t in top]
                data_table = {'headers': ['故障原因', '次数'], 'rows': rows}
            if rc.get('symptom_clusters'):
                clusters = rc['symptom_clusters'][:10]
                insights = [{
                    'severity': 'info',
                    'title': f'症状聚类「{c["symptom"]}」({c["count"]}次)→方案: {", ".join([s[0] for s in c.get("top_solutions", [])[:2]])}',
                    'desc': f'关联根因: {", ".join([r[0] for r in c.get("top_causes", [])[:2]])}',
                } for c in clusters]

        # ---- 新增：重复工单挖掘 ----
        elif group_by == 'recurring':
            dup = processor.get_recurring_tickets(filters)
            if dup['by_fault_group']:
                top = dup['by_fault_group'][:15]
                labels = [d['cause'] for d in top]
                values = [d['count'] for d in top]
                charts.append({
                    'id': 'chart_recurring',
                    'title': '重复故障 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(labels, values),
                })
                summary = f'重复工单挖掘完成。Top5 重复故障占比 {dup["summary"]["dup_ratio"]}%。'
                rows = [[d['cause'], str(d['count']), f'{d["pct"]}%'] for d in top]
                data_table = {'headers': ['故障原因', '重复次数', '占比'], 'rows': rows}

        # ---- 新增：运维质量指标 ----
        elif group_by == 'ops_quality':
            ops = processor.get_ops_quality_metrics(filters)
            charts.append({
                'id': 'chart_ops',
                'title': '运维质量指标',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(
                    ['退回率', '挂起率', '撤单率', 'SLA达标率'],
                    [ops['returned_ratio'], ops['suspended_ratio'], ops['cancelled_ratio'], ops['sla_ratio']],
                ),
            })
            summary = f'退回率 {ops["returned_ratio"]}% / 挂起率 {ops["suspended_ratio"]}% / 撤单率 {ops["cancelled_ratio"]}% / SLA达标率 {ops["sla_ratio"]}%。'
            data_table = {'headers': ['指标', '值', '数量'], 'rows': [
                ['退回服务台率', f'{ops["returned_ratio"]}%', f'{ops["returned_count"]}件'],
                ['挂起率', f'{ops["suspended_ratio"]}%', f'{ops["suspended_count"]}件'],
                ['撤单率', f'{ops["cancelled_ratio"]}%', f'{ops["cancelled_count"]}件'],
                ['SLA达标率', f'{ops["sla_ratio"]}%', ''],
                ['平均解决', f'{ops["avg_resolution_days"]}天', ''],
            ]}

        # ---- 新增：症状→方案聚类 ----
        elif group_by == 'symptom_solution':
            mapping = processor.get_symptom_solution_mapping(filters)
            clusters = mapping.get('clusters', [])[:15]
            if clusters:
                labels = [c['symptom'] for c in clusters]
                values = [c['count'] for c in clusters]
                charts.append({
                    'id': 'chart_symptom',
                    'title': '症状→方案聚类 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(labels, values),
                })
                summary = f'症状-方案聚类完成，共 {mapping["total_symptoms"]} 类症状。'
                rows = []
                for c in clusters:
                    sol_str = ', '.join([s[0] for s in c.get('top_solutions', [])[:3]])
                    rows.append([c['symptom'], str(c['count']), f'{c["avg_resolution_days"]}天', sol_str])
                data_table = {'headers': ['症状', '次数', '平均解决', '推荐方案'], 'rows': rows}

        # ---- 新增：请求人行为与组织分析 ----
        elif group_by == 'requester':
            behavior = processor.get_requester_behavior(filters)
            if behavior.get('top_requesters') and behavior['top_requesters']['values']:
                charts.append({
                    'id': 'chart_requester',
                    'title': '高频请求人 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(behavior['top_requesters']['labels'][:15], behavior['top_requesters']['values'][:15]),
                })
                summary = f'共 {behavior["summary"]["total_requesters"]} 个请求人，覆盖 {behavior["summary"]["total_departments"]} 个部门。'
                rows = [[l, str(v)] for l, v in zip(behavior['top_requesters']['labels'][:15], behavior['top_requesters']['values'][:15])]
                data_table = {'headers': ['请求人', '工单数'], 'rows': rows}
            if behavior.get('department_distribution'):
                charts.append({
                    'id': 'chart_req_dept',
                    'title': '请求部门分布',
                    'type': 'bar',
                    'option': render_bar(behavior['department_distribution']['labels'], behavior['department_distribution']['values']),
                })

        # ---- 新增：性质占比与趋势 ----
        elif group_by == 'nature_trend':
            nt = processor.get_nature_trend(filters)
            dist = nt['distribution']
            if dist['labels']:
                charts.append({
                    'id': 'chart_nature_pie',
                    'title': '各类性质占比',
                    'type': 'pie',
                    'option': render_pie(dist['labels'], dist['values']),
                })
                summary = f'各类性质占比分析完成。'
                total = sum(dist['values'])
                rows = [[l, str(v), f'{round(v/total*100,1)}%'] for l, v in zip(dist['labels'], dist['values'])]
                data_table = {'headers': ['性质', '数量', '占比'], 'rows': rows}
            if nt['trend']['series']:
                charts.append({
                    'id': 'chart_nature_trend',
                    'title': '各类性质周趋势',
                    'type': 'line',
                    'option': render_line(nt['trend']['labels'], nt['trend']['series']),
                })

        # ---- 动态维度：预设关键词未匹配时，自动在 DataFrame 列中查找最接近的维度 ----
        elif group_by == '_dynamic':
            unmatched = intent.get('unmatched_query', '')
            dim_col = processor.find_dynamic_dimension(unmatched) if unmatched else None
            if dim_col and dim_col in processor.df.columns:
                counts = processor._apply_filters(filters)[dim_col].value_counts()
                if len(counts) > 0:
                    cn_name = dim_col
                    for cn, en in processor.COL_MAP.items():
                        if en == dim_col:
                            cn_name = cn
                            break
                    charts.append({
                        'id': f'chart_dynamic_{dim_col}',
                        'title': f'{cn_name}分布',
                        'type': 'horizontal_bar',
                        'option': render_horizontal_bar(list(counts.index.astype(str)), [int(v) for v in counts.values]),
                    })
                    summary = f'按「{cn_name}」维度分析，共 {len(counts)} 个分类。（该维度为自动匹配，可在"维度管理"中确认永久添加）'
                    rows = [[str(k), str(v)] for k, v in counts.items()]
                    data_table = {'headers': [cn_name, '工单数'], 'rows': rows}
                    # 标记待确认维度，供 chat router 记录到 DB
                    sample_values = [str(v) for v in counts.index[:5].tolist()]
                    intent['_pending_dimension'] = {
                        'query_text': unmatched,
                        'matched_column': dim_col,
                        'matched_label': cn_name,
                        'sample_values': sample_values,
                        'group_by_suggestion': dim_col,
                    }
                else:
                    summary = f'「{unmatched}」未找到对应数据。'
            else:
                available = [f'{cn}({en})' for cn, en in processor.ANALYSIS_DIMENSIONS.items()
                             if en not in ('ticket_id', 'title', 'description', 'created_at', 'resolved_at')]
                summary = f'未识别到分析维度「{unmatched}」。可用维度：{"、".join(available[:12])}'

        # ---- 默认：KPI 汇总 ----
        else:
            data_table = {'headers': ['指标', '值'], 'rows': [
                ['总工单数', str(kpis['total'])],
                ['已解决', f'{kpis["resolved_count"]}件 ({kpis["resolved_ratio"]}%)'],
                ['SLA 达标率', f'{kpis["sla_ratio"]}%'],
                ['SLA 平均', f'{kpis["sla_avg"]}%'],
                ['挂起工单', f'{kpis["suspended_count"]}件 ({kpis["suspended_ratio"]}%)'],
                ['平均解决天数', f'{kpis["avg_resolution_days"]}天'],
                ['退回服务台', f'{kpis["returned_count"]}件'],
                ['已评价', f'{kpis["evaluated_count"]}件 ({kpis["evaluated_ratio"]}%)'],
            ]}
            summary = f'工单 KPI 汇总：总 {kpis["total"]} 件，SLA 达标率 {kpis["sla_ratio"]}%。'

        insights = processor.generate_insights(filters)

        return {
            'message': summary,
            'charts': charts,
            'insights': insights,
            'data_table': data_table,
        }

    # ===== 数据查询 Handler =====

    async def _handle_data_query(self, intent: dict) -> dict:
        processor = self._resolve_processor(intent)
        if not processor:
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

        # 按 query_type 分发到不同的 TicketProcessor 方法
        query_handlers = {
            'status_distribution': lambda f: (processor.get_status_distribution(f), 'pie', '状态分布'),
            'service_group_distribution': lambda f: (processor.get_service_group_distribution(f), 'horizontal_bar', '服务组工作量'),
            'assignee_distribution': lambda f: (processor.get_assignee_distribution(f, top_n=15), 'horizontal_bar', '责任人处理量'),
            'department_distribution': lambda f: (processor.get_department_distribution(f), 'bar', '部门分布'),
            'org_distribution': lambda f: (processor.get_org_distribution(f), 'bar', '请求人机构分布'),
            'source_channel_distribution': lambda f: (processor.get_source_channel_distribution(f), 'pie', '来源渠道分布'),
            'fault_group_distribution': lambda f: (processor.get_fault_group_distribution(f), 'pie', '故障原因分组'),
            'cause_category_distribution': lambda f: (processor.get_cause_category_distribution(f), 'pie', '原因类别'),
            'weekly_trend': lambda f: (processor.get_weekly_trend(f), 'line', '每周趋势'),
            'monthly_trend': lambda f: (processor.get_monthly_trend(f), 'line', '每月趋势'),
            'sla_weekly_trend': lambda f: (processor.get_sla_weekly_trend(f), 'line', 'SLA趋势'),
            'suspended_breakdown': lambda f: (processor.get_suspended_breakdown(f), 'horizontal_bar', '挂起原因'),
            'evaluation_summary': lambda f: (processor.get_evaluation_summary(f), None, '满意度'),
            'resolution_time_buckets': lambda f: (processor.get_resolution_time_buckets(f), 'bar', '解决时效'),
            'fault_root_cause_analysis': lambda f: (processor.get_fault_root_cause_analysis(f), None, '故障根因分析'),
            'fault_cause_trend': lambda f: (processor.get_fault_cause_trend(f), 'line', '故障原因趋势'),
            'symptom_solution_mapping': lambda f: (processor.get_symptom_solution_mapping(f), None, '症状方案聚类'),
            'recurring_tickets': lambda f: (processor.get_recurring_tickets(f), None, '重复工单'),
            'nature_trend': lambda f: (processor.get_nature_trend(f), None, '性质趋势'),
            'requester_behavior': lambda f: (processor.get_requester_behavior(f), None, '请求人行为'),
            'ops_quality_metrics': lambda f: (processor.get_ops_quality_metrics(f), None, '运维质量'),
        }

        handler = query_handlers.get(query_type)
        if handler:
            data, ctype, title = handler(filters)
            if ctype and data.get('labels'):
                if ctype == 'pie':
                    opt = render_pie(data['labels'], data['values'])
                elif ctype == 'horizontal_bar':
                    opt = render_horizontal_bar(data['labels'], data['values'])
                elif ctype == 'bar':
                    opt = render_bar(data['labels'], data['values'])
                elif ctype == 'line':
                    opt = render_line(data['labels'], [{'name': title, 'data': data['values']}])
                else:
                    opt = render_pie(data['labels'], data['values'])

                charts.append({
                    'id': f'chart_{query_type}',
                    'title': title,
                    'type': ctype,
                    'option': opt,
                })

            if data.get('labels') and data.get('values'):
                # 趋势类：简单显示数据
                if query_type in ('weekly_trend', 'monthly_trend', 'sla_weekly_trend'):
                    rows = [[l, str(v)] for l, v in zip(data['labels'], data['values'])][-10:]
                    data_table = {'headers': ['时间', '值'], 'rows': rows}
                elif query_type == 'evaluation_summary':
                    rows = [
                        ['服务态度', str(data.get('attitude_avg', 0))],
                        ['技术水平', str(data.get('tech_avg', 0))],
                        ['响应时效', str(data.get('response_avg', 0))],
                        ['评价数', str(data.get('eval_count', 0))],
                    ]
                    data_table = {'headers': ['指标', '评分'], 'rows': rows}
                elif query_type == 'resolution_time_buckets':
                    total = sum(data['values'])
                    rows = [[l, str(v), f'{round(v/total*100,1) if total else 0}%'] for l, v in zip(data['labels'], data['values'])]
                    data_table = {'headers': ['耗时', '数量', '占比'], 'rows': rows}
                else:
                    total = sum(data['values']) if data['values'] else 1
                    rows = [[l, str(v), f'{round(v/total*100,1) if total else 0}%'] for l, v in zip(data['labels'], data['values'])]
                    data_table = {'headers': ['类别', '数量', '占比'], 'rows': rows}

            summary = f'{title}查询完成。'
        else:
            kpis = processor.get_summary_kpis(filters)
            rows = [
                ['总工单数', str(kpis['total'])],
                ['已解决', f'{kpis["resolved_count"]}件 ({kpis["resolved_ratio"]}%)'],
                ['SLA 达标率', f'{kpis["sla_ratio"]}%'],
                ['平均解决天数', f'{kpis["avg_resolution_days"]}天'],
            ]
            data_table = {'headers': ['指标', '值'], 'rows': rows}
            summary = f'KPI 汇总：总工单 {kpis["total"]} 件，SLA 达标率 {kpis["sla_ratio"]}%。'

        insights = processor.generate_insights(filters)

        return {
            'message': summary,
            'charts': charts,
            'insights': insights,
            'data_table': data_table,
        }

    # ===== 报告导出 Handler（五章节结构报告） =====

    async def _handle_report_export(self, intent: dict) -> dict:
        """生成五章节结构化分析报告：摘要概览→产品线分析→原因分析→大客户分析→洞察建议。"""
        processor = self._resolve_processor(intent)
        filters = intent.get('filters', {})
        export_format = intent.get('format', 'html')

        if not processor:
            return {
                'message': '暂无可用的数据源，请先上传 Excel 文件。',
                'charts': [],
                'insights': [],
                'data_table': None,
                'report_sections': [],
            }

        try:
            kpis = processor.get_summary_kpis(filters)
            weekly_trend = processor.get_weekly_trend(filters)
            monthly_trend = processor.get_monthly_trend(filters)
            status_dist = processor.get_status_distribution(filters)
            sg_dist = processor.get_service_group_distribution(filters)
            fault_dist = processor.get_fault_group_distribution(filters)
            cause_dist = processor.get_cause_category_distribution(filters)
            biz_dist = processor.get_business_system_distribution(filters)
            root_cause = processor.get_fault_root_cause_analysis(filters)
            symptom = processor.get_symptom_solution_mapping(filters)
            recurring = processor.get_recurring_tickets(filters)
            requester = processor.get_requester_behavior(filters)
            dept_dist = processor.get_department_distribution(filters)
            ops = processor.get_ops_quality_metrics(filters)
            eval_data = processor.get_evaluation_summary(filters)
            insights = processor.generate_insights(filters)
        except Exception as e:
            return {
                'message': f'数据获取失败: {e}',
                'charts': [],
                'insights': [],
                'data_table': None,
                'report_sections': [],
            }

        # ── 按章节构建图表 ────────────────────────────
        charts = []

        # 章节1: 摘要概览
        if status_dist.get('labels'):
            charts.append({'id': 'ch1_status', 'title': '工单状态分布', 'type': 'pie', 'section': 1,
                           'option': render_pie(status_dist['labels'], status_dist['values'])})
        if weekly_trend.get('labels'):
            charts.append({'id': 'ch1_weekly', 'title': '每周工单趋势', 'type': 'line', 'section': 1,
                           'option': render_line(weekly_trend['labels'], [{'name': '工单数', 'data': weekly_trend['values']}])})
        if monthly_trend.get('labels'):
            charts.append({'id': 'ch1_monthly', 'title': '每月工单趋势', 'type': 'line', 'section': 1,
                           'option': render_line(monthly_trend['labels'], [{'name': '工单数', 'data': monthly_trend['values']}])})

        # 章节2: 产品线分析
        if sg_dist.get('labels'):
            charts.append({'id': 'ch2_sg', 'title': '服务组工单量排名', 'type': 'horizontal_bar', 'section': 2,
                           'option': render_horizontal_bar(sg_dist['labels'], sg_dist['values'])})
        if fault_dist.get('labels'):
            charts.append({'id': 'ch2_fault', 'title': '故障原因分组', 'type': 'pie', 'section': 2,
                           'option': render_pie(fault_dist['labels'], fault_dist['values'])})
        if cause_dist.get('labels'):
            charts.append({'id': 'ch2_cause', 'title': '原因类别分布', 'type': 'bar', 'section': 2,
                           'option': render_bar(cause_dist['labels'], cause_dist['values'])})
        if biz_dist.get('labels'):
            charts.append({'id': 'ch2_biz', 'title': '业务系统分布', 'type': 'horizontal_bar', 'section': 2,
                           'option': render_horizontal_bar(biz_dist['labels'], biz_dist['values'])})

        # 章节3: 原因分析
        if root_cause.get('fault_top_n'):
            top = root_cause['fault_top_n'][:15]
            charts.append({'id': 'ch3_root', 'title': '故障根因 TOP15', 'type': 'horizontal_bar', 'section': 3,
                           'option': render_horizontal_bar([t['cause'] for t in top], [t['count'] for t in top])})
        if recurring.get('by_fault_group'):
            top = recurring['by_fault_group'][:15]
            charts.append({'id': 'ch3_recurring', 'title': '重复故障 TOP15', 'type': 'horizontal_bar', 'section': 3,
                           'option': render_horizontal_bar([d['cause'] for d in top], [d['count'] for d in top])})
        if symptom.get('clusters'):
            clusters = symptom['clusters'][:15]
            charts.append({'id': 'ch3_symptom', 'title': '症状方案聚类 TOP15', 'type': 'horizontal_bar', 'section': 3,
                           'option': render_horizontal_bar([c['symptom'] for c in clusters], [c['count'] for c in clusters])})

        # 章节4: 大客户分析
        if requester.get('top_requesters') and requester['top_requesters']['values']:
            charts.append({'id': 'ch4_requester', 'title': '高频请求人 TOP15', 'type': 'horizontal_bar', 'section': 4,
                           'option': render_horizontal_bar(requester['top_requesters']['labels'][:15], requester['top_requesters']['values'][:15])})
        if dept_dist.get('labels'):
            charts.append({'id': 'ch4_dept', 'title': '请求部门分布', 'type': 'bar', 'section': 4,
                           'option': render_bar(dept_dist['labels'], dept_dist['values'])})
        if requester.get('org_distribution') and requester['org_distribution']['labels']:
            charts.append({'id': 'ch4_org', 'title': '请求机构分布', 'type': 'horizontal_bar', 'section': 4,
                           'option': render_horizontal_bar(requester['org_distribution']['labels'], requester['org_distribution']['values'])})

        # ── 数据表 ───────────────────────────────────
        kpi_table = {'headers': ['指标', '值'], 'rows': [
            ['总工单数', str(kpis['total'])],
            ['已解决', f"{kpis['resolved_count']}件 ({kpis['resolved_ratio']}%)"],
            ['SLA 达标率', f"{kpis['sla_ratio']}%"],
            ['SLA 平均', f"{kpis['sla_avg']}%"],
            ['挂起工单', f"{kpis['suspended_count']}件 ({kpis['suspended_ratio']}%)"],
            ['平均解决天数', f"{kpis['avg_resolution_days']}天"],
            ['退回服务台', f"{kpis['returned_count']}件"],
            ['撤单', f"{kpis['cancelled_count']}件"],
            ['已评价', f"{kpis['evaluated_count']}件 ({kpis['evaluated_ratio']}%)"],
        ]}

        ops_table = {'headers': ['指标', '值', '数量'], 'rows': [
            ['退回率', f"{ops['returned_ratio']}%", f"{ops['returned_count']}件"],
            ['挂起率', f"{ops['suspended_ratio']}%", f"{ops['suspended_count']}件"],
            ['撤单率', f"{ops['cancelled_ratio']}%", f"{ops['cancelled_count']}件"],
            ['SLA达标率', f"{ops['sla_ratio']}%", ''],
            ['平均解决', f"{ops['avg_resolution_days']}天", ''],
        ]}

        root_cause_rows = []
        if root_cause.get('fault_top_n'):
            for t in root_cause['fault_top_n'][:20]:
                root_cause_rows.append([t['cause'], str(t['count']), f"{t.get('pct', 0)}%"])
        root_cause_table = {'headers': ['故障原因', '次数', '占比'], 'rows': root_cause_rows} if root_cause_rows else None

        requester_rows = []
        if requester.get('top_requesters') and requester['top_requesters']['values']:
            for name, cnt in zip(requester['top_requesters']['labels'][:20], requester['top_requesters']['values'][:20]):
                requester_rows.append([name, str(cnt)])
        requester_table = {'headers': ['请求人', '工单数'], 'rows': requester_rows} if requester_rows else None

        # ── 章节结构 ─────────────────────────────────
        report_sections = [
            {'id': 1, 'title': '摘要概览', 'description': 'KPI 指标、工单趋势、关键发现',
             'charts': [c for c in charts if c.get('section') == 1], 'tables': [kpi_table]},
            {'id': 2, 'title': '产品线分析', 'description': '各服务组工单量、故障原因分布、TOP 原因类别',
             'charts': [c for c in charts if c.get('section') == 2], 'tables': []},
            {'id': 3, 'title': '原因分析', 'description': '故障根因细分、重复故障、症状方案聚类',
             'charts': [c for c in charts if c.get('section') == 3],
             'tables': [root_cause_table] if root_cause_table else []},
            {'id': 4, 'title': '大客户分析', 'description': '高频请求人 TOP 客户、部门/机构分布',
             'charts': [c for c in charts if c.get('section') == 4],
             'tables': [requester_table] if requester_table else []},
            {'id': 5, 'title': '洞察建议', 'description': '数据驱动的改进建议',
             'charts': [], 'tables': [ops_table], 'insights': insights},
        ]

        for c in charts:
            c.pop('section', None)

        # ── 导出文件 ─────────────────────────────────
        from backend.services.export_service import export_html, export_excel
        from pathlib import Path
        title = intent.get('title', 'ITSM 工单分析报告')

        if export_format == 'excel':
            file_bytes = export_excel(title, kpi_table, kpis, insights, charts)
            file_ext = 'xlsx'
        else:
            file_bytes = export_html(title, charts, insights, kpi_table, kpis['total'])
            file_ext = 'html'

        export_dir = Path(__file__).parent.parent / 'data' / 'exports'
        export_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = re.sub(r'[^\w\-]', '_', title)[:50]
        file_path = export_dir / f'{ts}_{safe_title}.{file_ext}'
        file_path.write_bytes(file_bytes)

        return {
            'message': f'{title}已生成。共 {kpis["total"]} 件工单，{len(charts)} 个图表，{len(insights)} 条洞察，5 章节。',
            'charts': charts,
            'insights': insights,
            'data_table': kpi_table,
            'report_sections': report_sections,
            'export': {
                'format': file_ext,
                'file_path': str(file_path),
                'file_size': len(file_bytes),
                'title': title,
            },
        }

    # ===== 深度分析 Handler（数据分析大师） =====

    async def _handle_deep_analysis(self, intent: dict) -> dict:
        """四阶段深度分析法：现状→根因→趋势→行动建议。"""
        processor = self._resolve_processor(intent)
        user_message = intent.get('message', '')
        filters = intent.get('filters', {})

        if not processor:
            return {
                'message': '暂无可用数据源，请先上传 Excel 文件。',
                'charts': [],
                'insights': [],
                'data_table': None,
                'deep_insights': [],
            }

        # 1. 收集多维度数据
        try:
            kpis = processor.get_summary_kpis(filters)
            status_dist = processor.get_status_distribution(filters)
            sg_dist = processor.get_service_group_distribution(filters)
            weekly_trend = processor.get_weekly_trend(filters)
            monthly_trend = processor.get_monthly_trend(filters)
            ops = processor.get_ops_quality_metrics(filters)
            recurring = processor.get_recurring_tickets(filters)
            root_cause = processor.get_fault_root_cause_analysis(filters)
            behavior = processor.get_requester_behavior(filters)
            eval_data = processor.get_evaluation_summary(filters)
        except Exception as e:
            return {
                'message': f'数据获取失败: {e}',
                'charts': [],
                'insights': [],
                'data_table': None,
                'deep_insights': [],
            }

        # 2. 构建数据上下文
        status_str = ', '.join([f"{l}:{v}件" for l, v in zip(status_dist['labels'][:5], status_dist['values'][:5])])
        sg_str = ', '.join([f"{l}:{v}件" for l, v in zip(sg_dist['labels'][:5], sg_dist['values'][:5])])

        weekly_vals = weekly_trend.get('values', [])
        weekly_labels = weekly_trend.get('labels', [])
        weekly_str = ', '.join([f"{l}:{v}" for l, v in zip(weekly_labels[-4:], weekly_vals[-4:])]) if weekly_vals else '无'

        recurring_str = ''
        if recurring.get('by_fault_group'):
            top3 = recurring['by_fault_group'][:3]
            recurring_str = ', '.join([f'"{d["cause"]}"({d["count"]}次)' for d in top3])

        root_cause_str = ''
        if root_cause.get('fault_top_n'):
            top3 = root_cause['fault_top_n'][:3]
            root_cause_str = ', '.join([f'"{f["cause"]}"({f["count"]}次)' for f in top3])

        top_requester_str = ''
        if behavior.get('top_requesters') and behavior['top_requesters']['values']:
            req_top = list(zip(behavior['top_requesters']['labels'][:3], behavior['top_requesters']['values'][:3]))
            top_requester_str = ', '.join([f'"{r[0]}"({r[1]}件)' for r in req_top])

        dept_count = behavior.get('summary', {}).get('total_departments', 0)
        requester_count = behavior.get('summary', {}).get('total_requesters', 0)

        data_context = f"""【当前ITSM工单数据全景】
总工单: {kpis['total']}件 | 已解决: {kpis['resolved_count']}件({kpis['resolved_ratio']}%)
SLA达标率: {kpis['sla_ratio']}%(均{kpis['sla_avg']}%) | 平均解决: {kpis['avg_resolution_days']}天
挂起: {kpis['suspended_count']}件 | 退回: {kpis['returned_count']}件 | 撤单: {kpis['cancelled_count']}件
状态分布: {status_str}
服务组TOP5: {sg_str}
近4周趋势: {weekly_str}
重复工单TOP3: {recurring_str or '无'}
根因TOP3: {root_cause_str or '无'}
高频请求人TOP3: {top_requester_str or '无'}
组织广度: {dept_count}个部门 / {requester_count}个请求人
运维质量: 退回率{ops['returned_ratio']}% / 挂起率{ops['suspended_ratio']}% / 撤单率{ops['cancelled_ratio']}%
满意度: 服务态度{round(float(eval_data.get('attitude_avg', 0)), 1)}分 / 技术{round(float(eval_data.get('tech_avg', 0)), 1)}分 / 时效{round(float(eval_data.get('response_avg', 0)), 1)}分({eval_data.get('eval_count', 0)}条)"""

        # 3. 调用 LLM 进行深度分析
        if not self.llm:
            return {
                'message': 'LLM 不可用，无法进行深度分析。',
                'charts': [],
                'insights': [],
                'data_table': None,
                'deep_insights': [],
            }

        system_prompt = f"""# Role: ITIL 顶级数据分析大师 & 运维总监

## Profile
你是一位拥有 15 年 ITIL 咨询经验的顶级数据分析大师。你精通统计学和趋势预测，能从工单数据中洞察企业 IT 架构的沉、人员效能瓶颈及潜在系统性风险。

## Analysis Methodology (四阶段分析法)
按以下结构输出深度洞察：

1.  【现状扫描】：简明扼要总结当前数据核心特征。
2. 🔍 【根因推导】：结合多维度交叉数据，推导根本原因。穿透到"人员技能、变更发布、设备老化、流程缺陷"层面。
3. 📈 【趋势与主观预测】：
   - 给出你作为专家的**主观判断**和推高/推低预测。
   - 识别潜在风险（如：SLA将崩溃、某类故障有爆发趋势）。
4.  【行动建议】：提供至少3条具体的、可落地的管理或技术建议（避免空话，要具体到"建议对XX团队进行某模块培训"）。

## Tone & Style
- 语气：专业、严谨、敏锐、一针见血。
- 视角：管理层视角与技术专家视角结合。
- 善用 Markdown 标题、加粗、列表。
- 用 [🔥 暴增预警]、[🕵️ 隐性根因]、[🎯 黄金建议] 等标签对洞察分类。

{data_context}

请基于以上数据，对用户的问题进行四阶段深度分析。

## 用户当前请求的分析维度
用户要求分析的重点是：「{user_message}」
请围绕这个维度进行深入分析，不要偏离主题。如果用户问的是某个具体维度（如故障根因、SLA趋势等），重点分析该维度的数据特征、根因和建议。"""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        chat_history = intent.get('chat_history', [])
        for m in chat_history[-6:]:
            messages.append({"role": m['role'], "content": m['content']})

        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.llm.chat_completion(messages, temperature=0.5, max_tokens=2048)
        except Exception:
            response = "抱歉，深度分析暂时不可用，请稍后再试。"

        # 4. 根据用户请求的分析维度动态生成图表
        group_by = intent.get('group_by', '')
        chart_type = intent.get('chart_type', '')
        charts = []
        data_table = None

        from backend.services.chart_renderer import (
            render_pie, render_bar, render_horizontal_bar, render_line,
            render_stacked_bar, render_rose,
        )

        if group_by == 'root_cause':
            # 故障根因分析 → 主图: 根因TOP15 + 可选: 重复故障 + 症状聚类
            if root_cause.get('fault_top_n'):
                top = root_cause['fault_top_n'][:15]
                charts.append({
                    'id': 'chart_root_cause',
                    'title': '故障根因 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar([t['cause'] for t in top], [t['count'] for t in top]),
                })
                rows = [[t['cause'], str(t['count'])] for t in top]
                data_table = {'headers': ['故障原因', '次数'], 'rows': rows}
            if recurring.get('by_fault_group'):
                top = recurring['by_fault_group'][:15]
                charts.append({
                    'id': 'chart_recurring',
                    'title': '重复故障 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar([d['cause'] for d in top], [d['count'] for d in top]),
                })
            symptom_data = processor.get_symptom_solution_mapping(filters)
            if symptom_data.get('clusters'):
                clusters = symptom_data['clusters'][:15]
                charts.append({
                    'id': 'chart_symptom',
                    'title': '症状→方案聚类 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar([c['symptom'] for c in clusters], [c['count'] for c in clusters]),
                })

        elif group_by == 'recurring':
            if recurring.get('by_fault_group'):
                top = recurring['by_fault_group'][:15]
                charts.append({
                    'id': 'chart_recurring',
                    'title': '重复故障 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar([d['cause'] for d in top], [d['count'] for d in top]),
                })
                rows = [[d['cause'], str(d['count']), f'{d["pct"]}%'] for d in top]
                data_table = {'headers': ['故障原因', '重复次数', '占比'], 'rows': rows}

        elif group_by == 'status':
            if status_dist.get('labels'):
                charts.append({
                    'id': 'chart_status',
                    'title': '工单状态分布',
                    'type': 'pie',
                    'option': render_pie(status_dist['labels'], status_dist['values']),
                })
                total = kpis['total'] or 1
                rows = [[l, str(v), f'{round(v/total*100,1)}%'] for l, v in zip(status_dist['labels'], status_dist['values'])]
                data_table = {'headers': ['状态', '数量', '占比'], 'rows': rows}

        elif group_by == 'service_group':
            if sg_dist.get('labels'):
                charts.append({
                    'id': 'chart_sg',
                    'title': '服务组工单量',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(sg_dist['labels'], sg_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(sg_dist['labels'], sg_dist['values'])]
                data_table = {'headers': ['服务组', '工单数'], 'rows': rows}

        elif group_by == 'weekly':
            if weekly_trend.get('labels'):
                charts.append({
                    'id': 'chart_weekly',
                    'title': '每周工单趋势',
                    'type': 'line',
                    'option': render_line(weekly_trend['labels'], [{'name': '工单数', 'data': weekly_trend['values']}]),
                })
                rows = [[l, str(v)] for l, v in zip(weekly_trend['labels'], weekly_trend['values'])]
                data_table = {'headers': ['周', '工单数'], 'rows': rows}

        elif group_by == 'monthly':
            if monthly_trend.get('labels'):
                charts.append({
                    'id': 'chart_monthly',
                    'title': '每月工单趋势',
                    'type': 'line',
                    'option': render_line(monthly_trend['labels'], [{'name': '工单数', 'data': monthly_trend['values']}]),
                })
                rows = [[l, str(v)] for l, v in zip(monthly_trend['labels'], monthly_trend['values'])]
                data_table = {'headers': ['月', '工单数'], 'rows': rows}

        elif group_by == 'sla':
            sla_trend = processor.get_sla_weekly_trend(filters)
            if sla_trend.get('labels'):
                charts.append({
                    'id': 'chart_sla_trend',
                    'title': 'SLA 达标率周趋势',
                    'type': 'line',
                    'option': render_line(sla_trend['labels'], [{'name': 'SLA(%)', 'data': sla_trend['values']}]),
                })
                rows = [[l, f'{v}%'] for l, v in zip(sla_trend['labels'], sla_trend['values'])]
                data_table = {'headers': ['周', 'SLA达标率'], 'rows': rows}

        elif group_by == 'resolution_time':
            buckets = processor.get_resolution_time_buckets(filters)
            if buckets.get('labels'):
                charts.append({
                    'id': 'chart_res_time',
                    'title': '解决时效分布',
                    'type': 'bar',
                    'option': render_bar(buckets['labels'], buckets['values']),
                })
                total = sum(buckets['values']) or 1
                rows = [[l, str(v), f'{round(v/total*100,1)}%'] for l, v in zip(buckets['labels'], buckets['values'])]
                data_table = {'headers': ['耗时', '数量', '占比'], 'rows': rows}

        elif group_by == 'suspended':
            sus = processor.get_suspended_breakdown(filters)
            if sus.get('labels'):
                charts.append({
                    'id': 'chart_suspended',
                    'title': '挂起原因分析',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(sus['labels'], sus['values']),
                })
                rows = [[l, str(v)] for l, v in zip(sus['labels'], sus['values'])]
                data_table = {'headers': ['挂起原因', '数量'], 'rows': rows}

        elif group_by == 'ops_quality':
            charts.append({
                'id': 'chart_ops',
                'title': '运维质量指标',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(
                    ['退回率', '挂起率', '撤单率', 'SLA达标率'],
                    [ops['returned_ratio'], ops['suspended_ratio'], ops['cancelled_ratio'], ops['sla_ratio']],
                ),
            })
            data_table = {'headers': ['指标', '值', '数量'], 'rows': [
                ['退回服务台率', f'{ops["returned_ratio"]}%', f'{ops["returned_count"]}件'],
                ['挂起率', f'{ops["suspended_ratio"]}%', f'{ops["suspended_count"]}件'],
                ['撤单率', f'{ops["cancelled_ratio"]}%', f'{ops["cancelled_count"]}件'],
                ['SLA达标率', f'{ops["sla_ratio"]}%', ''],
                ['平均解决', f'{ops["avg_resolution_days"]}天', ''],
            ]}

        elif group_by == 'symptom_solution':
            symptom_data = processor.get_symptom_solution_mapping(filters)
            if symptom_data.get('clusters'):
                clusters = symptom_data['clusters'][:15]
                charts.append({
                    'id': 'chart_symptom',
                    'title': '症状→方案聚类 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar([c['symptom'] for c in clusters], [c['count'] for c in clusters]),
                })
                rows = []
                for c in clusters:
                    sol_str = ', '.join([s[0] for s in c.get('top_solutions', [])[:3]])
                    rows.append([c['symptom'], str(c['count']), f'{c["avg_resolution_days"]}天', sol_str])
                data_table = {'headers': ['症状', '次数', '平均解决', '推荐方案'], 'rows': rows}

        elif group_by == 'requester':
            if behavior.get('top_requesters') and behavior['top_requesters']['values']:
                charts.append({
                    'id': 'chart_requester',
                    'title': '高频请求人 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(behavior['top_requesters']['labels'][:15], behavior['top_requesters']['values'][:15]),
                })
                rows = [[l, str(v)] for l, v in zip(behavior['top_requesters']['labels'][:15], behavior['top_requesters']['values'][:15])]
                data_table = {'headers': ['请求人', '工单数'], 'rows': rows}
            dept_dist = processor.get_department_distribution(filters)
            if dept_dist.get('labels'):
                charts.append({
                    'id': 'chart_req_dept',
                    'title': '请求部门分布',
                    'type': 'bar',
                    'option': render_bar(dept_dist['labels'], dept_dist['values']),
                })

        elif group_by == 'assignee':
            assignee_dist = processor.get_assignee_distribution(filters, top_n=15)
            if assignee_dist.get('labels'):
                charts.append({
                    'id': 'chart_assignee',
                    'title': '责任人处理量 TOP15',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(assignee_dist['labels'], assignee_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(assignee_dist['labels'], assignee_dist['values'])]
                data_table = {'headers': ['责任人', '工单数'], 'rows': rows}

        elif group_by == 'department':
            dept_dist = processor.get_department_distribution(filters)
            if dept_dist.get('labels'):
                charts.append({
                    'id': 'chart_dept',
                    'title': '请求部门分布',
                    'type': 'bar',
                    'option': render_bar(dept_dist['labels'], dept_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(dept_dist['labels'], dept_dist['values'])]
                data_table = {'headers': ['部门', '工单数'], 'rows': rows}

        elif group_by == 'org':
            org_dist = processor.get_org_distribution(filters)
            if org_dist.get('labels'):
                charts.append({
                    'id': 'chart_org',
                    'title': '请求人机构分布',
                    'type': 'bar',
                    'option': render_bar(org_dist['labels'], org_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(org_dist['labels'], org_dist['values'])]
                data_table = {'headers': ['机构', '工单数'], 'rows': rows}

        elif group_by == 'source_channel':
            source_dist = processor.get_source_channel_distribution(filters)
            if source_dist.get('labels'):
                charts.append({
                    'id': 'chart_source',
                    'title': '来源渠道分布',
                    'type': 'pie',
                    'option': render_pie(source_dist['labels'], source_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(source_dist['labels'], source_dist['values'])]
                data_table = {'headers': ['渠道', '工单数'], 'rows': rows}

        elif group_by == 'fault_group':
            fault_dist = processor.get_fault_group_distribution(filters)
            if fault_dist.get('labels'):
                charts.append({
                    'id': 'chart_fault',
                    'title': '故障原因分组',
                    'type': 'pie',
                    'option': render_pie(fault_dist['labels'], fault_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(fault_dist['labels'], fault_dist['values'])]
                data_table = {'headers': ['故障分组', '工单数'], 'rows': rows}

        elif group_by == 'cause_category':
            cause_dist = processor.get_cause_category_distribution(filters)
            if cause_dist.get('labels'):
                charts.append({
                    'id': 'chart_cause',
                    'title': '原因类别分布',
                    'type': 'pie',
                    'option': render_pie(cause_dist['labels'], cause_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(cause_dist['labels'], cause_dist['values'])]
                data_table = {'headers': ['原因类别', '工单数'], 'rows': rows}

        elif group_by == 'business_system':
            biz_dist = processor.get_business_system_distribution(filters)
            if biz_dist.get('labels'):
                charts.append({
                    'id': 'chart_sys',
                    'title': '业务系统分布',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(biz_dist['labels'], biz_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(biz_dist['labels'], biz_dist['values'])]
                data_table = {'headers': ['业务系统', '工单数'], 'rows': rows}

        elif group_by == 'resolver':
            resolver_dist = processor.get_resolver_distribution(filters)
            if resolver_dist.get('labels'):
                charts.append({
                    'id': 'chart_resolver',
                    'title': '解决人处理量',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(resolver_dist['labels'], resolver_dist['values']),
                })
                rows = [[l, str(v)] for l, v in zip(resolver_dist['labels'], resolver_dist['values'])]
                data_table = {'headers': ['解决人', '工单数'], 'rows': rows}

        elif group_by == 'nature_trend':
            nt = processor.get_nature_trend(filters)
            dist = nt.get('distribution', {})
            if dist.get('labels'):
                charts.append({
                    'id': 'chart_nature_pie',
                    'title': '各类性质占比',
                    'type': 'pie',
                    'option': render_pie(dist['labels'], dist['values']),
                })
                total = sum(dist['values']) or 1
                rows = [[l, str(v), f'{round(v/total*100,1)}%'] for l, v in zip(dist['labels'], dist['values'])]
                data_table = {'headers': ['性质', '数量', '占比'], 'rows': rows}
            if nt.get('trend', {}).get('series'):
                charts.append({
                    'id': 'chart_nature_trend',
                    'title': '各类性质周趋势',
                    'type': 'line',
                    'option': render_line(nt['trend']['labels'], nt['trend']['series']),
                })

        elif group_by == 'cross':
            ct = processor.get_status_by_service_group(filters)
            charts.append({
                'id': 'chart_cross',
                'title': '服务组×状态交叉分析',
                'type': 'stacked_bar',
                'option': render_stacked_bar(ct['groups'], ct['statuses']),
            })

        elif group_by == '_dynamic':
            unmatched = intent.get('unmatched_query', '')
            dim_col = processor.find_dynamic_dimension(unmatched) if unmatched else None
            if dim_col and dim_col in processor.df.columns:
                counts = processor._apply_filters(filters)[dim_col].value_counts()
                cn_name = dim_col
                for cn, en in processor.COL_MAP.items():
                    if en == dim_col:
                        cn_name = cn
                        break
                charts.append({
                    'id': f'chart_dynamic_{dim_col}',
                    'title': f'{cn_name}分布',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(list(counts.index.astype(str)), [int(v) for v in counts.values]),
                })
                rows = [[str(k), str(v)] for k, v in counts.items()]
                data_table = {'headers': [cn_name, '工单数'], 'rows': rows}

        # 无明确 group_by 时，回退到通用全景图
        if not charts:
            if status_dist.get('labels'):
                charts.append({
                    'id': 'chart_status',
                    'title': '工单状态分布',
                    'type': 'pie',
                    'option': render_pie(status_dist['labels'], status_dist['values']),
                })
            if weekly_trend.get('labels'):
                charts.append({
                    'id': 'chart_weekly',
                    'title': '近4周工单趋势',
                    'type': 'line',
                    'option': render_line(weekly_trend['labels'], [{'name': '工单数', 'data': weekly_trend['values']}]),
                })
            if sg_dist.get('labels'):
                charts.append({
                    'id': 'chart_sg',
                    'title': '服务组工单量 TOP5',
                    'type': 'horizontal_bar',
                    'option': render_horizontal_bar(sg_dist['labels'][:5], sg_dist['values'][:5]),
                })

        # 5. 从 LLM 响应中提取洞察卡片
        deep_insights = self._extract_insight_cards(response)

        return {
            'message': response,
            'charts': charts,
            'insights': [],
            'data_table': data_table,
            'deep_insights': deep_insights,
        }

    def _extract_insight_cards(self, text: str) -> list[dict]:
        """从 LLM 响应中提取结构化洞察卡片。"""
        import re
        cards = []

        # 匹配 [🔥 xxx] 或 [🕵️ xxx] 或 [🎯 xxx] 格式的标签行
        tag_pattern = r'\[([🔥🕵️🎯⚠️💡📊🔍📈]+)\s*([^\]]+)\]'
        tag_map = {
            '🔥': {'tag': '暴增预警', 'severity': 'danger'},
            '🕵️': {'tag': '隐性根因', 'severity': 'warning'},
            '🎯': {'tag': '黄金建议', 'severity': 'success'},
            '⚠️': {'tag': '风险警示', 'severity': 'danger'},
            '💡': {'tag': '行动建议', 'severity': 'info'},
            '📊': {'tag': '现状扫描', 'severity': 'info'},
            '🔍': {'tag': '根因推导', 'severity': 'warning'},
            '': {'tag': '趋势预测', 'severity': 'info'},
        }

        # 按 emoji 标签分割文本
        # 按行分割，找到每个标签行
        lines = text.split('\n')
        cards = []
        current_card = None
        current_content = []

        for line in lines:
            m = re.match(tag_pattern, line.strip())
            if m:
                # 保存上一个卡片
                if current_card and current_content:
                    current_card['content'] = '\n'.join(current_content).strip()[:500]
                    cards.append(current_card)

                emoji = m.group(1).strip()
                tag_title = m.group(2).strip()
                first_emoji = emoji[0] if emoji else ''
                info = tag_map.get(first_emoji, {'tag': tag_title, 'severity': 'info'})

                current_card = {
                    'tag': info['tag'],
                    'title': tag_title,
                    'content': '',
                    'severity': info['severity'],
                }
                current_content = []
            elif current_card is not None:
                current_content.append(line)

        # 保存最后一个卡片
        if current_card and current_content:
            current_card['content'] = '\n'.join(current_content).strip()[:500]
            cards.append(current_card)

        return cards

    # ===== 智能问答 Handler =====

    async def _handle_chitchat(self, intent: dict) -> dict:
        user_message = intent.get('message', '')
        processor = self._resolve_processor(intent)

        if not self.llm:
            return {
                'message': '你好！我是工单数据分析助手，可以帮助你分析工单的分布、趋势、SLA 达标率、重复问题挖掘、故障根因分析等。你可以试着问我"工单状态分布"、"最近趋势"、"哪些故障反复出现"、"请求人行为分析"。',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        data_context = ""
        if processor:
            try:
                kpis = processor.get_summary_kpis()
                status_dist = processor.get_status_distribution()
                sg_dist = processor.get_service_group_distribution()
                eval_data = processor.get_evaluation_summary()
                recurring = processor.get_recurring_tickets()
                ops = processor.get_ops_quality_metrics()
                behavior = processor.get_requester_behavior()
                root_cause = processor.get_fault_root_cause_analysis()

                status_str = ', '.join([f"{l}:{v}件" for l, v in zip(status_dist['labels'][:5], status_dist['values'][:5])])
                sg_str = ', '.join([f"{l}:{v}件" for l, v in zip(sg_dist['labels'][:5], sg_dist['values'][:5])])

                recurring_str = ''
                if recurring['by_fault_group']:
                    top3 = recurring['by_fault_group'][:3]
                    recurring_str = ', '.join([f'"{d["cause"]}"({d["count"]}次)' for d in top3])

                root_cause_str = ''
                if root_cause.get('fault_top_n'):
                    top3_fault = root_cause['fault_top_n'][:3]
                    root_cause_str = ', '.join([f'"{f["cause"]}"({f["count"]}次)' for f in top3_fault])

                behavior_str = ''
                if behavior.get('top_requesters') and behavior['top_requesters']['values']:
                    req_top = list(zip(behavior['top_requesters']['labels'][:3], behavior['top_requesters']['values'][:3]))
                    behavior_str = ', '.join([f'"{r[0]}"({r[1]}件)' for r in req_top])

                data_context = f"""【当前ITSM工单数据全景】
总工单: {kpis['total']}件 | 已解决: {kpis['resolved_count']}件({kpis['resolved_ratio']}%)
SLA达标率: {kpis['sla_ratio']}%(均{kpis['sla_avg']}%) | 平均解决: {kpis['avg_resolution_days']}天
挂起: {kpis['suspended_count']}件 | 退回: {kpis['returned_count']}件 | 撤单: {kpis['cancelled_count']}件
状态分布: {status_str}
服务组TOP5: {sg_str}
重复故障TOP3: {recurring_str or '无'}
根因TOP3: {root_cause_str or '无'}
高频请求人TOP3: {behavior_str or '无'}
满意度: 服务态度{round(float(eval_data.get('attitude_avg', 0)), 1)}分/技术水平{round(float(eval_data.get('tech_avg', 0)), 1)}分/响应时效{round(float(eval_data.get('response_avg', 0)), 1)}分({eval_data.get('eval_count', 0)}条)
退回率: {ops['returned_ratio']}% | 挂起率: {ops['suspended_ratio']}% | 撤单率: {ops['cancelled_ratio']}%
组织广度: {behavior.get('summary', {}).get('total_departments', 0)}个部门/{behavior.get('summary', {}).get('total_orgs', 0)}个机构/{behavior.get('summary', {}).get('total_requesters', 0)}个请求人"""
            except Exception:
                data_context = ""

        system_prompt = f"""你是ITSM工单数据分析助手MiMo，具备以下核心分析能力：

1. **故障根因与问题分类** — 在症状、故障原因、解决方案之间建立关联，精准归类
2. **运维质量改进** — 分析退回率/挂起率/撤单率/SLA趋势，定位运维短板
3. **高频故障挖掘** — 识别重复出现的同类工单，推动根本解决
4. **TopN故障趋势** — 跟踪主要故障原因的时间走势
5. **请求人行为与组织分析** — 分析哪些部门/人员提交最多、是否有异常行为模式
6. **症状→解决方案聚类** — 为常见症状关联最佳解决方案

{data_context}

回答原则：
- 先理解用户提问的真实意图（分析？诊断？建议？），精准分类
- 根据数据上下文进行详细分析，给出有深度的洞察
- 识别数据中的异常模式（突发增长、集中故障、重复问题）
- 回答时引用具体数据支撑观点
- 如数据不足，说明原因并建议补充方式
- 对于分析类问题，给出可操作的改进建议
- 使用列表或分层结构让分析清晰易读"""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        chat_history = intent.get('chat_history', [])
        for m in chat_history[-6:]:
            messages.append({"role": m['role'], "content": m['content']})

        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.llm.chat_completion(messages, temperature=0.7, max_tokens=2048)
        except Exception:
            response = "抱歉，我暂时无法回答这个问题，请稍后再试。"

        return {
            'message': response,
            'charts': [],
            'insights': [],
            'data_table': None,
        }
