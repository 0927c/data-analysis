"""认证路由。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import create_access_token, verify_password, hash_password, get_current_user
from backend.database import get_db
from backend.models import User
from backend.schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if user.auth_provider == "local":
        if not verify_password(req.password, user.password_hash or ""):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(user.id, user.username, user.role)
    return LoginResponse(
        access_token=token,
        user={'id': user.id, 'username': user.username, 'display_name': user.display_name, 'role': user.role},
    )


@router.post("/logout")
async def logout():
    return {"message": "已退出登录"}


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return user
