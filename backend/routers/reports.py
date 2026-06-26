"""报表管理路由。"""

import json
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models import User, Report
from backend.schemas import ReportOut, ReportDetail
from backend.services.export_service import export_html, export_excel
from backend.services.ticket_processor import TicketProcessor, TicketProcessorManager

router = APIRouter()

_processor: Optional[TicketProcessor] = None
_processor_manager: Optional[TicketProcessorManager] = None


def get_processor() -> TicketProcessor:
    return _processor


def set_processor(p: TicketProcessor):
    global _processor
    _processor = p


def set_processor_manager(pm: TicketProcessorManager):
    global _processor_manager
    _processor_manager = pm


def _get_active_processor() -> Optional[TicketProcessor]:
    """获取当前活跃的 processor（manager 优先）。"""
    if _processor_manager:
        return _processor_manager.get_primary() or _processor
    return _processor


# chart_id → DataFrame 列名映射（用于下钻）
CHART_DIM_MAP = {
    'chart_status': 'status',
    'chart_sg': 'service_group',
    'chart_service_group': 'service_group',
    'chart_assignee': 'responsible_person',
    'chart_dept': 'requester_dept',
    'chart_source': 'source',
    'chart_source_channel': 'source_channel',
    'chart_fault': 'fault_group',
    'chart_cause': 'cause_category',
    'chart_sys': 'business_system',
    'chart_business_system': 'business_system',
    'chart_resolver': 'resolver',
    'chart_weekly': 'created_week_label',
    'chart_monthly': 'created_month',
    'chart_sla_trend': 'created_week_label',
    'chart_res_time': None,  # 数值区间，无法直接过滤
    'chart_suspended': 'suspend_reason',
    'chart_cross': 'service_group',
    'chart_root_cause': 'fault_cause',
    'chart_recurring': 'fault_group',
    'chart_ops': None,
    'chart_symptom': 'symptom',
    'chart_requester': 'requester',
    'chart_req_dept': 'requester_dept',
    'chart_org': 'requester_org',
    'chart_nature_pie': 'nature',
    'chart_nature_trend': 'nature',
}

# 下钻时返回的关键列
DRILL_COLUMNS = [
    'ticket_id', 'title', 'status', 'service_group', 'business_system',
    'fault_group', 'fault_cause', 'requester', 'requester_dept', 'requester_org',
    'responsible_person', 'resolver', 'created_at', 'resolved_at',
    'source_channel', 'nature', 'sla_percent', 'is_suspended',
    'is_returned', 'is_cancelled', 'symptom', 'solution',
]


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

    items = []
    for r in reports:
        # 从 chart_config JSON 数组计算图表数量
        chart_count = 0
        if r.chart_config:
            try:
                chart_count = len(json.loads(r.chart_config))
            except (json.JSONDecodeError, TypeError):
                chart_count = 0
        items.append({
            'id': r.id, 'title': r.title, 'report_type': r.report_type,
            'created_at': r.created_at, 'chart_count': chart_count,
        })

    return {
        'items': items,
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
    try:
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail="报表不存在")
        if report.user_id != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="无权导出")

        charts = json.loads(report.chart_config or '[]')
        insights = json.loads(report.insights or '[]')
        data_table = json.loads(report.data_payload or '{}')
        proc = get_processor()
        kpis = proc.get_summary_kpis() if proc else {'total': 0}

        html_bytes = export_html(
            title=report.title or '报表',
            charts=charts,
            insights=insights,
            data_table=data_table,
            total=kpis.get('total', 0),
        )
        filename = quote(report.title or 'report', safe='')
        return Response(
            content=html_bytes,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}.html"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'HTML 导出失败: {e}')


@router.get("/{report_id}/export/excel")
async def export_report_excel(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出 Excel 报告。"""
    try:
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail="报表不存在")
        if report.user_id != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="无权导出")

        data_table = json.loads(report.data_payload or '{}')
        insights = json.loads(report.insights or '[]')
        proc = get_processor()
        kpis = proc.get_summary_kpis() if proc else {
            'total': 0, 'product_line_count': 0, 'unknown_count': 0,
            'unknown_ratio': 0, 'top_defect': 'N/A', 'top_defect_count': 0,
            'key_customer_count': 0, 'key_customer_ratio': 0,
        }

        excel_bytes = export_excel(
            title=report.title or '报表',
            data_table=data_table,
            kpis=kpis,
            insights=insights,
        )
        filename = quote(report.title or 'report', safe='')
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Excel 导出失败: {e}')


@router.get("/{report_id}/drill-down")
async def drill_down(
    report_id: int,
    chart_id: str = Query(..., description="图表ID"),
    value: str = Query(..., description="点击的分类值"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """图表下钻：点击某个柱子/扇区，返回对应的原始工单明细。"""
    import pandas as pd

    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")
    if report.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")

    proc = _get_active_processor()
    if not proc:
        raise HTTPException(status_code=503, detail="数据源不可用")

    col = CHART_DIM_MAP.get(chart_id)
    if not col:
        col = chart_id.replace("chart_", "")

    if col not in proc.df.columns:
        raise HTTPException(status_code=400, detail=f"无法下钻: 列 '{col}' 不存在")

    filtered = proc.df[proc.df[col].astype(str).str.contains(value, na=False, case=False)]
    total = len(filtered)

    available_cols = [c for c in DRILL_COLUMNS if c in filtered.columns]
    page_df = filtered[available_cols].iloc[(page - 1) * page_size: page * page_size]

    col_labels = {
        "ticket_id": "工单编号", "title": "标题", "status": "状态",
        "service_group": "服务组", "business_system": "业务系统",
        "fault_group": "故障分组", "fault_cause": "故障原因",
        "requester": "请求人", "requester_dept": "请求部门", "requester_org": "请求人机构",
        "responsible_person": "责任人", "resolver": "解决人",
        "created_at": "创建时间", "resolved_at": "解决时间",
        "source_channel": "来源渠道", "nature": "性质",
        "sla_percent": "SLA%", "is_suspended": "挂起",
        "is_returned": "退回", "is_cancelled": "撤单",
        "symptom": "症状", "solution": "解决方案",
    }
    headers = [col_labels.get(c, c) for c in available_cols]

    rows = []
    for _, row in page_df.iterrows():
        rows.append([
            str(row.get(c, "")) if pd.notna(row.get(c, "")) else ""
            for c in available_cols
        ])

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "chart_id": chart_id,
        "value": value,
        "column": col,
        "headers": headers,
        "rows": rows,
    }
