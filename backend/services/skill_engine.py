"""Skill 执行引擎：注册、分发、执行工单分析技能。"""

from __future__ import annotations
import json
import os
import re
from typing import Callable, Optional

from backend.services.ticket_processor import TicketProcessor
from backend.services.chart_renderer import (
    render_pie, render_bar, render_stacked_bar, render_horizontal_bar, render_rose, render_line,
)

SKILLS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'harness', 'skills')


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

    def __init__(self, processor: TicketProcessor, llm_provider=None):
        self.processor = processor
        self.llm = llm_provider
        self._skills: dict[str, dict] = {}
        self._handlers: dict[str, Callable] = {
            'ticket_analysis': self._handle_ticket_analysis,
            'data_query': self._handle_data_query,
            'report_export': self._handle_report_export,
        }
        self._auto_discover_skills()
        self._register_chitchat()

    def _auto_discover_skills(self):
        if not os.path.isdir(SKILLS_DIR):
            self._register_ticket_analysis()
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
                continue

            self.register_skill(sid, {
                'name': meta.get('name', sid),
                'description': meta.get('description', ''),
                'enabled': meta.get('enabled', True),
                'category': meta.get('category', ''),
                'priority': meta.get('priority', 99),
                'handler': handler,
            })

    def _register_ticket_analysis(self):
        self.register_skill('ticket_analysis', {
            'name': '工单数据分析',
            'description': '分析工单数据，生成统计图表',
            'enabled': True,
            'category': 'analysis',
            'priority': 1,
            'handler': self._handle_ticket_analysis,
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
        if not self.processor:
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

        kpis = self.processor.get_summary_kpis(filters)

        # ---- 状态分布 ----
        if group_by == 'status' or chart_type == 'pie':
            dist = self.processor.get_status_distribution(filters)
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
            dist = self.processor.get_service_group_distribution(filters)
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
            dist = self.processor.get_assignee_distribution(filters)
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
            dist = self.processor.get_department_distribution(filters)
            charts.append({
                'id': 'chart_dept',
                'title': '请求部门分布',
                'type': 'bar',
                'option': render_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，涉及 {len(dist["labels"])} 个部门。'

        # ---- 来源渠道分布 ----
        elif group_by == 'source_channel':
            dist = self.processor.get_source_channel_distribution(filters)
            charts.append({
                'id': 'chart_source',
                'title': '来源渠道分布',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，来源渠道分布如上。'

        # ---- 故障原因分组 ----
        elif group_by == 'fault_group':
            dist = self.processor.get_fault_group_distribution(filters)
            charts.append({
                'id': 'chart_fault',
                'title': '故障原因分组',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，故障原因分组如上。'

        # ---- 原因类别 ----
        elif group_by == 'cause_category':
            dist = self.processor.get_cause_category_distribution(filters)
            charts.append({
                'id': 'chart_cause',
                'title': '原因类别分布',
                'type': 'pie',
                'option': render_pie(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，原因类别分布如上。'

        # ---- 业务系统分布 ----
        elif group_by == 'business_system':
            dist = self.processor.get_business_system_distribution(filters)
            charts.append({
                'id': 'chart_sys',
                'title': '业务系统分布',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，覆盖 {len(dist["labels"])} 个业务系统。'

        # ---- 解决人 ----
        elif group_by == 'resolver':
            dist = self.processor.get_resolver_distribution(filters)
            charts.append({
                'id': 'chart_resolver',
                'title': '解决人处理量',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(dist['labels'], dist['values']),
            })
            summary = f'共 {kpis["total"]} 件工单，解决人处理量如上。'

        # ---- 周趋势 ----
        elif group_by == 'weekly':
            trend = self.processor.get_weekly_trend(filters)
            charts.append({
                'id': 'chart_weekly',
                'title': '每周工单趋势',
                'type': 'line',
                'option': render_line(trend['labels'], [{'name': '工单数', 'data': trend['values']}]),
            })
            summary = f'每周工单趋势如上，共 {kpis["total"]} 件工单。'

        # ---- 月趋势 ----
        elif group_by == 'monthly':
            trend = self.processor.get_monthly_trend(filters)
            charts.append({
                'id': 'chart_monthly',
                'title': '每月工单趋势',
                'type': 'line',
                'option': render_line(trend['labels'], [{'name': '工单数', 'data': trend['values']}]),
            })
            summary = f'每月工单趋势如上，共 {kpis["total"]} 件工单。'

        # ---- SLA 趋势 ----
        elif group_by == 'sla':
            trend = self.processor.get_sla_weekly_trend(filters)
            charts.append({
                'id': 'chart_sla_trend',
                'title': 'SLA 达标率周趋势',
                'type': 'line',
                'option': render_line(trend['labels'], [{'name': 'SLA(%)', 'data': trend['values']}]),
            })
            summary = f'SLA 平均达标率 {kpis["sla_avg"]}%，趋势如上。'

        # ---- 解决时效 ----
        elif group_by == 'resolution_time':
            buckets = self.processor.get_resolution_time_buckets(filters)
            charts.append({
                'id': 'chart_res_time',
                'title': '解决时效分布',
                'type': 'bar',
                'option': render_bar(buckets['labels'], buckets['values']),
            })
            summary = f'平均解决时间 {kpis["avg_resolution_days"]} 天。'

        # ---- 挂起分析 ----
        elif group_by == 'suspended':
            sus = self.processor.get_suspended_breakdown(filters)
            charts.append({
                'id': 'chart_suspended',
                'title': '挂起原因分析',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(sus['labels'], sus['values']),
            })
            summary = f'共 {kpis["suspended_count"]} 件挂起工单（{kpis["suspended_ratio"]}%）。'

        # ---- 交叉分析：服务组×状态 ----
        elif chart_type == 'stacked_bar':
            ct = self.processor.get_status_by_service_group(filters)
            charts.append({
                'id': 'chart_cross',
                'title': '服务组×状态交叉分析',
                'type': 'stacked_bar',
                'option': render_stacked_bar(ct['groups'], ct['statuses']),
            })
            summary = f'各服务组工单状态结构如上。'

        # ---- 新增：故障根因深度分析 ----
        elif group_by == 'root_cause':
            rc = self.processor.get_fault_root_cause_analysis(filters)
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
            dup = self.processor.get_recurring_tickets(filters)
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
            ops = self.processor.get_ops_quality_metrics(filters)
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
            mapping = self.processor.get_symptom_solution_mapping(filters)
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
            behavior = self.processor.get_requester_behavior(filters)
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
            nt = self.processor.get_nature_trend(filters)
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

        insights = self.processor.generate_insights(filters)

        return {
            'message': summary,
            'charts': charts,
            'insights': insights,
            'data_table': data_table,
        }

    # ===== 数据查询 Handler =====

    async def _handle_data_query(self, intent: dict) -> dict:
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

        # 按 query_type 分发到不同的 TicketProcessor 方法
        query_handlers = {
            'status_distribution': lambda f: (self.processor.get_status_distribution(f), 'pie', '状态分布'),
            'service_group_distribution': lambda f: (self.processor.get_service_group_distribution(f), 'horizontal_bar', '服务组工作量'),
            'assignee_distribution': lambda f: (self.processor.get_assignee_distribution(f, top_n=15), 'horizontal_bar', '责任人处理量'),
            'department_distribution': lambda f: (self.processor.get_department_distribution(f), 'bar', '部门分布'),
            'source_channel_distribution': lambda f: (self.processor.get_source_channel_distribution(f), 'pie', '来源渠道分布'),
            'fault_group_distribution': lambda f: (self.processor.get_fault_group_distribution(f), 'pie', '故障原因分组'),
            'cause_category_distribution': lambda f: (self.processor.get_cause_category_distribution(f), 'pie', '原因类别'),
            'weekly_trend': lambda f: (self.processor.get_weekly_trend(f), 'line', '每周趋势'),
            'monthly_trend': lambda f: (self.processor.get_monthly_trend(f), 'line', '每月趋势'),
            'sla_weekly_trend': lambda f: (self.processor.get_sla_weekly_trend(f), 'line', 'SLA趋势'),
            'suspended_breakdown': lambda f: (self.processor.get_suspended_breakdown(f), 'horizontal_bar', '挂起原因'),
            'evaluation_summary': lambda f: (self.processor.get_evaluation_summary(f), None, '满意度'),
            'resolution_time_buckets': lambda f: (self.processor.get_resolution_time_buckets(f), 'bar', '解决时效'),
            'fault_root_cause_analysis': lambda f: (self.processor.get_fault_root_cause_analysis(f), None, '故障根因分析'),
            'fault_cause_trend': lambda f: (self.processor.get_fault_cause_trend(f), 'line', '故障原因趋势'),
            'symptom_solution_mapping': lambda f: (self.processor.get_symptom_solution_mapping(f), None, '症状方案聚类'),
            'recurring_tickets': lambda f: (self.processor.get_recurring_tickets(f), None, '重复工单'),
            'nature_trend': lambda f: (self.processor.get_nature_trend(f), None, '性质趋势'),
            'requester_behavior': lambda f: (self.processor.get_requester_behavior(f), None, '请求人行为'),
            'ops_quality_metrics': lambda f: (self.processor.get_ops_quality_metrics(f), None, '运维质量'),
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
            kpis = self.processor.get_summary_kpis(filters)
            rows = [
                ['总工单数', str(kpis['total'])],
                ['已解决', f'{kpis["resolved_count"]}件 ({kpis["resolved_ratio"]}%)'],
                ['SLA 达标率', f'{kpis["sla_ratio"]}%'],
                ['平均解决天数', f'{kpis["avg_resolution_days"]}天'],
            ]
            data_table = {'headers': ['指标', '值'], 'rows': rows}
            summary = f'KPI 汇总：总工单 {kpis["total"]} 件，SLA 达标率 {kpis["sla_ratio"]}%。'

        insights = self.processor.generate_insights(filters)

        return {
            'message': summary,
            'charts': charts,
            'insights': insights,
            'data_table': data_table,
        }

    # ===== 报告导出 Handler =====

    async def _handle_report_export(self, intent: dict) -> dict:
        if not self.processor:
            return {
                'message': '暂无可用的数据源，请先上传 Excel 文件。',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        filters = intent.get('filters', {})
        kpis = self.processor.get_summary_kpis(filters)

        status_dist = self.processor.get_status_distribution(filters)
        sg_dist = self.processor.get_service_group_distribution(filters)
        assignee_dist = self.processor.get_assignee_distribution(filters)
        weekly_trend = self.processor.get_weekly_trend(filters)
        insights = self.processor.generate_insights(filters)

        charts = [
            {
                'id': 'chart_status',
                'title': '工单状态分布',
                'type': 'pie',
                'option': render_pie(status_dist['labels'], status_dist['values']),
            },
            {
                'id': 'chart_sg',
                'title': '服务组工单量',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(sg_dist['labels'], sg_dist['values']),
            },
            {
                'id': 'chart_assignee',
                'title': '责任人处理量',
                'type': 'horizontal_bar',
                'option': render_horizontal_bar(assignee_dist['labels'], assignee_dist['values']),
            },
        ]

        if weekly_trend['labels']:
            charts.append({
                'id': 'chart_weekly',
                'title': '每周工单趋势',
                'type': 'line',
                'option': render_line(weekly_trend['labels'], [{'name': '工单数', 'data': weekly_trend['values']}]),
            })

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

        return {
            'message': f'工单分析报告已生成。共 {kpis["total"]} 件工单，SLA 达标率 {kpis["sla_ratio"]}%。',
            'charts': charts,
            'insights': insights,
            'data_table': data_table,
        }

    # ===== 智能问答 Handler =====

    async def _handle_chitchat(self, intent: dict) -> dict:
        user_message = intent.get('message', '')

        if not self.llm:
            return {
                'message': '你好！我是工单数据分析助手，可以帮助你分析工单的分布、趋势、SLA 达标率、重复问题挖掘、故障根因分析等。你可以试着问我"工单状态分布"、"最近趋势"、"哪些故障反复出现"、"请求人行为分析"。',
                'charts': [],
                'insights': [],
                'data_table': None,
            }

        data_context = ""
        if self.processor:
            try:
                kpis = self.processor.get_summary_kpis()
                status_dist = self.processor.get_status_distribution()
                sg_dist = self.processor.get_service_group_distribution()
                eval_data = self.processor.get_evaluation_summary()
                recurring = self.processor.get_recurring_tickets()
                ops = self.processor.get_ops_quality_metrics()
                behavior = self.processor.get_requester_behavior()
                root_cause = self.processor.get_fault_root_cause_analysis()

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
