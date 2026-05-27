"""
OpsBrain Web — API Keys Routes

多 API 管理：支持多个 API Key 切换、启用/禁用。
参考 OpenClaw 的设计：多提供商、多 API Key、灵活切换。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import async_session
from ..models import User, ApiKey
from ..schemas import ApiKeyCreate, ApiKeyUpdate

from logging_setup import get_logger

log = get_logger(__name__)
apis_router = APIRouter()


@apis_router.get("/")
async def list_api_keys(user: User = Depends(get_current_user)):
    """列出所有 API Key"""
    async with async_session() as session:
        result = await session.execute(select(ApiKey).order_by(ApiKey.created_at))
        keys = result.scalars().all()
    return {"api_keys": [k.to_dict() for k in keys]}


@apis_router.post("/")
async def create_api_key(req: ApiKeyCreate, user: User = Depends(get_current_user)):
    """创建新的 API Key 配置"""
    async with async_session() as session:
        # 如果设为默认，先取消其他默认
        if req.is_default:
            result = await session.execute(
                select(ApiKey).where(ApiKey.is_default == True)
            )
            for old_default in result.scalars().all():
                old_default.is_default = False

        api_key = ApiKey(**req.model_dump())
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)

    log.info("API Key created", extra={"name": req.name, "provider": req.provider})
    return api_key.to_dict()


@apis_router.put("/{key_id}")
async def update_api_key(
    key_id: str,
    req: ApiKeyUpdate,
    user: User = Depends(get_current_user),
):
    """更新 API Key 配置"""
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=404, detail="API Key not found")

        # 如果设为此 API 为默认，取消其他默认
        if req.is_default:
            result = await session.execute(
                select(ApiKey).where(
                    ApiKey.is_default == True,
                    ApiKey.id != key_id
                )
            )
            for old_default in result.scalars().all():
                old_default.is_default = False

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(api_key, field, value)

        await session.commit()
        await session.refresh(api_key)

    return api_key.to_dict()


@apis_router.delete("/{key_id}")
async def delete_api_key(key_id: str, user: User = Depends(get_current_user)):
    """删除 API Key"""
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=404, detail="API Key not found")

        await session.delete(api_key)
        await session.commit()

    return {"message": "API Key deleted"}


@apis_router.post("/{key_id}/toggle")
async def toggle_api_key(key_id: str, user: User = Depends(get_current_user)):
    """切换 API Key 启用/禁用状态"""
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=404, detail="API Key not found")

        api_key.is_active = not api_key.is_active
        await session.commit()

    return {
        "id": key_id,
        "is_active": api_key.is_active,
        "message": "API Key " + ("enabled" if api_key.is_active else "disabled"),
    }


@apis_router.post("/{key_id}/set-default")
async def set_default_api_key(key_id: str, user: User = Depends(get_current_user)):
    """设为默认 API Key"""
    async with async_session() as session:
        # 取消所有默认
        result = await session.execute(
            select(ApiKey).where(ApiKey.is_default == True)
        )
        for old_default in result.scalars().all():
            old_default.is_default = False

        # 设置新的默认
        result = await session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=404, detail="API Key not found")

        api_key.is_default = True
        await session.commit()

    return {"id": key_id, "is_default": True, "message": "Default API Key updated"}
