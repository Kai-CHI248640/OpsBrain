"""
OpsBrain Web — Subagent Routes

Subagent 是自动绑定到每个拓扑的轻量 Agent。
由拓扑保存时自动创建，无需手动管理。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, Subagent, TopologySave

from logging_setup import get_logger

log = get_logger(__name__)
subagent_router = APIRouter()


def _now() -> datetime:
    return datetime.utcnow()


@subagent_router.get("/")
async def list_subagents(user: User = Depends(get_current_user)):
    """列出所有 Subagent"""
    async with async_session() as session:
        result = await session.execute(
            select(Subagent).order_by(Subagent.created_at.desc())
        )
        subagents = result.scalars().all()
    return {"subagents": [s.to_dict() for s in subagents]}


@subagent_router.get("/topology/{topo_id}")
async def get_subagent_by_topology(topo_id: str, user: User = Depends(get_current_user)):
    """获取指定拓扑绑定的 Subagent"""
    async with async_session() as session:
        result = await session.execute(
            select(Subagent).where(Subagent.topology_id == topo_id)
        )
        subagent = result.scalar_one_or_none()
    if not subagent:
        raise HTTPException(status_code=404, detail="Subagent not found for this topology")
    return subagent.to_dict()


@subagent_router.put("/{subagent_id}/status")
async def update_subagent_status(
    subagent_id: str,
    data: dict,
    user: User = Depends(get_current_user),
):
    """更新 Subagent 状态（idle / working / error）"""
    async with async_session() as session:
        result = await session.execute(
            select(Subagent).where(Subagent.id == subagent_id)
        )
        subagent = result.scalar_one_or_none()
        if not subagent:
            raise HTTPException(status_code=404, detail="Subagent not found")

        new_status = data.get("status", "")
        if new_status not in ("idle", "working", "error"):
            raise HTTPException(status_code=400, detail="Invalid status")

        subagent.status = new_status
        subagent.last_active = _now()
        if data.get("message_count") is not None:
            subagent.message_count = data["message_count"]
        await session.commit()
        await session.refresh(subagent)

    return subagent.to_dict()
