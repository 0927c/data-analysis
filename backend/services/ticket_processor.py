"""工单数据处理服务 — 从 Excel 读取 ITSM 工单数据，提供多维度统计分析。"""

from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

# ---- 分析维度的中文→英文字段映射（供 IntentParser / LLM 使用） ----
ANALYSIS_DIMENSIONS = {
    'status': '状态',
    'priority': '性质',
    'assignee': '责任人',
    'resolver': '解决人',
    'department': '请求人部门',
    'org': '请求人机构',
    'service_group': '所属服务组',
    'service': '所属服务',
    'business_system': '所属业务系统',
    'business_module': '所属业务系统模块',
    'source': '来源',
    'source_channel': '来源渠道',
    'cause_category': '原因类别',
    'fault_group': '故障原因分组',
    'fault_cause': '故障原因',
    'symptom': '症状',
    'resolution': '处理方式',
    'sla': 'SLA百分比',
    'suspended': '是否挂起过',
    'returned': '是否退回过服务台',
    'cancelled': '是否撤单',
    'evaluated': '是否评价',
}

# 用于规则引擎的关键词映射
INTENT_DIMENSION_KEYWORDS = {
    '状态': 'status', '工单状态': 'status',
    '服务组': 'service_group', '所属服务组': 'service_group',
    '责任人': 'assignee', '处理人': 'assignee', '谁处理': 'assignee',
    '部门': 'department', '请求部门': 'department',
    '来源': 'source', '来源渠道': 'source_channel', '渠道': 'source_channel',
    '原因': 'cause_category', '故障原因': 'fault_group', '故障分组': 'fault_group',
    'SLA': 'sla', '时效': 'sla', '达标率': 'sla', '超时': 'sla',
    '挂起': 'suspended', '挂起工单': 'suspended',
    '评价': 'evaluated', '满意度': 'evaluated', '评分': 'evaluated',
    '业务系统': 'business_system', '模块': 'business_module',
    '趋势': 'trend', '变化': 'trend', '走势': 'trend',
    '排名': 'rank', '最多': 'rank', 'TOP': 'rank',
    '分布': 'dist', '占比': 'dist', '比例': 'dist',
    '解决': 'resolver', '解决人': 'resolver', '解决时长': 'resolution_time',
    '周报': 'weekly', '月报': 'monthly',
}


# ============================================================
# TicketProcessor 服务类
# ============================================================
class TicketProcessor:
    """ITSM 工单数据处理服务。从 Excel 读取、清洗、提供多维度统计分析。"""

    COL_MAP = {
        '编号': 'ticket_id',
        '标题': 'title',
        '详细': 'description',
        '创建时间': 'created_at',
        '请求人部门': 'requester_dept',
        '请求人': 'requester',
        '创建人': 'creator',
        '来源': 'source',
        '状态': 'status',
        '责任角色': 'responsible_role',
        '责任人': 'responsible_person',
        '请求人联系方式': 'requester_contact',
        '解决角色': 'resolver_role',
        '解决人': 'resolver',
        '解决时间': 'resolved_at',
        '更新人': 'updater',
        '更新时间': 'updated_at',
        '所属服务组': 'service_group',
        '所属服务': 'service_name',
        '所属业务系统': 'business_system',
        '所属业务系统模块': 'business_module',
        '是否评价': 'is_evaluated',
        '服务态度': 'attitude_score',
        '技术水平': 'tech_score',
        '响应时效': 'response_score',
        '评价内容': 'eval_content',
        'SLA百分比': 'sla_percent',
        '是否挂起过': 'is_suspended',
        '挂起时长': 'suspend_duration',
        '挂起原因': 'suspend_reason',
        '症状': 'symptom',
        '是否退回过服务台': 'is_returned',
        '故障原因': 'fault_cause',
        '性质': 'nature',
        '解决办法': 'solution',
        '来源渠道': 'source_channel',
        '故障原因分组': 'fault_group',
        '流程链信息': 'process_chain',
        '请求人机构': 'requester_org',
        '请求人职务': 'requester_title',
        '原因类别': 'cause_category',
        '处理方式': 'resolution_method',
        '是否撤单': 'is_cancelled',
        '备注1': 'remark1',
    }

    def __init__(self, excel_path: str, custom_col_map: dict = None):
        self.excel_path = Path(excel_path)
        self._df: pd.DataFrame | None = None
        self._custom_col_map = custom_col_map  # 用户自定义字段映射

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._load()
        return self._df

    def _get_col_map(self) -> dict:
        """获取实际使用的列映射（自定义优先，否则使用默认 COL_MAP）。"""
        if self._custom_col_map:
            return {**self.COL_MAP, **self._custom_col_map}
        return self.COL_MAP

    def find_dynamic_dimension(self, query_text: str) -> Optional[str]:
        """根据用户查询文本，在 DataFrame 列中模糊匹配最相关的维度列。

        返回匹配的列名（英文），未匹配返回 None。
        匹配策略：
        1. 精确命中 ANALYSIS_DIMENSIONS 中文值 → 返回对应的 key
        2. 模糊子串匹配列名（中文或英文）
        3. 未匹配返回 None
        """
        if not query_text:
            return None
        text = query_text.lower().strip()
        col_map = self._get_col_map()  # 中文列名 → 英文列名

        # 策略1：精确匹配 ANALYSIS_DIMENSIONS 中文值
        for dim_key, dim_cn in ANALYSIS_DIMENSIONS.items():
            if dim_cn in query_text or dim_cn.lower() in text:
                if dim_key in ('status', 'sla', 'suspended', 'returned', 'cancelled', 'evaluated'):
                    continue  # 布尔/指标维度不做分组
                return dim_key

        # 策略2：子串匹配列名（中文→英文映射，以及英文列名直接匹配）
        best_col = None
        best_score = 0
        for cn_col, en_col in col_map.items():
            # 跳过时间、ID、文本类列
            if en_col in ('ticket_id', 'title', 'description', 'created_at', 'resolved_at',
                          'updated_at', 'updater', 'creator', 'remark1', 'process_chain',
                          'eval_content', 'solution', 'requester_contact'):
                continue
            cn_lower = cn_col.lower()
            en_lower = en_col.lower()
            # 中文列名子串匹配
            if cn_lower in text or text in cn_lower:
                score = len(cn_lower)
                if score > best_score:
                    best_score = score
                    best_col = en_col
            # 英文列名字串匹配（如 "dept" in "requester_dept"）
            elif en_lower in text or text in en_lower:
                score = len(en_lower) * 0.8
                if score > best_score:
                    best_score = score
                    best_col = en_col
            # 列名拆分后的词匹配
            elif any(part in text for part in cn_lower.replace('所属', '').replace('是否', '').replace('请求人', '') if len(part) >= 2):
                score = 2
                if score > best_score:
                    best_score = score
                    best_col = en_col

        return best_col

    def _load(self):
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel 文件不存在: {self.excel_path}")

        df = pd.read_excel(self.excel_path, sheet_name=0)

        col_map = self._get_col_map()
        rename_map = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # 解析时间字段
        for col in ['created_at', 'resolved_at', 'updated_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # 解析 SLA 百分比为数值
        if 'sla_percent' in df.columns:
            df['sla_percent_num'] = pd.to_numeric(df['sla_percent'], errors='coerce').fillna(0)

        # 计算解决耗时（天）
        if 'created_at' in df.columns and 'resolved_at' in df.columns:
            df['resolution_days'] = (df['resolved_at'] - df['created_at']).dt.total_seconds() / 86400
            df['resolution_days'] = df['resolution_days'].clip(lower=0)

        # 创建时间维度
        if 'created_at' in df.columns:
            df['created_week'] = df['created_at'].dt.isocalendar().week.astype(int)
            df['created_year'] = df['created_at'].dt.year.astype(int)
            df['created_week_label'] = df['created_year'].astype(str) + '-W' + df['created_week'].astype(str).str.zfill(2)
            df['created_month'] = df['created_at'].dt.to_period('M').astype(str)

        self._df = df

    def _apply_filters(self, filters: Optional[dict] = None) -> pd.DataFrame:
        df = self.df
        if not filters:
            return df

        filtered = df.copy()
        field_to_col = {
            'status': 'status',
            'assignee': 'responsible_person',
            'resolver': 'resolver',
            'department': 'requester_dept',
            'org': 'requester_org',
            'service_group': 'service_group',
            'business_system': 'business_system',
            'business_module': 'business_module',
            'source': 'source',
            'source_channel': 'source_channel',
            'cause_category': 'cause_category',
            'fault_group': 'fault_group',
            'suspended': 'is_suspended',
            'nature': 'nature',
        }

        for fkey, fval in filters.items():
            if fkey in field_to_col:
                col = field_to_col[fkey]
                if col in filtered.columns:
                    # 模糊匹配：支持 "PPM" 匹配 "PPM正式环境"
                    if isinstance(fval, str):
                        filtered = filtered[filtered[col].astype(str).str.contains(fval, na=False, case=False)]
                    else:
                        filtered = filtered[filtered[col] == fval]
            elif fkey == 'date_from' and 'created_at' in filtered.columns:
                filtered = filtered[filtered['created_at'] >= pd.Timestamp(fval)]
            elif fkey == 'date_to' and 'created_at' in filtered.columns:
                filtered = filtered[filtered['created_at'] <= pd.Timestamp(fval)]

        return filtered

    def get_unique_values(self, column: str) -> list:
        """获取某列的去重值列表（供前端下拉）"""
        col = self.COL_MAP.get(column, column)
        if col in self.df.columns:
            return self.df[col].dropna().unique().tolist()
        return []

    # ===== KPI 汇总 =====

    def get_summary_kpis(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        total = len(df)

        # SLA 达标率
        sla_qualified = len(df[df['sla_percent_num'] <= 100]) if 'sla_percent_num' in df.columns else 0
        sla_ratio = round(sla_qualified / total * 100, 1) if total else 0

        # SLA 平均
        sla_avg = round(df['sla_percent_num'].mean(), 1) if 'sla_percent_num' in df.columns else 0

        # 已解决数（"结束"=已关闭也算解决）
        resolved_count = len(df[df['status'].isin(['已解决', '已关闭', '关闭', '结束'])]) if 'status' in df.columns else 0
        resolved_ratio = round(resolved_count / total * 100, 1) if total else 0

        # 挂起数
        suspended_count = len(df[df['is_suspended'] == '是']) if 'is_suspended' in df.columns else 0
        suspended_ratio = round(suspended_count / total * 100, 1) if total else 0

        # 平均解决天数
        avg_days = round(df['resolution_days'].mean(), 1) if 'resolution_days' in df.columns and len(df[df['resolution_days'].notna()]) > 0 else 0

        # 退回服务台数
        returned_count = len(df[df['is_returned'] == '是']) if 'is_returned' in df.columns else 0

        # 评价率
        evaluated_count = len(df[df['is_evaluated'] == '是']) if 'is_evaluated' in df.columns else 0
        evaluated_ratio = round(evaluated_count / total * 100, 1) if total else 0

        # 撤单数
        cancelled_count = len(df[df['is_cancelled'] == '是']) if 'is_cancelled' in df.columns else 0

        return {
            'total': total,
            'resolved_count': resolved_count,
            'resolved_ratio': resolved_ratio,
            'sla_qualified': sla_qualified,
            'sla_ratio': sla_ratio,
            'sla_avg': sla_avg,
            'suspended_count': suspended_count,
            'suspended_ratio': suspended_ratio,
            'avg_resolution_days': avg_days,
            'returned_count': returned_count,
            'evaluated_count': evaluated_count,
            'evaluated_ratio': evaluated_ratio,
            'cancelled_count': cancelled_count,
        }

    # ===== 分布统计 =====

    def get_status_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'status' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['status'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_service_group_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'service_group' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['service_group'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_assignee_distribution(self, filters: Optional[dict] = None, top_n: int = 15) -> dict:
        df = self._apply_filters(filters)
        if 'responsible_person' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['responsible_person'].value_counts().head(top_n)
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_department_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'requester_dept' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['requester_dept'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_org_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'requester_org' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['requester_org'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_source_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'source' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['source'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_source_channel_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'source_channel' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['source_channel'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_fault_group_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'fault_group' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['fault_group'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_cause_category_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'cause_category' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['cause_category'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_business_system_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'business_system' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['business_system'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_nature_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'nature' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['nature'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_resolution_method_distribution(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'resolution_method' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['resolution_method'].value_counts()
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    def get_resolver_distribution(self, filters: Optional[dict] = None, top_n: int = 15) -> dict:
        df = self._apply_filters(filters)
        if 'resolver' not in df.columns:
            return {'labels': [], 'values': []}
        counts = df['resolver'].value_counts().head(top_n)
        return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

    # ===== 交叉分析 =====

    def get_status_by_service_group(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'service_group' not in df.columns or 'status' not in df.columns:
            return {'groups': [], 'statuses': {}}
        ct = pd.crosstab(df['service_group'], df['status'])
        groups = sorted(ct.index.tolist())
        statuses = {}
        for s in ct.columns:
            statuses[s] = {g: int(ct.loc[g, s]) if g in ct.index else 0 for g in groups}
        return {'groups': groups, 'statuses': statuses}

    # ===== 趋势分析 =====

    def get_weekly_trend(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'created_week_label' not in df.columns:
            return {'labels': [], 'values': []}
        trend = df.groupby('created_week_label').size().sort_index()
        return {'labels': list(trend.index), 'values': [int(v) for v in trend.values]}

    def get_monthly_trend(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'created_month' not in df.columns:
            return {'labels': [], 'values': []}
        trend = df.groupby('created_month').size().sort_index()
        return {'labels': list(trend.index), 'values': [int(v) for v in trend.values]}

    def get_sla_weekly_trend(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'created_week_label' not in df.columns or 'sla_percent_num' not in df.columns:
            return {'labels': [], 'values': []}
        sla_trend = df.groupby('created_week_label')['sla_percent_num'].mean().sort_index()
        return {'labels': list(sla_trend.index), 'values': [round(v, 1) for v in sla_trend.values]}

    # ===== 挂起分析 =====

    def get_suspended_breakdown(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'is_suspended' not in df.columns:
            return {'labels': [], 'values': []}
        suspended = df[df['is_suspended'] == '是']
        if 'suspend_reason' in suspended.columns:
            counts = suspended['suspend_reason'].value_counts()
            return {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}
        return {'labels': ['挂起'], 'values': [len(suspended)]}

    # ===== 满意度分析 =====

    def get_evaluation_summary(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'is_evaluated' not in df.columns:
            return {'attitude_avg': 0, 'tech_avg': 0, 'response_avg': 0, 'eval_count': 0}

        evaluated = df[df['is_evaluated'] == '是']
        if len(evaluated) == 0:
            return {'attitude_avg': 0, 'tech_avg': 0, 'response_avg': 0, 'eval_count': 0}

        def safe_mean(col):
            if col in evaluated.columns:
                vals = pd.to_numeric(evaluated[col], errors='coerce').dropna()
                return round(vals.mean(), 2) if len(vals) > 0 else 0
            return 0

        return {
            'attitude_avg': safe_mean('attitude_score'),
            'tech_avg': safe_mean('tech_score'),
            'response_avg': safe_mean('response_score'),
            'eval_count': len(evaluated),
        }

    # ===== 解决时效分析 =====

    def get_resolution_time_buckets(self, filters: Optional[dict] = None) -> dict:
        df = self._apply_filters(filters)
        if 'resolution_days' not in df.columns:
            return {'labels': [], 'values': []}

        resolved = df[df['resolution_days'].notna()]
        buckets = {'<1天': 0, '1-3天': 0, '3-7天': 0, '7-14天': 0, '14-30天': 0, '>30天': 0}
        for d in resolved['resolution_days']:
            if d < 1:
                buckets['<1天'] += 1
            elif d <= 3:
                buckets['1-3天'] += 1
            elif d <= 7:
                buckets['3-7天'] += 1
            elif d <= 14:
                buckets['7-14天'] += 1
            elif d <= 30:
                buckets['14-30天'] += 1
            else:
                buckets['>30天'] += 1

        ordered = ['<1天', '1-3天', '3-7天', '7-14天', '14-30天', '>30天']
        return {'labels': ordered, 'values': [buckets[k] for k in ordered]}

    # ===== 故障根因深度分析 =====

    def get_fault_root_cause_analysis(self, filters: Optional[dict] = None) -> dict:
        """故障根因深度分析：原因类别→故障分组→症状的层级钻取。"""
        df = self._apply_filters(filters)

        result = {
            'cause_categories': {},
            'fault_groups': {},
            'fault_top_n': [],
        }

        # 原因类别→故障分组映射
        if 'cause_category' in df.columns and 'fault_group' in df.columns:
            for cause in df['cause_category'].dropna().unique():
                sub = df[df['cause_category'] == cause]
                fg_counts = sub['fault_group'].value_counts().to_dict()
                result['cause_categories'][cause] = {
                    'count': int(len(sub)),
                    'fault_groups': {str(k): int(v) for k, v in fg_counts.items()},
                }

        # 故障分组统计
        if 'fault_group' in df.columns:
            fg = df['fault_group'].value_counts()
            result['fault_groups'] = {'labels': list(fg.index), 'values': [int(v) for v in fg.values]}

        # 症状→原因→方案映射
        if 'symptom' in df.columns and 'fault_cause' in df.columns and 'solution' in df.columns:
            symptom_map = defaultdict(lambda: {'count': 0, 'causes': defaultdict(int), 'solutions': defaultdict(int)})
            for _, row in df.iterrows():
                symptom = str(row.get('symptom', '')).strip()
                if not symptom or symptom == 'nan':
                    continue
                symptom_map[symptom]['count'] += 1
                cause = str(row.get('fault_cause', '')).strip()
                if cause and cause != 'nan':
                    symptom_map[symptom]['causes'][cause] += 1
                solution = str(row.get('solution', '')).strip()
                if solution and solution != 'nan':
                    symptom_map[symptom]['solutions'][solution] += 1

            # 转列表排序
            sorted_symptoms = sorted(symptom_map.items(), key=lambda x: x[1]['count'], reverse=True)
            result['symptom_clusters'] = []
            for sym, data in sorted_symptoms[:20]:
                result['symptom_clusters'].append({
                    'symptom': sym,
                    'count': data['count'],
                    'top_causes': sorted(data['causes'].items(), key=lambda x: x[1], reverse=True)[:3],
                    'top_solutions': sorted(data['solutions'].items(), key=lambda x: x[1], reverse=True)[:3],
                })

        # Top N 故障原因
        if 'fault_cause' in df.columns:
            fc = df['fault_cause'].value_counts().head(20)
            result['fault_top_n'] = [
                {'cause': str(k), 'count': int(v)}
                for k, v in fc.items() if str(k).strip() and str(k) != 'nan'
            ]

        return result

    def get_fault_cause_trend(self, filters: Optional[dict] = None, top_n: int = 5) -> dict:
        """Top N 故障原因的趋势变化（按周）。"""
        df = self._apply_filters(filters)

        if 'fault_cause' not in df.columns or 'created_week_label' not in df.columns:
            return {'labels': [], 'series': []}

        top_causes = df['fault_cause'].value_counts().head(top_n).index.tolist()

        weeks = sorted(df['created_week_label'].dropna().unique())
        series = []
        for cause in top_causes:
            data = []
            for w in weeks:
                count = len(df[(df['created_week_label'] == w) & (df['fault_cause'] == cause)])
                data.append(count)
            series.append({'name': str(cause), 'data': data})

        return {'labels': weeks, 'series': series}

    def get_symptom_solution_mapping(self, filters: Optional[dict] = None) -> dict:
        """症状→对应解决方案的智能聚类映射。"""
        df = self._apply_filters(filters)

        cluster = defaultdict(lambda: {'solutions': defaultdict(int), 'count': 0, 'avg_resolution_days': 0})
        days_list = defaultdict(list)

        if 'symptom' in df.columns and 'solution' in df.columns:
            for _, row in df.iterrows():
                symptom = str(row.get('symptom', '')).strip()
                if not symptom or symptom == 'nan':
                    continue
                solution = str(row.get('solution', '')).strip()
                if solution and solution != 'nan':
                    cluster[symptom]['solutions'][solution] += 1
                cluster[symptom]['count'] += 1
                if 'resolution_days' in df.columns and pd.notna(row.get('resolution_days')):
                    days_list[symptom].append(row['resolution_days'])

            for sym in cluster:
                if days_list[sym]:
                    cluster[sym]['avg_resolution_days'] = round(sum(days_list[sym]) / len(days_list[sym]), 1)
                cluster[sym]['solutions'] = dict(cluster[sym]['solutions'])

        sorted_clusters = sorted(cluster.items(), key=lambda x: x[1]['count'], reverse=True)
        result = []
        for sym, data in sorted_clusters[:30]:
            result.append({
                'symptom': sym,
                'count': data['count'],
                'avg_resolution_days': data['avg_resolution_days'],
                'top_solutions': sorted(data['solutions'].items(), key=lambda x: x[1], reverse=True)[:5],
            })

        return {'clusters': result, 'total_symptoms': len(cluster)}

    def get_recurring_tickets(self, filters: Optional[dict] = None, min_count: int = 2) -> dict:
        """挖掘重复出现的同类工单：按标题相似度 + 故障原因分组。"""
        df = self._apply_filters(filters)

        result = {'by_fault_group': [], 'by_title_similarity': [], 'summary': {}}

        # 按故障原因分组统计重复
        if 'fault_cause' in df.columns:
            fg_dup = df['fault_cause'].value_counts()
            dup_list = []
            for cause, count in fg_dup.items():
                if count >= min_count and str(cause).strip() and str(cause) != 'nan':
                    sub = df[df['fault_cause'] == cause]
                    dup_list.append({
                        'cause': str(cause),
                        'count': int(count),
                        'pct': round(count / len(df) * 100, 1) if len(df) else 0,
                        'sample_titles': sub['title'].dropna().head(3).tolist() if 'title' in sub.columns else [],
                        'avg_resolution_days': round(sub['resolution_days'].mean(), 1) if 'resolution_days' in sub.columns else 0,
                    })
            dup_list.sort(key=lambda x: x['count'], reverse=True)
            result['by_fault_group'] = dup_list[:20]

        # 按标题关键词分组（简易去重）
        if 'title' in df.columns:
            keyword_counts = defaultdict(list)
            for _, row in df.iterrows():
                title = str(row.get('title', '')).strip()
                if not title or title == 'nan':
                    continue
                # 提取关键短词（2-5个汉字的词组）
                for i in range(len(title) - 1):
                    for j in range(i + 2, min(i + 6, len(title) + 1)):
                        kw = title[i:j]
                        if all('\u4e00' <= c <= '\u9fff' for c in kw):
                            keyword_counts[kw].append(title)

            dup_titles = []
            seen = set()
            for kw, titles in sorted(keyword_counts.items(), key=lambda x: len(x[1]), reverse=True):
                if len(titles) >= min_count and kw not in seen and len(kw) >= 2:
                    # 合并已被包含的关键词
                    superset = any(kw in k for k in seen if k != kw)
                    if not superset:
                        dup_titles.append({
                            'keyword': kw,
                            'count': len(titles),
                            'sample_titles': list(set(titles))[:5],
                        })
                        seen.add(kw)
            dup_titles.sort(key=lambda x: x['count'], reverse=True)
            result['by_title_similarity'] = dup_titles[:15]

        # 汇总
        total_dup = sum(d['count'] for d in result['by_fault_group'][:5])
        result['summary'] = {
            'total_tickets': len(df),
            'top5_dup_count': total_dup,
            'dup_ratio': round(total_dup / len(df) * 100, 1) if len(df) else 0,
        }

        return result

    def get_nature_trend(self, filters: Optional[dict] = None) -> dict:
        """各类性质的占比（饼图）和趋势（堆叠面积图）。"""
        df = self._apply_filters(filters)

        if 'nature' not in df.columns:
            return {'distribution': {'labels': [], 'values': []}, 'trend': {'labels': [], 'series': []}}

        # 占比
        counts = df['nature'].value_counts()
        distribution = {'labels': list(counts.index), 'values': [int(v) for v in counts.values]}

        # 趋势
        if 'created_week_label' in df.columns:
            weeks = sorted(df['created_week_label'].dropna().unique())
            nature_types = counts.head(8).index.tolist()
            series = []
            for nt in nature_types:
                data = []
                for w in weeks:
                    count = len(df[(df['created_week_label'] == w) & (df['nature'] == nt)])
                    data.append(count)
                series.append({'name': str(nt), 'data': data})
            trend = {'labels': weeks, 'series': series}
        else:
            trend = {'labels': [], 'series': []}

        return {'distribution': distribution, 'trend': trend}

    def get_requester_behavior(self, filters: Optional[dict] = None) -> dict:
        """请求人行为与组织分布分析。"""
        df = self._apply_filters(filters)

        result = {}

        # 请求人部门分布
        if 'requester_dept' in df.columns:
            dept = df['requester_dept'].value_counts()
            result['department_distribution'] = {
                'labels': list(dept.index), 'values': [int(v) for v in dept.values],
            }

        # 请求人机构分布
        if 'requester_org' in df.columns:
            org = df['requester_org'].value_counts()
            result['org_distribution'] = {
                'labels': list(org.index), 'values': [int(v) for v in org.values],
            }

        # 高频请求人（提工单最多的人）
        if 'requester' in df.columns:
            req = df['requester'].value_counts().head(20)
            result['top_requesters'] = {
                'labels': list(req.index), 'values': [int(v) for v in req.values],
            }

        # 请求人职务分布
        if 'requester_title' in df.columns:
            title = df['requester_title'].value_counts()
            result['title_distribution'] = {
                'labels': list(title.index), 'values': [int(v) for v in title.values],
            }

        # 部门×性质交叉
        if 'requester_dept' in df.columns and 'nature' in df.columns:
            ct = pd.crosstab(df['requester_dept'], df['nature'])
            dept_names = sorted(ct.index.tolist())
            nature_breakdown = {}
            for n in ct.columns:
                nature_breakdown[str(n)] = {d: int(ct.loc[d, n]) if d in ct.index else 0 for d in dept_names}
            result['dept_nature_cross'] = {
                'departments': dept_names,
                'natures': nature_breakdown,
            }

        # 行为概况
        result['summary'] = {
            'total_requesters': int(df['requester'].nunique()) if 'requester' in df.columns else 0,
            'total_departments': int(df['requester_dept'].nunique()) if 'requester_dept' in df.columns else 0,
            'total_orgs': int(df['requester_org'].nunique()) if 'requester_org' in df.columns else 0,
        }

        return result

    def get_ops_quality_metrics(self, filters: Optional[dict] = None) -> dict:
        """运维质量改进指标：一次解决率、退回率、挂起率、升级率趋势。"""
        df = self._apply_filters(filters)
        total = len(df)

        # 退回服务台率
        returned_count = len(df[df['is_returned'] == '是']) if 'is_returned' in df.columns else 0
        returned_ratio = round(returned_count / total * 100, 1) if total else 0

        # 挂起率
        suspended_count = len(df[df['is_suspended'] == '是']) if 'is_suspended' in df.columns else 0
        suspended_ratio = round(suspended_count / total * 100, 1) if total else 0

        # 撤单率
        cancelled_count = len(df[df['is_cancelled'] == '是']) if 'is_cancelled' in df.columns else 0
        cancelled_ratio = round(cancelled_count / total * 100, 1) if total else 0

        # SLA 达标率
        sla_qualified = len(df[df['sla_percent_num'] <= 100]) if 'sla_percent_num' in df.columns else 0
        sla_ratio = round(sla_qualified / total * 100, 1) if total else 0

        # 平均解决天数
        avg_days = round(df['resolution_days'].mean(), 1) if 'resolution_days' in df.columns else 0

        # 按周趋势
        weekly_metrics = []
        if 'created_week_label' in df.columns:
            for w in sorted(df['created_week_label'].dropna().unique()):
                sub = df[df['created_week_label'] == w]
                s_total = len(sub)
                s_sla = len(sub[sub['sla_percent_num'] <= 100]) if 'sla_percent_num' in sub.columns else 0
                s_returned = len(sub[sub['is_returned'] == '是']) if 'is_returned' in sub.columns else 0
                s_suspended = len(sub[sub['is_suspended'] == '是']) if 'is_suspended' in sub.columns else 0
                weekly_metrics.append({
                    'week': w,
                    'total': s_total,
                    'sla_ratio': round(s_sla / s_total * 100, 1) if s_total else 0,
                    'returned_ratio': round(s_returned / s_total * 100, 1) if s_total else 0,
                    'suspended_ratio': round(s_suspended / s_total * 100, 1) if s_total else 0,
                })

        return {
            'returned_ratio': returned_ratio,
            'returned_count': returned_count,
            'suspended_ratio': suspended_ratio,
            'suspended_count': suspended_count,
            'cancelled_ratio': cancelled_ratio,
            'cancelled_count': cancelled_count,
            'sla_ratio': sla_ratio,
            'avg_resolution_days': avg_days,
            'total': total,
            'weekly_trend': weekly_metrics,
        }

    def generate_insights(self, filters: Optional[dict] = None) -> list[dict]:
        df = self._apply_filters(filters)
        kpis = self.get_summary_kpis(filters)
        insights = []

        # 1. SLA 达标率
        if kpis['sla_ratio'] < 80 and kpis['total'] > 0:
            insights.append({
                'severity': 'critical',
                'title': f'SLA 达标率仅 {kpis["sla_ratio"]}%，低于 80% 警戒线',
                'desc': f'{kpis["total"] - kpis["sla_qualified"]} 件工单未达标，需排查超时原因并优化流程。',
            })
        elif kpis['total'] > 0:
            insights.append({
                'severity': 'info',
                'title': f'SLA 达标率 {kpis["sla_ratio"]}%，平均 SLA {kpis["sla_avg"]}%',
                'desc': f'{kpis["sla_qualified"]}/{kpis["total"]} 件工单达标，保持良好。',
            })

        # 2. 工单解决率
        if 'resolved_ratio' in kpis and kpis['resolved_ratio'] < 70 and kpis['total'] > 0:
            insights.append({
                'severity': 'warning',
                'title': f'工单解决率仅 {kpis["resolved_ratio"]}%，大量工单未关闭',
                'desc': f'{kpis["total"] - kpis["resolved_count"]} 件工单待处理，建议关注待解决工单积压情况。',
            })

        # 3. 平均解决天数
        if kpis['avg_resolution_days'] > 7:
            insights.append({
                'severity': 'warning',
                'title': f'平均解决时间 {kpis["avg_resolution_days"]} 天，超过一周',
                'desc': '建议分析长周期工单的原因，优化处理流程。',
            })

        # 4. 挂起工单
        if kpis['suspended_ratio'] > 10:
            insights.append({
                'severity': 'warning',
                'title': f'挂起工单占比 {kpis["suspended_ratio"]}%，共 {kpis["suspended_count"]} 件',
                'desc': '挂起工单需关注挂起原因，避免长期无人跟进。',
            })

        # 5. 退回服务台
        if kpis['returned_count'] > 0 and kpis['total'] > 0:
            returned_ratio = round(kpis['returned_count'] / kpis['total'] * 100, 1)
            if returned_ratio > 5:
                insights.append({
                    'severity': 'warning',
                    'title': f'{kpis["returned_count"]} 件工单退回服务台（{returned_ratio}%）',
                    'desc': '退回率偏高，可能需要加强一线人员培训和知识库建设。',
                })

        # 6. 评价参与率
        if kpis['evaluated_count'] > 0:
            if kpis['evaluated_ratio'] < 30:
                insights.append({
                    'severity': 'info',
                    'title': f'评价参与率仅 {kpis["evaluated_ratio"]}%，用户反馈不足',
                    'desc': '建议在工单关闭时增加评价提醒，提升评价覆盖率。',
                })
        else:
            insights.append({
                'severity': 'info',
                'title': '暂无用户评价数据',
                'desc': '当前无已评价工单，无法评估服务质量。建议引导用户完成评价。',
            })

        # 7. 服务组工作量
        sg_dist = self.get_service_group_distribution(filters)
        if sg_dist['labels']:
            top_sg = sg_dist['labels'][0]
            top_sg_val = sg_dist['values'][0]
            pct = round(top_sg_val / kpis['total'] * 100, 1)
            insights.append({
                'severity': 'info',
                'title': f'"{top_sg}" 服务组工单量最高，共 {top_sg_val} 件（{pct}%）',
                'desc': '建议评估该组资源与负载是否匹配。',
            })

        # 8. 重复工单挖掘
        try:
            recurring = self.get_recurring_tickets(filters)
            if recurring['by_fault_group']:
                top_dup = recurring['by_fault_group'][0]
                if top_dup['count'] >= 3:
                    insights.append({
                        'severity': 'critical',
                        'title': f'重复工单预警：「{top_dup["cause"]}」出现 {top_dup["count"]} 次（{top_dup["pct"]}%）',
                        'desc': f'该故障原因重复出现 {top_dup["count"]} 次，疑似根本问题未解决。建议建立已知问题库(KEDB)，推动根本解决方案。示例工单：{", ".join(top_dup.get("sample_titles", [])[:2])}',
                    })
            if recurring['summary'].get('dup_ratio', 0) > 30:
                insights.append({
                    'severity': 'warning',
                    'title': f'Top5 重复故障占 {recurring["summary"]["dup_ratio"]}%，重复率偏高',
                    'desc': '大量工单集中在少数几类问题上，推动根本解决可大幅降低工单量。',
                })
        except Exception:
            pass

        # 9. 请求人行为与组织分布
        try:
            behavior = self.get_requester_behavior(filters)
            if behavior.get('top_requesters') and behavior['top_requesters']['values']:
                top_req = behavior['top_requesters']['labels'][0]
                top_req_count = behavior['top_requesters']['values'][0]
                req_pct = round(top_req_count / kpis['total'] * 100, 1)
                if req_pct > 15:
                    insights.append({
                        'severity': 'warning',
                        'title': f'高频请求人「{top_req}」提交了 {top_req_count} 件工单（{req_pct}%）',
                        'desc': f'单个用户占比过高，建议排查是否存在系统故障反复上报、或通过自助服务/培训降低重复报修。',
                    })
            if behavior.get('summary', {}).get('total_orgs', 0) > 10:
                insights.append({
                    'severity': 'info',
                    'title': f'工单覆盖 {behavior["summary"]["total_departments"]} 个部门、{behavior["summary"]["total_orgs"]} 个机构',
                    'desc': f'共 {behavior["summary"]["total_requesters"]} 个不同请求人，组织覆盖广泛。',
                })
        except Exception:
            pass

        # 10. 运维质量指标
        try:
            ops = self.get_ops_quality_metrics(filters)
            if ops['returned_ratio'] > 10 and ops['total'] > 0:
                insights.append({
                    'severity': 'warning',
                    'title': f'退回率 {ops["returned_ratio"]}%（{ops["returned_count"]}件），挂起率 {ops["suspended_ratio"]}%',
                    'desc': '退回率和挂起率偏高反映一线处理能力或知识库建设不足。建议加强培训和FAQ完善。',
                })
            if ops['cancelled_ratio'] > 5:
                insights.append({
                    'severity': 'info',
                    'title': f'撤单率 {ops["cancelled_ratio"]}%（{ops["cancelled_count"]}件）',
                    'desc': '关注撤单原因——用户自行解决还是重复提交？优化工单提交引导可减少撤单。',
                })
        except Exception:
            pass

        # 11. 故障根因深度分析
        try:
            root_cause = self.get_fault_root_cause_analysis(filters)
            if root_cause.get('fault_top_n'):
                top_fault = root_cause['fault_top_n'][0]
                insights.append({
                    'severity': 'critical',
                    'title': f'TOP 故障根因：「{top_fault["cause"]}」发生 {top_fault["count"]} 次，占比最高',
                    'desc': '建议对该故障建立专项复盘：分析根本原因、评估是否可自动修复、制定标准化SOP减少重复。',
                })
            if root_cause.get('symptom_clusters'):
                top_symptom = root_cause['symptom_clusters'][0]
                cause_str = ', '.join([f'"{c[0]}"({c[1]}次)' for c in top_symptom.get('top_causes', [])[:2]])
                insights.append({
                    'severity': 'info',
                    'title': f'高频症状聚类：「{top_symptom["symptom"]}」发生 {top_symptom["count"]} 次',
                    'desc': f'关联根因: {cause_str}。建议对该症状建立快速诊断手册。',
                })
        except Exception:
            pass

        return insights


# ============================================================
# 多数据源处理器管理器
# ============================================================

class TicketProcessorManager:
    """多数据源处理器管理器，替代全局单例。

    管理多个 TicketProcessor 实例，每个对应一个 datasource_id。
    支持设置 primary（默认查询的数据源）。
    """

    def __init__(self):
        self._processors: dict[int, TicketProcessor] = {}
        self._primary_id: Optional[int] = None
        self._file_paths: dict[int, str] = {}

    def register(self, datasource_id: int, file_path: str, field_mapping: dict = None) -> TicketProcessor:
        """注册一个新数据源的处理器。"""
        processor = TicketProcessor(file_path, custom_col_map=field_mapping)
        _ = processor.df  # 触发加载
        self._processors[datasource_id] = processor
        self._file_paths[datasource_id] = file_path

        # 如果是第一个注册的，自动设为 primary
        if self._primary_id is None:
            self._primary_id = datasource_id

        return processor

    def get(self, datasource_id: int) -> Optional[TicketProcessor]:
        """获取指定数据源的处理器。"""
        if datasource_id is None:
            return self.get_primary()
        return self._processors.get(datasource_id)

    def get_primary(self) -> Optional[TicketProcessor]:
        """获取当前主要数据源的处理器。"""
        if self._primary_id is not None:
            return self._processors.get(self._primary_id)
        # 兜底：返回第一个
        if self._processors:
            first_id = next(iter(self._processors))
            self._primary_id = first_id
            return self._processors[first_id]
        return None

    def get_primary_id(self) -> Optional[int]:
        """获取当前主要数据源 ID。"""
        return self._primary_id

    def set_primary(self, datasource_id: int) -> bool:
        """设置主要数据源。"""
        if datasource_id in self._processors:
            self._primary_id = datasource_id
            return True
        return False

    def list_ids(self) -> list[int]:
        """列出所有已注册的数据源 ID。"""
        return list(self._processors.keys())

    def list_datasources_info(self) -> list[dict]:
        """列出所有数据源的摘要信息。"""
        result = []
        for ds_id, proc in self._processors.items():
            try:
                total = len(proc.df)
            except Exception:
                total = 0
            result.append({
                "datasource_id": ds_id,
                "record_count": total,
                "is_primary": ds_id == self._primary_id,
                "file_path": self._file_paths.get(ds_id, ""),
            })
        return result

    def remove(self, datasource_id: int):
        """移除一个数据源的处理器。"""
        self._processors.pop(datasource_id, None)
        self._file_paths.pop(datasource_id, None)
        if self._primary_id == datasource_id:
            # 切换到其他可用的数据源
            if self._processors:
                self._primary_id = next(iter(self._processors))
            else:
                self._primary_id = None

    def has_datasource(self, datasource_id: int) -> bool:
        """检查数据源是否已注册。"""
        return datasource_id in self._processors
