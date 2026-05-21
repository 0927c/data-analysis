"""Skill 管理路由（管理员）。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_user, require_admin
from backend.models import User, Skill

router = APIRouter()


@router.get("")
async def get_skills(user: User = Depends(get_current_user)):
    """Skill 列表。"""
    # Return from skill engine for MVP (hardcoded for now)
    from backend.routers.chat import get_se
    se = get_se()
    if se:
        return se.get_available_skills()
    return []


@router.put("/{skill_id}/toggle")
async def toggle_skill(
    skill_id: int,
    enabled: Optional[bool] = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用 Skill。"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    if enabled is not None:
        skill.enabled = enabled
        await db.commit()

    return {"message": f"Skill 已{'启用' if skill.enabled else '禁用'}", "id": skill.id, "enabled": skill.enabled}


@router.put("/{skill_id}")
async def update_skill(
    skill_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    supported_chart_types: Optional[str] = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新 Skill 配置。"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    if name is not None:
        skill.name = name
    if description is not None:
        skill.description = description
    if supported_chart_types is not None:
        skill.supported_chart_types = supported_chart_types

    await db.commit()
    return {"message": "Skill 已更新", "id": skill.id}
