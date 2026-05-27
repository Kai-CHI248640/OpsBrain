"""
OpsBrain Web — Project Config Routes

项目文件管理：拉取的项目、镜像、数据等文件的存放路径配置。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import async_session
from ..models import User, ProjectConfig
from ..schemas import ProjectConfigCreate, ProjectConfigUpdate

from logging_setup import get_logger

log = get_logger(__name__)
projects_router = APIRouter()


@projects_router.get("/")
async def list_project_configs(user: User = Depends(get_current_user)):
    """列出所有项目配置"""
    async with async_session() as session:
        result = await session.execute(select(ProjectConfig))
        configs = result.scalars().all()
    return {"project_configs": [c.to_dict() for c in configs]}


@projects_router.post("/")
async def create_project_config(
    req: ProjectConfigCreate,
    user: User = Depends(get_current_user),
):
    """创建项目配置"""
    async with async_session() as session:
        config = ProjectConfig(**req.model_dump())
        session.add(config)
        await session.commit()
        await session.refresh(config)

    log.info("Project config created", extra={"name": req.name})
    return config.to_dict()


@projects_router.put("/{config_id}")
async def update_project_config(
    config_id: str,
    req: ProjectConfigUpdate,
    user: User = Depends(get_current_user),
):
    """更新项目配置"""
    async with async_session() as session:
        result = await session.execute(
            select(ProjectConfig).where(ProjectConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Project config not found")

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await session.commit()
        await session.refresh(config)

    return config.to_dict()


@projects_router.get("/{config_id}")
async def get_project_config(config_id: str, user: User = Depends(get_current_user)):
    """获取单个项目配置"""
    async with async_session() as session:
        result = await session.execute(
            select(ProjectConfig).where(ProjectConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Project config not found")
    return config.to_dict()


@projects_router.delete("/{config_id}")
async def delete_project_config(config_id: str, user: User = Depends(get_current_user)):
    """删除项目配置"""
    async with async_session() as session:
        result = await session.execute(
            select(ProjectConfig).where(ProjectConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Project config not found")

        await session.delete(config)
        await session.commit()

    return {"message": "Project config deleted"}
