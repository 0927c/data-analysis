"""数据分析路由 — 对应 report.html 的 7 张图表数据。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_current_user
from backend.models import User
from backend.services.complaint_processor import ComplaintProcessor
from backend.utils import convert_numpy

router = APIRouter()

# Global processor instance (set in main.py)
_processor: Optional[ComplaintProcessor] = None


def get_processor() -> ComplaintProcessor:
    return _processor


def set_processor(p: ComplaintProcessor):
    global _processor
    _processor = p


@router.get("/summary")
async def get_summary(user: User = Depends(get_current_user)):
    """KPI 汇总。"""
    p = get_processor()
    if not p:
        return {}
    return convert_numpy(p.get_summary_kpis())


@router.get("/product-lines")
async def get_product_lines(user: User = Depends(get_current_user)):
    """产品线分布。"""
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_product_line_distribution())


@router.get("/root-causes")
async def get_root_causes(user: User = Depends(get_current_user)):
    """原因大类分布。"""
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_root_cause_distribution())


@router.get("/defects/top15")
async def get_defects_top15(user: User = Depends(get_current_user)):
    """不良类型 TOP15。"""
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_defect_top15())


@router.get("/cross-table")
async def get_cross_table(user: User = Depends(get_current_user)):
    """产品线 × 原因交叉表。"""
    p = get_processor()
    if not p:
        return {'products': [], 'causes': {}}
    return convert_numpy(p.get_cross_table())


@router.get("/key-customers")
async def get_key_customers(user: User = Depends(get_current_user)):
    """大客户排名。"""
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_key_customers())


@router.get("/mfg-defects")
async def get_mfg_defects(user: User = Depends(get_current_user)):
    """制造原因细分。"""
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_mfg_defect_breakdown())


@router.get("/rnd-defects")
async def get_rnd_defects(user: User = Depends(get_current_user)):
    """研发原因细分。"""
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_rnd_defect_breakdown())


@router.get("/insights")
async def get_insights(user: User = Depends(get_current_user)):
    """洞察建议。"""
    p = get_processor()
    if not p:
        return []
    return convert_numpy(p.generate_insights())
