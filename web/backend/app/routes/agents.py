"""
OpsBrain Web — Agent Config Routes

Agent 文件管理：参考 OpenClaw 的 Agent 机制。
管理 Agent 类型、技能文件、运行时路径等。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import async_session
from ..models import User, AgentConfig
from ..schemas import AgentConfigCreate, AgentConfigUpdate

from logging_setup import get_logger

log = get_logger(__name__)
agents_router = APIRouter()


@agents_router.get("/")
async def list_agent_configs(user: User = Depends(get_current_user)):
    """列出所有 Agent 配置"""
    async with async_session() as session:
        result = await session.execute(select(AgentConfig).order_by(AgentConfig.created_at))
        configs = result.scalars().all()
    return {"agent_configs": [c.to_dict() for c in configs]}


@agents_router.post("/")
async def create_agent_config(
    req: AgentConfigCreate,
    user: User = Depends(get_current_user),
):
    """创建 Agent 配置"""
    async with async_session() as session:
        config = AgentConfig(**req.model_dump())
        session.add(config)
        await session.commit()
        await session.refresh(config)

    log.info("Agent config created", extra={"name": req.name, "type": req.agent_type})
    return config.to_dict()


@agents_router.put("/{config_id}")
async def update_agent_config(
    config_id: str,
    req: AgentConfigUpdate,
    user: User = Depends(get_current_user),
):
    """更新 Agent 配置"""
    async with async_session() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Agent config not found")

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await session.commit()
        await session.refresh(config)

    return config.to_dict()


@agents_router.get("/{config_id}")
async def get_agent_config(config_id: str, user: User = Depends(get_current_user)):
    """获取单个 Agent 配置"""
    async with async_session() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found")
    return config.to_dict()


@agents_router.delete("/{config_id}")
async def delete_agent_config(config_id: str, user: User = Depends(get_current_user)):
    """删除 Agent 配置"""
    async with async_session() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Agent config not found")

        await session.delete(config)
        await session.commit()

    return {"message": "Agent config deleted"}


@agents_router.post("/{config_id}/toggle")
async def toggle_agent(config_id: str, user: User = Depends(get_current_user)):
    """开启/关闭 Agent"""
    async with async_session() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Agent config not found")

        config.is_enabled = not config.is_enabled
        await session.commit()

    return {
        "id": config_id,
        "is_enabled": config.is_enabled,
        "message": "Agent " + ("enabled" if config.is_enabled else "disabled"),
    }
