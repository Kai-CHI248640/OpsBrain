"""
OpsBrain Web — Topology Save/Load Routes

当保存拓扑时，自动创建绑定的 Subagent。
"""

from __future__ import annotations

import json as _json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, TopologySave, Subagent, ApiKey
from .dashboard import get_network_runtime_data

from logging_setup import get_logger

log = get_logger(__name__)
topology_router = APIRouter()


def _now() -> datetime:
    return datetime.utcnow()


@topology_router.get("/")
async def list_topologies(user: User = Depends(get_current_user)):
    """列出所有已保存的拓扑"""
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).order_by(TopologySave.updated_at.desc())
        )
        topologies = result.scalars().all()
    return {"topologies": [t.to_dict() for t in topologies]}


@topology_router.post("/")
async def save_topology(data: dict, user: User = Depends(get_current_user)):
    """保存拓扑，并自动创建绑定的 Subagent"""
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
        await session.flush()

        # ── 自动创建 Subagent 绑定到此拓扑 ──
        # 使用第一个可用的 API Key
        api_result = await session.execute(
            select(ApiKey).where(ApiKey.is_active == True).order_by(ApiKey.is_default.desc())
        )
        default_api = api_result.scalar_one_or_none()

        subagent = Subagent(
            topology_id=topo.id,
            name=f"Agent-{name}",
            status="idle",
            api_key_id=default_api.id if default_api else "",
            message_count=0,
        )
        session.add(subagent)
        await session.flush()

        topo.subagent_id = subagent.id
        await session.commit()
        await session.refresh(topo)

    log.info("Topology saved with subagent",
             extra={"name": name, "id": topo.id, "subagent_id": topo.subagent_id})
    return topo.to_dict()


@topology_router.get("/{topo_id}")
async def get_topology(topo_id: str, user: User = Depends(get_current_user)):
    """获取单个拓扑详情"""
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
    if not topo:
        raise HTTPException(status_code=404, detail="Topology not found")
    return topo.to_dict()


@topology_router.put("/{topo_id}")
async def update_topology(topo_id: str, data: dict, user: User = Depends(get_current_user)):
    """更新拓扑（名称、设备数据等）"""
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
        if not topo:
            raise HTTPException(status_code=404, detail="Topology not found")

        if "name" in data:
            topo.name = data["name"]
        if "device_data" in data:
            topo.device_data = _json.dumps(data["device_data"])
            topo.device_count = len(data["device_data"])
        if "link_data" in data:
            topo.link_data = _json.dumps(data["link_data"])
            topo.link_count = len(data["link_data"])

        topo.updated_at = _now()
        await session.commit()
        await session.refresh(topo)

    return topo.to_dict()


@topology_router.delete("/{topo_id}")
async def delete_topology(topo_id: str, user: User = Depends(get_current_user)):
    """删除拓扑及绑定的 Subagent"""
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
        if not topo:
            raise HTTPException(status_code=404, detail="Topology not found")

        # 同时删除绑定的 Subagent
        if topo.subagent_id:
            sub_result = await session.execute(
                select(Subagent).where(Subagent.id == topo.subagent_id)
            )
            subagent = sub_result.scalar_one_or_none()
            if subagent:
                await session.delete(subagent)

        await session.delete(topo)
        await session.commit()

    # 重置 Agent 记忆
    from .agent import _save_mem
    _save_mem("agent", [])

    return {"message": "Topology and bound subagent deleted, Agent memory reset", "id": topo_id}


def _detect_local_subnets() -> list[str]:
    """自动检测本机所有网卡上的子网段"""
    from platform_info import detect_local_subnets
    return detect_local_subnets()


@topology_router.post("/discover")
async def run_discovery(data: dict):
    """Agent 内部调用的网络嗅探 API（无需认证，仅内部使用）"""
    method = data.get("method", "lan")
    target = data.get("target", "")
    username = data.get("username", "admin")
    password = data.get("password", "")

    try:
        # ── 自动检测所有网卡子网 ──
        import sys, os, asyncio as _aio, ipaddress, socket

        target_subnets: list[str] = []
        if target:
            # 用户指定了 target，就用指定的
            try:
                net = ipaddress.ip_network(target, strict=False)
                target_subnets.append(str(net))
            except ValueError:
                # 可能是单个 IP，直接使用
                target_subnets.append(target)
        else:
            # 自动检测本地所有网卡子网
            detected = _detect_local_subnets()
            if detected:
                target_subnets = detected
            else:
                # 回退：尝试常见私有网段
                target_subnets = ["10.0.0.0/24", "172.16.0.0/24", "172.17.0.0/24",
                                 "192.168.0.0/24", "192.168.1.0/24", "192.168.2.0/24"]

        scanned_hosts: list[str] = []
        for subnet_str in target_subnets[:3]:  # 最多3个子网
            try:
                net = ipaddress.ip_network(subnet_str, strict=False)
                all_hosts = [str(h) for h in net.hosts()]
                if len(all_hosts) > 256:
                    scanned_hosts.extend(all_hosts[:256])
                else:
                    scanned_hosts.extend(all_hosts)
            except ValueError:
                scanned_hosts.append(subnet_str)

        # 确保网关 IP 和本机 IP 在扫描列表中
        from platform_info import get_gateway_ip, get_local_ips
        gw = get_gateway_ip()
        if gw and gw not in scanned_hosts:
            scanned_hosts.insert(0, gw)
        local_ips = get_local_ips()
        for lip in local_ips:
            if lip not in scanned_hosts:
                scanned_hosts.append(lip)

        # 去重 + 总量限制
        seen = set()
        hosts = []
        for h in scanned_hosts:
            if h not in seen:
                seen.add(h)
                hosts.append(h)
                if len(hosts) >= 256:
                    break

        # 并发 TCP 扫描（semaphore=100，timeout=0.5s）
        sem = _aio.Semaphore(100)

        async def _probe(host: str) -> dict | None:
            async with sem:
                open_ports = {}
                probe_ports = [(22, "ssh"), (23, "telnet"), (80, "http"),
                               (443, "https"), (161, "snmp"), (8000, "http"),
                               (8080, "http"), (8443, "https")]
                for port, svc_name in probe_ports:
                    try:
                        _, w = await _aio.wait_for(_aio.open_connection(host, port), timeout=0.5)
                        w.close()
                        await w.wait_closed()
                        open_ports[svc_name] = port
                    except Exception:
                        pass
                if not open_ports:
                    return None
                login = "ssh" if "ssh" in open_ports else ("telnet" if "telnet" in open_ports else None)
                dev_type = "unknown"
                if "snmp" in open_ports and ("http" in open_ports or "https" in open_ports):
                    dev_type = "router"
                elif "http" in open_ports and not login:
                    dev_type = "router"
                is_local = host in local_ips
                dev_name = f"本机 ({host})" if is_local else f"Device-{host}"
                return {
                    "name": dev_name, "ip": host,
                    "type": dev_type, "vendor": "unknown",
                    "loginMethod": login,
                    "username": username if login else "", "password": password or "" if login else "",
                    "status": "online",
                    "port": open_ports.get(login, 0) if login else 0,
                    "open_ports": open_ports,
                    "local": is_local,
                }

        tasks = [_probe(h) for h in hosts]
        results = await _aio.gather(*tasks)
        devices = [d for d in results if d is not None]

        # ── 生成拓扑连线（星形：所有设备连网关） ──
        links = []
        gw_ip = gw or ""
        gw_dev = None
        for d in devices:
            if d["ip"] == gw_ip:
                gw_dev = d
                break
        if gw_dev:
            for d in devices:
                if d["ip"] != gw_ip:
                    links.append({
                        "source": gw_dev["name"],
                        "target": d["name"],
                        "source_port": "LAN",
                        "target_port": "",
                        "confirmed": False,
                    })
        elif len(devices) >= 2:
            hub = devices[0]
            for d in devices[1:]:
                links.append({
                    "source": hub["name"],
                    "target": d["name"],
                    "source_port": "LAN",
                    "target_port": "",
                    "confirmed": False,
                })

        # 深度嗅探：尝试 SSH 获取设备信息
        links, analysis = [], ""
        runtime = get_network_runtime_data()

        if devices and password:
            for dev in devices[:5]:
                if dev["loginMethod"] == "ssh":
                    try:
                        import paramiko as pm
                        def _probe():
                            c = pm.SSHClient()
                            c.set_missing_host_key_policy(pm.AutoAddPolicy())
                            c.connect(dev["ip"], 22, username, password, timeout=8,
                                      allow_agent=False, look_for_keys=False)
                            _, stdout, _ = c.exec_command("show version | include uptime", timeout=8)
                            out = stdout.read().decode(errors='replace')[:200]
                            c.close(); return out
                        loop = _aio.get_running_loop()
                        ver = await loop.run_in_executor(None, _probe)
                        dev["probe_result"] = ver.strip()
                        vl = ver.lower()
                        if "cisco" in vl: dev["vendor"] = "cisco"
                        elif "huawei" in vl: dev["vendor"] = "huawei"
                        elif "h3c" in vl: dev["vendor"] = "h3c"
                        elif "juniper" in vl: dev["vendor"] = "juniper"
                        if any(k in vl for k in ("router", "ios-xe")): dev["type"] = "router"
                        elif any(k in vl for k in ("switch", "catalyst", "nexus")): dev["type"] = "switch"
                    except Exception:
                        pass
            subnet_info = ", ".join(target_subnets[:5])
            analysis = f"扫描完成，发现 {len(devices)} 台设备（扫描了 {len(hosts)} 个IP，网段: {subnet_info}）"
        else:
            subnet_info = ", ".join(target_subnets[:5])
            analysis = f"扫描完成，发现 {len(devices)} 台设备（扫描了 {len(hosts)} 个IP，网段: {subnet_info}）"
            if not password:
                analysis += "，未提供密码无法深度嗅探"
        if runtime.get("warning"):
            analysis += f"。提示：{runtime['warning']}"

        # 拓扑名不再直接用 target 网段
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        name = data.get("name", "") or f"{method}-发现-{timestamp}"

        async with async_session() as session:
            topo = TopologySave(
                name=name,
                discovery_method=method,
                device_count=len(devices),
                link_count=len(links),
                device_data=_json.dumps(devices),
                link_data=_json.dumps(links),
                analysis=analysis,
                mermaid_code="",
            )
            session.add(topo)
            await session.flush()

            api_result = await session.execute(
                select(ApiKey).where(ApiKey.is_active == True).order_by(ApiKey.is_default.desc())
            )
            default_api = api_result.scalar_one_or_none()
            subagent = Subagent(
                topology_id=topo.id,
                name=f"Agent-{name}",
                status="idle",
                api_key_id=default_api.id if default_api else "",
                message_count=0,
            )
            session.add(subagent)
            await session.flush()
            topo.subagent_id = subagent.id
            await session.commit()

        return {
            "ok": True,
            "topo_id": topo.id[:8],
            "name": name,
            "device_count": len(devices),
            "link_count": len(links),
            "runtime": runtime,
            "analysis": analysis,
            "devices": [{"name": d.get("name","?"), "type": d.get("type","?"),
                         "ip": d.get("ip","?"), "vendor": d.get("vendor","?")} for d in devices[:10]],
        }
    except ImportError as ie:
        return {
            "ok": False,
            "error": f"缺少依赖模块: {ie}。请确认容器已安装所需 Python 包。",
        }
    except Exception as e:
        return {"ok": False, "error": f"嗅探失败: {str(e)}"}


@topology_router.post("/discover-seed")
async def run_seed_discovery(data: dict):
    """种子设备发现：从已知设备 SSH 登录，LLDP/CDP 递归发现全拓扑"""
    seeds = data.get("seeds", [])
    max_devices = data.get("max_devices", 50)
    max_depth = data.get("max_depth", 5)

    if not seeds:
        return {"ok": False, "error": "至少需要一台种子设备"}

    try:
        from ..discovery.seed import SeedDiscovery

        engine = SeedDiscovery(
            seeds=seeds,
            max_devices=max_devices,
            max_depth=max_depth,
            global_password=data.get("global_password", ""),
        )
        result = await engine.run()

        # 保存到数据库
        async with async_session() as session:
            topo = TopologySave(
                name=data.get("name", "") or f"种子发现-{datetime.now().strftime('%Y%m%d-%H%M')}",
                discovery_method="seed",
                device_count=result["device_count"],
                link_count=result["link_count"],
                device_data=_json.dumps(result["devices"]),
                link_data=_json.dumps(result["links"]),
                analysis=result.get("analysis", ""),
                mermaid_code=result.get("mermaid_code", ""),
            )
            session.add(topo)
            await session.flush()

            api_result = await session.execute(
                select(ApiKey).where(ApiKey.is_active == True).order_by(ApiKey.is_default.desc())
            )
            default_api = api_result.scalar_one_or_none()
            subagent = Subagent(
                topology_id=topo.id,
                name=f"Agent-{topo.name}",
                status="idle",
                api_key_id=default_api.id if default_api else "",
                message_count=0,
            )
            session.add(subagent)
            await session.flush()
            topo.subagent_id = subagent.id
            await session.commit()

        result["topo_id"] = topo.id[:8]
        return result

    except Exception as e:
        log.error("Seed discovery failed", extra={"error": str(e)})
        return {"ok": False, "error": f"种子发现失败: {str(e)}"}


@topology_router.post("/scan")
async def run_network_scan(data: dict):
    """主机网络嗅探：ARP + TCP 端口扫描（需要 host 网络模式）"""
    subnets = data.get("subnets", [])
    max_hosts = data.get("max_hosts", 256)
    snmp_community = data.get("snmp_community", "public")
    
    try:
        from ..scanner.scanner import NetworkScanner
        
        scanner = NetworkScanner(
            subnets=subnets or None,
            max_hosts=max_hosts,
            snmp_community=snmp_community,
        )
        result = await scanner.scan()
        runtime = get_network_runtime_data()
        result["runtime"] = runtime
        if runtime.get("warning"):
            result["analysis"] = f"{result.get('analysis', '')}。提示：{runtime['warning']}"
        
        # 保存
        async with async_session() as session:
            topo = TopologySave(
                name=data.get("name", "") or f"网络嗅探-{datetime.now().strftime('%Y%m%d-%H%M')}",
                discovery_method="scan",
                device_count=result["device_count"],
                link_count=0,
                device_data=_json.dumps(result.get("devices", [])),
                link_data=_json.dumps([]),
                analysis=result.get("analysis", ""),
                mermaid_code="",
            )
            session.add(topo)
            await session.flush()
            topo.subagent_id = ""
            await session.commit()
        
        return result
    except Exception as e:
        log.error("Scan failed", extra={"error": str(e)})
        return {"ok": False, "error": f"网络嗅探失败: {str(e)}"}


@topology_router.post("/console-discover")
async def discover_console_ports(data: dict):
    """串口服务器端口自动发现"""
    server_ip = data.get("ip", "")
    start_port = data.get("start", 2001)
    end_port = data.get("end", 2100)
    
    if not server_ip:
        return {"ok": False, "error": "请输入串口服务器 IP"}
    
    try:
        from ..scanner.console import auto_discover_ports
        ports = await auto_discover_ports(server_ip, range(start_port, end_port + 1))
        return {
            "ok": True,
            "active_ports": ports,
            "count": len(ports),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@topology_router.post("/console-collect")
async def collect_console_devices(data: dict):
    """串口服务器批量采集"""
    server_ip = data.get("ip", "")
    brand = data.get("brand", "telnet")
    devices = data.get("devices", [])
    
    if not server_ip:
        return {"ok": False, "error": "请输入串口服务器 IP"}
    if not devices:
        return {"ok": False, "error": "无设备列表"}
    
    try:
        from ..scanner.console import ConsoleCollector
        collector = ConsoleCollector(server_ip=server_ip, brand=brand)
        results = await collector.collect_all(devices)
        
        # 分析采集结果
        success = sum(1 for r in results if "error" not in r)
        return {
            "ok": True,
            "total": len(results),
            "success": success,
            "failed": len(results) - success,
            "results": results,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
