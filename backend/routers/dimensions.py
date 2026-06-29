"""维度管理路由 — 查看/批准/拒绝待确认的分析维度。"""

from __future__ import annotations
import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models import User, PendingDimension
from backend.services import dimension_overrides

router = APIRouter()


@router.get("/pending", response_model=dict)
async def get_pending_dimensions(
    status_filter: str = Query("pending", description="pending/approved/rejected/all"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取待确认维度列表。"""
    query = select(PendingDimension)
    count_query = select(func.count()).select_from(PendingDimension)

    # 管理员看全部，普通用户只看自己的
    if user.role != "admin":
        query = query.where(PendingDimension.user_id == user.id)
        count_query = count_query.where(PendingDimension.user_id == user.id)

    if status_filter != "all":
        query = query.where(PendingDimension.status == status_filter)
        count_query = count_query.where(PendingDimension.status == status_filter)

    total = (await db.execute(count_query)).scalar()
    query = query.order_by(PendingDimension.usage_count.desc(), PendingDimension.created_at.desc())
    items = (await db.execute(query)).scalars().all()

    result = []
    for pd in items:
        sample_values = []
        if pd.sample_values:
            try:
                sample_values = json.loads(pd.sample_values)
            except json.JSONDecodeError:
                sample_values = []
        result.append({
            'id': pd.id,
            'user_id': pd.user_id,
            'query_text': pd.query_text,
            'matched_column': pd.matched_column,
            'matched_label': pd.matched_label,
            'sample_values': sample_values,
            'usage_count': pd.usage_count,
            'status': pd.status,
            'approved_group_by': pd.approved_group_by,
            'created_at': pd.created_at.isoformat() if pd.created_at else None,
            'reviewed_at': pd.reviewed_at.isoformat() if pd.reviewed_at else None,
        })

    return {'items': result, 'total': total}


@router.post("/{pd_id}/approve")
async def approve_dimension(
    pd_id: int,
    group_by_key: Optional[str] = Query(None, description="自定义 group_by key（默认用 matched_column）"),
    keywords: Optional[str] = Query(None, description="逗号分隔的触发关键词（默认用 query_text）"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批准一个待确认维度，加入映射表。"""
    result = await db.execute(select(PendingDimension).where(PendingDimension.id == pd_id))
    pd = result.scalar_one_or_none()
    if not pd:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 确定 group_by key
    key = group_by_key or pd.group_by_suggestion or pd.matched_column

    # 确定关键词
    kw_list = []
    if keywords:
        kw_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]
    else:
        # 从原始查询中提取关键词（去掉常见图表词）
        query = pd.query_text
        for chart_kw in ['分布', '占比', '排名', '趋势', '分析', '有多少', '多少']:
            query = query.replace(chart_kw, '')
        kw_list = [query.strip()] if query.strip() else [pd.matched_label or pd.matched_column]

    # 注册到覆盖层
    dimension_overrides.approve_dimension(key, pd.matched_column, kw_list)

    # 更新 DB 记录
    pd.status = 'approved'
    pd.approved_group_by = key
    pd.reviewed_by = user.id
    pd.reviewed_at = datetime.now()

    await db.commit()

    return {
        'message': f'维度「{pd.matched_label}」已批准，group_by={key}，关键词={kw_list}',
        'group_by': key,
        'keywords': kw_list,
    }


@router.post("/{pd_id}/reject")
async def reject_dimension(
    pd_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """拒绝一个待确认维度。"""
    result = await db.execute(select(PendingDimension).where(PendingDimension.id == pd_id))
    pd = result.scalar_one_or_none()
    if not pd:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 如果之前批准过，从覆盖层移除
    if pd.status == 'approved' and pd.approved_group_by:
        dimension_overrides.reject_dimension(pd.approved_group_by)

    pd.status = 'rejected'
    pd.reviewed_by = user.id
    pd.reviewed_at = datetime.now()

    await db.commit()

    return {'message': f'维度「{pd.matched_label}」已拒绝'}


@router.get("/overrides", response_model=dict)
async def get_current_overrides(
    user: User = Depends(get_current_user),
):
    """获取当前生效的维度覆盖层（已批准的维度）。"""
    return {
        'dimension_columns': dimension_overrides.DIMENSION_COLUMN_MAP,
        'keyword_dimensions': dimension_overrides.KEYWORD_DIMENSION_MAP,
    }
