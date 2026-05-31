"""数据分析路由 — 工单分析版本。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_current_user
from backend.models import User
from backend.services.ticket_processor import TicketProcessor
from backend.utils import convert_numpy

router = APIRouter()

_processor: Optional[TicketProcessor] = None


def get_processor() -> TicketProcessor:
    return _processor


def set_processor(p: TicketProcessor):
    global _processor
    _processor = p


@router.get("/summary")
async def get_summary(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {}
    return convert_numpy(p.get_summary_kpis())


@router.get("/status")
async def get_status(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_status_distribution())


@router.get("/service-groups")
async def get_service_groups(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_service_group_distribution())


@router.get("/assignees")
async def get_assignees(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_assignee_distribution())


@router.get("/departments")
async def get_departments(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_department_distribution())


@router.get("/source-channels")
async def get_source_channels(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_source_channel_distribution())


@router.get("/fault-groups")
async def get_fault_groups(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_fault_group_distribution())


@router.get("/weekly-trend")
async def get_weekly_trend(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_weekly_trend())


@router.get("/monthly-trend")
async def get_monthly_trend(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_monthly_trend())


@router.get("/evaluation")
async def get_evaluation(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return {}
    return convert_numpy(p.get_evaluation_summary())


@router.get("/insights")
async def get_insights(user: User = Depends(get_current_user)):
    p = get_processor()
    if not p:
        return []
    return convert_numpy(p.generate_insights())
