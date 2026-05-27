"""
OpsBrain Web — Auth Routes

登录 / 注册 / 初始设置 / 当前用户信息
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, ensure_admin_exists,
)
from ..database import async_session
from ..models import User
from ..schemas import LoginRequest, SetupRequest, TokenResponse

from logging_setup import get_logger

log = get_logger(__name__)
auth_router = APIRouter()


# ── 检查是否需要初始设置 ────────────────────────────────────────────────────


@auth_router.get("/setup-required")
async def check_setup_required():
    """检查系统是否需要初始化（首次部署）"""
    needs_setup = await ensure_admin_exists()
    return {"setup_required": needs_setup}


# ── 初始设置（首次部署） ─────────────────────────────────────────────────────


@auth_router.post("/setup", response_model=TokenResponse)
async def initial_setup(req: SetupRequest):
    """创建第一个管理员账号（仅首次部署时可用）"""
    needs_setup = await ensure_admin_exists()
    if not needs_setup:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System already initialized",
        )

    async with async_session() as session:
        # 检查用户名是否重复
        result = await session.execute(
            select(User).where(User.username == req.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")

        user = User(
            username=req.username,
            password_hash=hash_password(req.password),
            display_name=req.display_name or req.username,
            role="admin",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    log.info("Admin user created", extra={"username": req.username})

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=user.to_dict(),
    )


# ── 登录 ────────────────────────────────────────────────────────────────────


@auth_router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """用户登录"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.username == req.username, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(req.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        # 更新最后登录时间
        from datetime import datetime
        user.last_login = datetime.utcnow()
        await session.commit()

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, user=user.to_dict())


# ── 当前用户信息 ────────────────────────────────────────────────────────────


@auth_router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return user.to_dict()


# ── 修改密码 ────────────────────────────────────────────────────────────────


@auth_router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    user: User = Depends(get_current_user),
):
    """修改密码"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not verify_password(old_password, db_user.password_hash):
            raise HTTPException(status_code=400, detail="Old password is incorrect")

        db_user.password_hash = hash_password(new_password)
        await session.commit()

    return {"message": "Password updated"}
