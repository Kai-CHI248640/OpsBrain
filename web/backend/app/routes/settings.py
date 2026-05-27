"""
OpsBrain Web — Settings Routes

通用设置管理（主题、系统参数等）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import async_session
from ..models import User, Setting
from ..schemas import SettingUpdate, ThemeUpdate

from logging_setup import get_logger

log = get_logger(__name__)
settings_router = APIRouter()


@settings_router.get("/")
async def list_settings(category: str = "", user: User = Depends(get_current_user)):
    """获取所有设置，可按分类筛选"""
    async with async_session() as session:
        if category:
            result = await session.execute(
                select(Setting).where(Setting.category == category)
            )
        else:
            result = await session.execute(select(Setting))
        settings = result.scalars().all()
    return {"settings": [s.to_dict() for s in settings]}


@settings_router.get("/{key}")
async def get_setting(key: str, user: User = Depends(get_current_user)):
    """获取单条设置"""
    async with async_session() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == key)
        )
        setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting.to_dict()


@settings_router.put("/{key}")
async def update_setting(
    key: str,
    req: SettingUpdate,
    user: User = Depends(get_current_user),
):
    """更新设置"""
    async with async_session() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = req.value
            setting.category = req.category
            setting.description = req.description
        else:
            from ..models import Setting as SettingModel
            setting = SettingModel(
                key=req.key,
                value=req.value,
                category=req.category,
                description=req.description,
            )
            session.add(setting)

        await session.commit()
        await session.refresh(setting)

    log.info("Setting updated", extra={"key": key})
    return setting.to_dict()


@settings_router.post("/theme")
async def set_theme(
    req: ThemeUpdate,
    user: User = Depends(get_current_user),
):
    """设置主题（light/dark）"""
    key = "ui.theme"
    async with async_session() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = req.theme
        else:
            from ..models import Setting as SettingModel
            setting = SettingModel(
                key=key,
                value=req.theme,
                category="ui",
                description="界面主题",
            )
            session.add(setting)

        await session.commit()

    return {"theme": req.theme, "message": "Theme updated"}
