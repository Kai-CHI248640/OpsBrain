"""
OpsBrain Web — Dashboard Stats & API Health Routes

提供控制台左侧面板需要的实时数据：
- 拓扑数量
- 故障设备
- API 状态（检测 API 是否能正常使用）
- Subagent 任务（正在工作/已使用的 Subagent）

业务逻辑已分离，可被 Agent 工具直接调用。
"""

from __future__ import annotations

import json as _json
import httpx
import asyncio
import socket

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, TopologySave, ApiKey, Subagent

from logging_setup import get_logger

log = get_logger(__name__)
dashboard_router = APIRouter()


# ─── 业务逻辑（可被 Agent 工具调用） ──────────────────────────────────

async def get_stats_data() -> dict:
    """获取统计数据（不依赖 HTTP 请求上下文）"""
    async with async_session() as session:
        topo_result = await session.execute(
            select(TopologySave).order_by(TopologySave.updated_at.desc())
        )
        topologies = topo_result.scalars().all()
        topology_count = len(topologies)

        faulty_devices = 0
        for topo in topologies:
            raw = topo.device_data
            if not raw:
                continue
            devices = _json.loads(raw) if isinstance(raw, str) else raw
            for d in devices:
                status = d.get("status", "")
                ip = d.get("ip", "")
                if status == "offline" or (not status and not ip):
                    faulty_devices += 1

        api_result = await session.execute(
            select(ApiKey).where(ApiKey.is_active == True)
        )
        active_apis = api_result.scalars().all()
        total_apis = len(active_apis)

        subagent_result = await session.execute(select(Subagent))
        subagents = subagent_result.scalars().all()
        working_subagents = sum(1 for s in subagents if s.status == "working")
        total_subagents = len(subagents)

    total_devices = sum(t.device_count for t in topologies)

    return {
        "topology_count": topology_count,
        "faulty_devices": faulty_devices,
        "total_devices": total_devices,
        "api_status": {
            "total": total_apis,
            "healthy": None,
            "unhealthy": None,
            "configured": total_apis > 0,
        },
        "subagent_tasks": {
            "working": working_subagents,
            "idle": total_subagents - working_subagents,
            "total": total_subagents,
        },
    }


async def check_api_health_data() -> dict:
    """检测所有活跃 API Key 是否可达（不依赖 HTTP 请求上下文）"""
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.is_active == True)
        )
        apis = result.scalars().all()

    default_bases = {
        "openai": "https://api.openai.com/v1/models",
        "deepseek": "https://api.deepseek.com/models",
        "siliconflow": "https://api.siliconflow.cn/v1/models",
        "anthropic": "https://api.anthropic.com/v1/messages",
        "ollama": "http://localhost:11434/api/tags",
    }

    async def _ping(k: ApiKey) -> dict:
        base = (k.api_base or "").strip() or default_bases.get(k.provider, "")
        if not base:
            return {"name": k.name, "healthy": False}
        try:
            headers = {"Authorization": f"Bearer {k.api_key}"}
            if k.provider == "ollama":
                headers = {}
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(base, headers=headers)
                return {"id": k.id, "name": k.name, "provider": k.provider, "healthy": r.status_code < 500}
        except Exception:
            return {"id": k.id, "name": k.name, "provider": k.provider, "healthy": False}

    results = await asyncio.gather(*[_ping(k) for k in apis]) if apis else []
    healthy = sum(1 for r in results if r["healthy"])
    return {"total": len(results), "healthy": healthy, "unhealthy": len(results) - healthy, "details": results}


# ─── HTTP 路由 ─────────────────────────────────────────────────────────

@dashboard_router.get("/stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    return await get_stats_data()


@dashboard_router.get("/api-health")
async def check_api_health(user: User = Depends(get_current_user)):
    return await check_api_health_data()


# ─── 本机信息（Local Mode）─────────────────────────────────────────

async def get_local_info() -> dict:
    """获取 OpsBrain 部署主机的系统信息"""
    import platform
    from platform_info import get_cpu_info, get_memory_info, get_disk_info, get_local_ips

    hostname = socket.gethostname()
    cpu = get_cpu_info()
    mem = get_memory_info()
    disk = get_disk_info()
    ips = get_local_ips()

    return {
        "hostname": hostname,
        "os": platform.platform()[:80],
        "cpu": cpu,
        "memory": mem,
        "disk": disk,
        "network": {"hostname": hostname, "ips": ips},
        "is_local": True,
    }


def get_network_runtime_data() -> dict:
    """Describe whether the backend can see the host network."""
    import os
    import ipaddress
    from platform_info import detect_local_subnets, detect_container

    subnets = detect_local_subnets()
    private_bridge_prefixes = ("172.17.", "172.18.", "172.19.")
    bridge_like = False
    host_like = False

    for subnet in subnets:
        try:
            net = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            continue
        if str(net.network_address).startswith(("172.17.", "172.18.", "172.19.")):
            bridge_like = True
        elif net.is_private and not str(net.network_address).startswith("127."):
            host_like = True

    in_container = detect_container()
    mode = "host" if in_container and host_like and not bridge_like else "bridge" if in_container else "bare-metal"
    can_sniff_lan = mode in ("host", "bare-metal")

    return {
        "in_container": in_container,
        "mode": mode,
        "can_sniff_lan": can_sniff_lan,
        "detected_subnets": subnets,
        "warning": "" if can_sniff_lan else (
            "当前后端看起来运行在 Docker bridge 网络中，自动嗅探大概率只能看到容器网段。"
            "如需发现真实局域网，请使用 host network 部署采集器，或改用种子发现/Console Server/Excel 导入。"
        ),
    }


def _detect_visible_subnets() -> list[str]:
    """Read routing table and return subnets visible to this process."""
    from platform_info import detect_local_subnets
    return detect_local_subnets()


@dashboard_router.get("/local-info")
async def local_info(user: User = Depends(get_current_user)):
    return await get_local_info()


@dashboard_router.get("/network-runtime")
async def network_runtime(user: User = Depends(get_current_user)):
    return get_network_runtime_data()


# ─── 知识库 API ─────────────────────────────────────────────────────

@dashboard_router.get("/knowledge")
async def get_knowledge(user: User = Depends(get_current_user)):
    from ..knowledge_base import get_all_configs, knowledge_summary
    return {"configs": get_all_configs(), "summary": knowledge_summary()}


@dashboard_router.post("/knowledge/search")
async def search_knowledge(data: dict, user: User = Depends(get_current_user)):
    from ..knowledge_base import search_configs
    query = (data.get("query") or "").strip()
    vendor = data.get("vendor", "*")
    top_k = data.get("top_k", 10)
    return {"results": search_configs(query, vendor=vendor, top_k=top_k)}


@dashboard_router.post("/knowledge")
async def add_knowledge(data: dict, user: User = Depends(get_current_user)):
    from ..knowledge_base import add_config
    vendor = (data.get("vendor") or "").strip()
    task = (data.get("task") or "").strip()
    commands = (data.get("commands") or "").strip()
    if not vendor or not task or not commands:
        raise HTTPException(400, "vendor, task, commands 不能为空")
    return add_config(vendor, task, commands, data.get("notes", ""))


@dashboard_router.post("/knowledge/import-file")
async def import_knowledge_file(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """上传 CSV/XLSX 文件导入知识库"""
    from ..knowledge_base import import_from_xlsx
    contents = await file.read()
    result = import_from_xlsx(contents)
    return result


# ─── 本机设备数据（用于拓扑自动添加）── ─────────────────────────────

async def get_local_device_data() -> dict:
    """生成本机设备数据，可自动添加到拓扑中"""
    info = await get_local_info()
    cpu = info["cpu"]
    mem = info["memory"]
    return {
        "name": f"OpsBrain-Local ({info['hostname']})",
        "type": "server",
        "vendor": "local",
        "ip": info["network"]["ips"][0] if info["network"]["ips"] else "127.0.0.1",
        "loginMethod": "ssh",
        "username": "",
        "password": "",
        "status": "online",
        "local": True,
        "details": f"{cpu['model'][:40]} | {cpu['cores']}核 | {mem['total_mb']}MB RAM"
    }
