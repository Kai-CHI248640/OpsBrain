"""Add TopologySave model and routes to backend."""
import paramiko, json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("129.211.28.47", 22, "root", "248640", allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

# ── 1. Add TopologySave model to models.py ─────────────────────────
topo_model = """

class TopologySave(Base):
    __tablename__ = "topology_saves"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    discovery_method: Mapped[str] = mapped_column(String(64), default="lan")
    device_count: Mapped[int] = mapped_column(Integer, default=0)
    link_count: Mapped[int] = mapped_column(Integer, default=0)
    device_data: Mapped[str] = mapped_column(Text, default="[]")
    link_data: Mapped[str] = mapped_column(Text, default="[]")
    analysis: Mapped[str] = mapped_column(Text, default="")
    mermaid_code: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        import json as _json
        return {
            "id": self.id,
            "name": self.name,
            "discovery_method": self.discovery_method,
            "device_count": self.device_count,
            "link_count": self.link_count,
            "device_data": _json.loads(self.device_data) if self.device_data else [],
            "link_data": _json.loads(self.link_data) if self.link_data else [],
            "analysis": self.analysis,
            "mermaid_code": self.mermaid_code,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }
"""

with sftp.open("/root/opsbrain/web/backend/app/models.py", "r") as f:
    models = f.read().decode()

if "class TopologySave" not in models:
    models = models.rstrip() + "\n" + topo_model + "\n"
    with sftp.open("/root/opsbrain/web/backend/app/models.py", "w") as f:
        f.write(models.encode())
    print("[OK] TopologySave model added")
else:
    print("[OK] TopologySave model already exists")

# ── 2. Create topology routes file ─────────────────────────────────
topo_routes = r'''"""
OpsBrain Web — Topology Save/Load Routes
"""
from __future__ import annotations

import json as _json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, TopologySave

import logging
log = logging.getLogger(__name__)
topology_router = APIRouter()


@topology_router.get("/")
async def list_topologies(user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).order_by(TopologySave.updated_at.desc())
        )
        topologies = result.scalars().all()
    return {"topologies": [t.to_dict() for t in topologies]}


@topology_router.post("/")
async def save_topology(data: dict, user: User = Depends(get_current_user)):
    name = data.get("name", "").strip()
    if not name:
        async with async_session() as session:
            result = await session.execute(select(TopologySave))
            existing = len(result.scalars().all())
        name = f"Topology{existing + 1}"

    async with async_session() as session:
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
        session.add(topo)
        await session.commit()
        await session.refresh(topo)

    log.info("Topology saved", extra={"name": name, "id": topo.id})
    return topo.to_dict()


@topology_router.get("/{topo_id}")
async def get_topology(topo_id: str, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
    if not topo:
        raise HTTPException(status_code=404, detail="Topology not found")
    return topo.to_dict()


@topology_router.delete("/{topo_id}")
async def delete_topology(topo_id: str, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
        if not topo:
            raise HTTPException(status_code=404, detail="Topology not found")
        await session.delete(topo)
        await session.commit()
    return {"message": "Topology deleted", "id": topo_id}
'''

with sftp.open("/root/opsbrain/web/backend/app/routes/topology.py", "w") as f:
    f.write(topo_routes.encode())
print("[OK] topology.py routes created")

# ── 3. Register in routes/__init__.py ──────────────────────────────
with sftp.open("/root/opsbrain/web/backend/app/routes/__init__.py", "r") as f:
    init = f.read().decode()

if "topology_router" not in init:
    init = init.replace(
        "from .agents import agents_router",
        "from .agents import agents_router\nfrom .topology import topology_router"
    )
    init = init.replace(
        'prefix="/agents", tags=["Agent Configs"])',
        'prefix="/agents", tags=["Agent Configs"])\nrouter.include_router(topology_router, prefix="/topology", tags=["Topology"])'
    )
    with sftp.open("/root/opsbrain/web/backend/app/routes/__init__.py", "w") as f:
        f.write(init.encode())
    print("[OK] topology router registered")
else:
    print("[OK] topology router already registered")

sftp.close()

# ── 4. Rebuild web backend ─────────────────────────────────────────
import time, sys

def run(cmd, wait=10):
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    time.sleep(wait)
    out = chan.recv(65536).decode(errors="replace")
    sys.stdout.write(out)
    sys.stdout.flush()

print("\n=== Rebuild web backend ===")
run("cd /root/opsbrain/oobm-topology && docker compose build web 2>&1", wait=180)

print("\n=== Restart ===")
run("cd /root/opsbrain/oobm-topology && docker compose down && docker compose up -d nginx web 2>&1", wait=15)
time.sleep(5)

print("\n=== Test new API ===")
run("curl -s http://localhost/opsbrain/api/v1/topology/ 2>&1", wait=3)

client.close()
print("\nBackend updated: TopologySave model + CRUD routes")
