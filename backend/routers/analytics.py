"""数据分析路由 — 工单分析版本。支持多数据源。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_current_user
from backend.models import User
from backend.services.ticket_processor import TicketProcessor, TicketProcessorManager
from backend.utils import convert_numpy

router = APIRouter()

# 向后兼容：单处理器模式
_processor: Optional[TicketProcessor] = None
# 新模式：多数据源管理器
_processor_manager: Optional[TicketProcessorManager] = None


def get_processor(datasource_id: int = None) -> Optional[TicketProcessor]:
    """获取处理器。优先使用 manager，否则使用单例。"""
    if _processor_manager:
        if datasource_id is not None:
            return _processor_manager.get(datasource_id)
        return _processor_manager.get_primary()
    return _processor


def set_processor(p: TicketProcessor):
    global _processor
    _processor = p


def set_processor_manager(mgr: TicketProcessorManager):
    global _processor_manager
    _processor_manager = mgr


@router.get("/summary")
async def get_summary(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {}
    return convert_numpy(p.get_summary_kpis())


@router.get("/status")
async def get_status(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_status_distribution())


@router.get("/service-groups")
async def get_service_groups(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_service_group_distribution())


@router.get("/assignees")
async def get_assignees(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_assignee_distribution())


@router.get("/departments")
async def get_departments(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_department_distribution())


@router.get("/source-channels")
async def get_source_channels(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_source_channel_distribution())


@router.get("/fault-groups")
async def get_fault_groups(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_fault_group_distribution())


@router.get("/weekly-trend")
async def get_weekly_trend(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_weekly_trend())


@router.get("/monthly-trend")
async def get_monthly_trend(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {'labels': [], 'values': []}
    return convert_numpy(p.get_monthly_trend())


@router.get("/evaluation")
async def get_evaluation(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return {}
    return convert_numpy(p.get_evaluation_summary())


@router.get("/insights")
async def get_insights(
    datasource_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    p = get_processor(datasource_id)
    if not p:
        return []
    return convert_numpy(p.generate_insights())
