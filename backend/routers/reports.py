"""报表管理路由。"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models import User, Report
from backend.schemas import ReportOut, ReportDetail
from backend.services.export_service import export_html, export_excel
from backend.services.complaint_processor import ComplaintProcessor

router = APIRouter()

_processor: Optional[ComplaintProcessor] = None


def get_processor() -> ComplaintProcessor:
    return _processor


def set_processor(p: ComplaintProcessor):
    global _processor
    _processor = p


@router.get("", response_model=dict)
async def get_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """报表列表（分页、搜索）。"""
    query = select(Report).where(Report.user_id == user.id)
    count_query = select(func.count()).select_from(Report).where(Report.user_id == user.id)

    if search:
        query = query.where(Report.title.contains(search))
        count_query = count_query.where(Report.title.contains(search))

    # 管理员看全部
    if user.role == "admin":
        query = select(Report)
        count_query = select(func.count()).select_from(Report)
        if search:
            query = query.where(Report.title.contains(search))
            count_query = count_query.where(Report.title.contains(search))

    total = (await db.execute(count_query)).scalar()
    query = query.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    reports = (await db.execute(query)).scalars().all()

    return {
        'items': [
            {
                'id': r.id, 'title': r.title, 'report_type': r.report_type,
                'created_at': r.created_at,
            }
            for r in reports
        ],
        'total': total,
        'page': page,
        'page_size': page_size,
    }


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """报表详情。"""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")
    if report.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")
    return report


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除报表。"""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")
    if report.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权删除")
    await db.delete(report)
    await db.commit()
    return {"message": "报表已删除"}


@router.get("/{report_id}/export/html")
async def export_report_html(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出 HTML 报告。"""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")
    if report.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权导出")

    charts = json.loads(report.chart_config or '[]')
    insights = json.loads(report.insights or '[]')
    data_table = json.loads(report.data_payload or '{}')
    kpis = get_processor().get_summary_kpis()

    html_bytes = export_html(
        title=report.title or '报表',
        charts=charts,
        insights=insights,
        data_table=data_table,
        total=kpis['total'],
    )
    return Response(
        content=html_bytes,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{report.title or "report"}.html"'},
    )


@router.get("/{report_id}/export/excel")
async def export_report_excel(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出 Excel 报告。"""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")
    if report.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权导出")

    data_table = json.loads(report.data_payload or '{}')
    insights = json.loads(report.insights or '[]')
    kpis = get_processor().get_summary_kpis()

    excel_bytes = export_excel(
        title=report.title or '报表',
        data_table=data_table,
        kpis=kpis,
        insights=insights,
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{report.title or "report"}.xlsx"'},
    )
