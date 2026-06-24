"""
OpsBrain Web — Topology Service

业务逻辑层：拓扑发现、保存、查询等操作
"""

from __future__ import annotations

import json as _json
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TopologySave, Subagent, ApiKey


def _now() -> datetime:
    return datetime.utcnow()


class TopologyService:
    """拓扑业务服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_topologies(self) -> List[Dict[str, Any]]:
        """列出所有拓扑"""
        result = await self.session.execute(
            select(TopologySave).order_by(TopologySave.updated_at.desc())
        )
        topologies = result.scalars().all()
        return [t.to_dict() for t in topologies]

    async def get_topology(self, topo_id: str) -> Optional[Dict[str, Any]]:
        """获取单个拓扑"""
        result = await self.session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
        return topo.to_dict() if topo else None

    async def create_topology(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建拓扑并自动创建绑定的 Subagent"""
        name = data.get("name", "").strip()
        if not name:
            existing = await self._count_topologies()
            name = f"Topology{existing + 1}"

        topo = TopologySave(
            name=name,
            discovery_method=data.get("discovery_method", "lan"),
            device_count=data.get("device_count", 0),
            link_count=data.get("link_count", 0),
            device_data=_json.dumps(data.get("device_data", [])),
            link_data=_json.dumps(data.get("link_data", [])),
            analysis=data.get("analysis", ""),
            mermaid_code=data.get("mermaid_code", ""),
        )
        self.session.add(topo)
        await self.session.flush()

        default_api = await self._get_default_api_key()
        subagent = Subagent(
            topology_id=topo.id,
            name=f"Agent-{name}",
            status="idle",
            api_key_id=default_api.id if default_api else "",
            message_count=0,
        )
        self.session.add(subagent)
        await self.session.flush()

        topo.subagent_id = subagent.id
        await self.session.commit()
        await self.session.refresh(topo)

        return topo.to_dict()

    async def update_topology(self, topo_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新拓扑"""
        result = await self.session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
        if not topo:
            return None

        if "name" in data:
            topo.name = data["name"]
        if "device_data" in data:
            topo.device_data = _json.dumps(data["device_data"])
            topo.device_count = len(data["device_data"])
        if "link_data" in data:
            topo.link_data = _json.dumps(data["link_data"])
            topo.link_count = len(data["link_data"])

        topo.updated_at = _now()
        await self.session.commit()
        await self.session.refresh(topo)

        return topo.to_dict()

    async def delete_topology(self, topo_id: str) -> bool:
        """删除拓扑及绑定的 Subagent"""
        result = await self.session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
        if not topo:
            return False

        if topo.subagent_id:
            sub_result = await self.session.execute(
                select(Subagent).where(Subagent.id == topo.subagent_id)
            )
            subagent = sub_result.scalar_one_or_none()
            if subagent:
                await self.session.delete(subagent)

        await self.session.delete(topo)
        await self.session.commit()

        return True

    async def _count_topologies(self) -> int:
        result = await self.session.execute(select(TopologySave))
        return len(result.scalars().all())

    async def _get_default_api_key(self) -> Optional[ApiKey]:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.is_active == True).order_by(ApiKey.is_default.desc())
        )
        return result.scalar_one_or_none()