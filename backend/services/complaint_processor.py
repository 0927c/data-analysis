"""客诉数据处理服务 — 封装客诉.md 的 46 条正则规则为可复用类。"""

import re
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd


# ============================================================
# 46 条原因分类规则（从客诉.md 直接迁移）
# ============================================================
CAUSE_RULES = [
    # 制造-工艺类
    (r'封口不良|缝包|缝线|M口破裂|自动缝包机|手动缝包机', '封口/缝包工艺问题'),
    (r'配色|混色|色粉|炭黑分散|在线混色|离线混色', '配色/混色不均'),
    (r'清机不干[净洁]|料皮残留|残留未清|上单.*污染|深色材料污染|隔离不[彻干净]|隔离不彻底|混料段回收', '清机/换料不彻底'),
    (r'碳化|烧焦|过热', '碳化/过热'),
    (r'塑化不良|密炼|混炼不均', '塑化/混炼不良'),
    (r'放料|降温|结块|料温', '放料/温控异常'),
    (r'计量秤.*跳|比例问题|计量异常', '计量/配料异常'),
    (r'开机波动|开机不稳|生产不稳定', '开机工艺波动'),
    (r'切粒|粒子形状|粒子大小|磨面', '切粒/磨面异常'),
    (r'工艺校称|工艺.*调整|工艺参数', '工艺参数异常'),
    (r'振动筛|喷粉|往复机', '工艺设备异常'),
    (r'设备故障|机台.*老旧|装备升级|漏水|密炼机漏', '设备故障/老化'),
    (r'滤网|杂质引入|异物引入|异物', '杂质/异物引入'),
    (r'流程.*失效|进仓|流程节点', '流程管控失效'),

    # 研发类
    (r'配方.*变更|配方.*更换|树脂更换|树脂替代|稳定剂替换|新配方|配方中加', '配方变更/替换'),
    (r'开发.*标准.*未明确|开发过程|产品设计', '开发标准未明确'),
    (r'材料.*不稳定|无法稳定生产|量产.*不稳定', '材料开发不稳定'),
    (r'配方不固定|没有明确.*上下限', '配方/标准不固定'),
    (r'耐刮差剂|添加剂|组分', '添加剂/配方设计问题'),

    # 客户类
    (r'测试方法.*不一致|测试标准.*不一致|客户.*测试|测试仪器|复测.*合格|重新制样', '客户测试方法差异'),
    (r'客户.*温度偏差|客户.*设备|客户端.*调整|客户现场调整', '客户加工参数不当'),
    (r'客户加工|客户成型|加工过程.*碳化|加工过程.*异物', '客户加工工艺问题'),
    (r'客户.*标准.*严苛|管控标准.*严苛', '客户标准严苛'),
    (r'沟通.*问题|双方.*沟通|确认时沟通|标准.*偏差', '双方标准沟通不足'),
    (r'制件厚度|半透材料|厚度不一', '材料特性与工艺不匹配'),

    # 仓储类
    (r'标签.*贴[反错]|贴错.*标签|贴反', '标签贴错'),
    (r'窜包|串包|用错包装袋|包装袋.*错', '窜包/用错包装'),
    (r'破包|M口破裂|包装破损', '包装破损'),
    (r'缠膜|打托|纸盖|包装防护|包装方案', '包装防护不足'),
    (r'地台板断裂|地台板.*型号|歪板', '地台板问题'),
    (r'发货.*错误|发错|错发', '发货错误'),
    (r'订单延误|延误|未按时', '订单延误'),
    (r'取样|抽样|样条|COA|随货|送货单|喷码|声明函', '标识/随货资料错误'),
    (r'淋湿|明水|受潮|水分', '受潮/淋湿'),
    (r'先进先出|FIFO', '先进先出管理'),
    (r'重量不符|少重|称重', '重量不符'),

    # 原料类
    (r'原料|YBL|原料问题', '原料异常'),
    (r'色板.*变[色黄]|色板放置变色|随货色板.*黄|色板.*变色', '色板老化/变色'),
]

# 提取原因 → 原因大类 映射
CAUSE_CATEGORY_MAP = {
    # 制造原因
    '封口/缝包工艺问题': '制造原因',
    '配色/混色不均': '制造原因',
    '清机/换料不彻底': '制造原因',
    '碳化/过热': '制造原因',
    '塑化/混炼不良': '制造原因',
    '放料/温控异常': '制造原因',
    '计量/配料异常': '制造原因',
    '开机工艺波动': '制造原因',
    '切粒/磨面异常': '制造原因',
    '工艺参数异常': '制造原因',
    '工艺设备异常': '制造原因',
    '设备故障/老化': '制造原因',
    '杂质/异物引入': '制造原因',
    '流程管控失效': '制造原因',
    # 研发原因
    '配方变更/替换': '研发原因',
    '开发标准未明确': '研发原因',
    '材料开发不稳定': '研发原因',
    '配方/标准不固定': '研发原因',
    '添加剂/配方设计问题': '研发原因',
    # 客户原因
    '客户测试方法差异': '客户原因',
    '客户加工参数不当': '客户原因',
    '客户加工工艺问题': '客户原因',
    '客户标准严苛': '客户原因',
    '双方标准沟通不足': '客户原因',
    '材料特性与工艺不匹配': '客户原因',
    # 仓储原因
    '标签贴错': '仓储原因',
    '窜包/用错包装': '仓储原因',
    '包装破损': '仓储原因',
    '包装防护不足': '仓储原因',
    '地台板问题': '仓储原因',
    '发货错误': '仓储原因',
    '订单延误': '仓储原因',
    '标识/随货资料错误': '仓储原因',
    '受潮/淋湿': '仓储原因',
    '先进先出管理': '仓储原因',
    '重量不符': '仓储原因',
    # 原料原因
    '原料异常': '原料原因',
    '色板老化/变色': '原料原因',
    # 兜底
    '未调查/无结论': '原因不明',
    '已关闭/归档': '原因不明',
    '客户原因(待细查)': '客户原因',
    '原因待确认': '原因不明',
    '内部合格/客户仍投诉': '原因不明',
    '其他/原因不明': '原因不明',
}


def _extract_cause(text: str) -> str:
    """从初步调查文本中提取单个原因（从客诉.md 直接迁移）。"""
    if pd.isna(text) or str(text).strip() in ['', 'nan', '/', '该客诉已关闭']:
        return '未调查/无结论'
    text = str(text)
    for pattern, cause_name in CAUSE_RULES:
        if re.search(pattern, text):
            return cause_name
    # 兜底分类
    if '已关闭' in text or '归档' in text:
        return '已关闭/归档'
    if '客户' in text and ('异常' in text or '问题' in text or '确认' in text):
        return '客户原因(待细查)'
    if '待' in text and ('确认' in text or '排查' in text or '调查' in text):
        return '原因待确认'
    if '无异常' in text or '合格' in text or '满足' in text:
        return '内部合格/客户仍投诉'
    return '其他/原因不明'


# ============================================================
# ComplaintProcessor 服务类
# ============================================================
class ComplaintProcessor:
    """客诉数据处理服务。从 Excel 读取数据、分类原因、提供各维度统计分析。"""

    # 大客户体系关键词
    KEY_CUSTOMERS = [
        '格力', '利盟', '广汽丰田', '美的', '松下', '比亚迪汽车', '博世',
        '奇瑞汽车', '华为', '比亚迪十一事业部', '兄弟工业', '敏实',
        '小米汽车', '海康',
    ]

    def __init__(self, excel_path: str):
        self.excel_path = Path(excel_path)
        self._df: pd.DataFrame | None = None
        self._key_customer_col: str | None = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._load()
        return self._df

    def _load(self):
        """加载 Excel 并执行原因分类。"""
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel 文件不存在: {self.excel_path}")

        self._df = pd.read_excel(self.excel_path, sheet_name='Sheet1')

        # 检查是否有大客户体系列
        for col_name in ['大客户体系', '大客户', 'key_customer']:
            if col_name in self._df.columns:
                self._key_customer_col = col_name
                break

        # 执行原因提取
        self._df['提取原因'] = self._df['初步调查'].apply(_extract_cause)
        self._df['原因大类'] = self._df['提取原因'].map(CAUSE_CATEGORY_MAP).fillna('原因不明')

    def _apply_filters(self, filters: Optional[dict] = None) -> pd.DataFrame:
        """根据筛选条件返回子集 DataFrame。"""
        df = self.df
        if not filters:
            return df

        filtered = df.copy()
        if filters.get('product_line'):
            filtered = filtered[filtered['产品线'] == filters['product_line']]
        if filters.get('cause_category'):
            filtered = filtered[filtered['原因大类'] == filters['cause_category']]
        if filters.get('defect_type'):
            filtered = filtered[filtered['二级不良'] == filters['defect_type']]
        return filtered

    def _detect_key_customers(self, df: pd.DataFrame) -> pd.Series:
        """从初步调查文本中检测大客户关键词。"""
        if self._key_customer_col:
            return df[self._key_customer_col]

        def detect(text):
            if pd.isna(text):
                return None
            t = str(text)
            for cust in self.KEY_CUSTOMERS:
                if cust in t:
                    return cust
            return None

        return df['初步调查'].apply(detect)

    # ===== 数据分析方法 =====

    def get_product_line_distribution(self, filters: Optional[dict] = None) -> dict:
        """产品线投诉分布（横向柱状图数据）。"""
        df = self._apply_filters(filters)
        counts = df['产品线'].value_counts().sort_index()
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_root_cause_distribution(self, filters: Optional[dict] = None) -> dict:
        """原因大类分布（饼图数据）。"""
        df = self._apply_filters(filters)
        counts = df['原因大类'].value_counts()
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_defect_top15(self, filters: Optional[dict] = None, top_n: int = 15) -> dict:
        """二级不良类型 TOP N。"""
        df = self._apply_filters(filters)
        counts = df['二级不良'].value_counts().head(top_n)
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_cross_table(self, filters: Optional[dict] = None) -> dict:
        """产品线 × 原因大类 交叉表（堆叠柱状图数据）。"""
        df = self._apply_filters(filters)
        ct = pd.crosstab(df['产品线'], df['原因大类'])
        products = sorted(ct.index.tolist())
        causes = {}
        for cause in ct.columns:
            causes[cause] = {p: int(ct.loc[p, cause]) if p in ct.index else 0 for p in products}
        return {'products': products, 'causes': causes}

    def get_key_customers(self, filters: Optional[dict] = None, top_n: int = 14) -> dict:
        """大客户投诉排名。"""
        df = self._apply_filters(filters)
        customers = self._detect_key_customers(df)
        customers = customers.dropna()
        counts = customers.value_counts().head(top_n)
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_mfg_defect_breakdown(self, filters: Optional[dict] = None) -> dict:
        """制造原因下的二级不良类型细分。"""
        df = self._apply_filters(filters)
        mfg = df[df['原因大类'] == '制造原因']
        counts = mfg['二级不良'].value_counts().head(10)
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_rnd_defect_breakdown(self, filters: Optional[dict] = None) -> dict:
        """研发原因下的二级不良类型细分。"""
        df = self._apply_filters(filters)
        rnd = df[df['原因大类'] == '研发原因']
        counts = rnd['二级不良'].value_counts().head(10)
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_cli_defect_breakdown(self, filters: Optional[dict] = None) -> dict:
        """客户原因下的二级不良类型细分。"""
        df = self._apply_filters(filters)
        cli = df[df['原因大类'] == '客户原因']
        counts = cli['二级不良'].value_counts().head(10)
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_wh_defect_breakdown(self, filters: Optional[dict] = None) -> dict:
        """仓储原因下的二级不良类型细分。"""
        df = self._apply_filters(filters)
        wh = df[df['原因大类'] == '仓储原因']
        counts = wh['二级不良'].value_counts().head(10)
        return {'labels': list(counts.index), 'values': list(counts.values)}

    def get_summary_kpis(self, filters: Optional[dict] = None) -> dict:
        """KPI 汇总。"""
        df = self._apply_filters(filters)
        total = len(df)

        unknown_count = len(df[df['原因大类'] == '原因不明'])
        unknown_ratio = round(unknown_count / total * 100, 1) if total else 0

        defect_counts = df['二级不良'].value_counts()
        top_defect = defect_counts.index[0] if len(defect_counts) else 'N/A'
        top_defect_count = int(defect_counts.iloc[0]) if len(defect_counts) else 0

        customers = self._detect_key_customers(df).dropna()
        key_customer_count = len(customers)

        product_line_count = df['产品线'].nunique()

        return {
            'total': total,
            'product_line_count': product_line_count,
            'unknown_count': unknown_count,
            'unknown_ratio': unknown_ratio,
            'top_defect': top_defect,
            'top_defect_count': top_defect_count,
            'key_customer_count': key_customer_count,
            'key_customer_ratio': round(key_customer_count / total * 100, 1) if total else 0,
        }

    def generate_insights(self, filters: Optional[dict] = None) -> list[dict]:
        """基于规则生成洞察卡片（severity + title + desc）。"""
        df = self._apply_filters(filters)
        kpis = self.get_summary_kpis(filters)
        insights = []

        # 洞察 1: 产品线投诉量最高
        pl_dist = self.get_product_line_distribution(filters)
        if pl_dist['labels']:
            top_pl = pl_dist['labels'][0]
            top_pl_val = pl_dist['values'][0]
            pct = round(top_pl_val / kpis['total'] * 100, 1)
            insights.append({
                'severity': 'critical',
                'title': f'{top_pl}产品线投诉量最高达{top_pl_val}件，占比{pct}%，远超其他产品线',
                'desc': f'{top_pl}产品线在各类原因中均占较高比例，需立即启动专项整改。',
            })

        # 洞察 2: 原因不明占比
        if kpis['unknown_ratio'] > 15:
            insights.append({
                'severity': 'critical',
                'title': f'{kpis["unknown_ratio"]}%的投诉原因不明，根因追踪能力不足',
                'desc': f'{kpis["unknown_count"]}件投诉无法确认根因，建议建立"投诉-调查-根因"闭环机制。',
            })

        # 洞察 3: TOP 缺陷
        insights.append({
            'severity': 'warning',
            'title': f'"{kpis["top_defect"]}"为最突出质量问题，共{kpis["top_defect_count"]}件',
            'desc': f'{kpis["top_defect"]}跨多条产品线出现，属于系统性问题，需从配方体系、色母管控、检测标准等层面统筹解决。',
        })

        # 洞察 4: 制造+仓储内部可控
        mfg = len(df[df['原因大类'] == '制造原因'])
        wh = len(df[df['原因大类'] == '仓储原因'])
        internal_pct = round((mfg + wh) / kpis['total'] * 100, 1)
        insights.append({
            'severity': 'warning',
            'title': f'制造原因({mfg}件)和仓储原因({wh}件)合计占{internal_pct}%，属内部可控范围',
            'desc': '这两类原因完全可通过内部管理改善，投入产出比高。',
        })

        # 洞察 5: 大客户标记缺失
        customer_ratio = kpis['key_customer_ratio']
        if customer_ratio < 30:
            missing = kpis['total'] - kpis['key_customer_count']
            insights.append({
                'severity': 'info',
                'title': f'大客户体系标记缺失率高达{round(100 - customer_ratio, 1)}%',
                'desc': f'仅{kpis["key_customer_count"]}条投诉标注了大客户体系（占{customer_ratio}%），{missing}条缺失。建议完善大客户标记，便于分级响应和VIP客户满意度管理。',
            })

        return insights
