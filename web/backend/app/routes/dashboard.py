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

    return {
        "topology_count": topology_count,
        "faulty_devices": faulty_devices,
        "api_status": {"total": total_apis, "healthy": 0, "unhealthy": 0},
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
    import platform, socket, os

    # CPU
    cpu_model = "Unknown"
    cpu_cores = 0
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                if "processor" in line:
                    cpu_cores += 1
    except:
        cpu_cores = os.cpu_count() or 0

    # Memory
    mem_total = mem_used = mem_free = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    mem_total = int(line.split()[1]) // 1024
                elif "MemAvailable" in line:
                    mem_free = int(line.split()[1]) // 1024
                elif "MemFree" in line and not mem_free:
                    mem_free = int(line.split()[1]) // 1024
        mem_used = mem_total - mem_free
    except:
        pass

    # Disk
    try:
        stat = os.statvfs("/var/lib/opsbrain" if os.path.exists("/var/lib/opsbrain") else "/")
        disk_total = (stat.f_frsize * stat.f_blocks) // (1024**3)
        disk_free = (stat.f_frsize * stat.f_bavail) // (1024**3)
    except:
        disk_total = disk_free = 0

    # Network
    hostname = socket.gethostname()
    ips = []
    try:
        import subprocess
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3)
        ips = [ip.strip() for ip in result.stdout.split() if ip.strip()]
    except:
        pass
    if not ips:
        try:
            ips = [socket.gethostbyname(hostname)]
        except:
            ips = ["unknown"]

    return {
        "hostname": hostname,
        "os": platform.platform()[:80],
        "cpu": {"model": cpu_model, "cores": cpu_cores},
        "memory": {"total_mb": mem_total, "used_mb": mem_used, "free_mb": mem_free,
                    "pct": round(mem_used/mem_total*100, 1) if mem_total else 0},
        "disk": {"total_gb": disk_total, "free_gb": disk_free},
        "network": {"hostname": hostname, "ips": ips},
        "is_local": True,
    }


@dashboard_router.get("/local-info")
async def local_info(user: User = Depends(get_current_user)):
    return await get_local_info()


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
