"""
OpsBrain Web — Topology Save/Load Routes

当保存拓扑时，自动创建绑定的 Subagent。
"""

from __future__ import annotations

import json as _json
import os
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..database import async_session
from ..models import User, TopologySave, Subagent, ApiKey
from ..services.topology_service import TopologyService
from ..utils.response import ApiResponse, NotFoundException
from .dashboard import get_network_runtime_data

from logging_setup import get_logger

log = get_logger(__name__)
topology_router = APIRouter()


def _now() -> datetime:
    return datetime.utcnow()


def _detect_local_subnets() -> list[str]:
    from platform_info import detect_local_subnets
    return detect_local_subnets()


@topology_router.get("/")
async def list_topologies(user: User = Depends(get_current_user)):
    """列出所有已保存的拓扑"""
    async with async_session() as session:
        service = TopologyService(session)
        topologies = await service.list_topologies()
    return ApiResponse.success(topologies, "查询成功")


@topology_router.post("/")
async def save_topology(data: Dict[str, Any], user: User = Depends(get_current_user)):
    """保存拓扑，并自动创建绑定的 Subagent"""
    async with async_session() as session:
        service = TopologyService(session)
        result = await service.create_topology(data)
    log.info("Topology saved with subagent",
             extra={"name": result["name"], "id": result["id"], "subagent_id": result["subagent_id"]})
    return ApiResponse.success(result, "保存成功")


@topology_router.get("/{topo_id}")
async def get_topology(topo_id: str, user: User = Depends(get_current_user)):
    """获取单个拓扑详情"""
    async with async_session() as session:
        service = TopologyService(session)
        topo = await service.get_topology(topo_id)
    if not topo:
        raise NotFoundException("拓扑不存在")
    return ApiResponse.success(topo, "查询成功")


@topology_router.put("/{topo_id}")
async def update_topology(topo_id: str, data: Dict[str, Any], user: User = Depends(get_current_user)):
    """更新拓扑（名称、设备数据等）"""
    async with async_session() as session:
        service = TopologyService(session)
        result = await service.update_topology(topo_id, data)
    if not result:
        raise NotFoundException("拓扑不存在")
    return ApiResponse.success(result, "更新成功")


@topology_router.delete("/{topo_id}")
async def delete_topology(topo_id: str, user: User = Depends(get_current_user)):
    """删除拓扑及绑定的 Subagent"""
    async with async_session() as session:
        service = TopologyService(session)
        success = await service.delete_topology(topo_id)
    if not success:
        raise NotFoundException("拓扑不存在")

    from .agent import _save_mem
    _save_mem("agent", [])

    return ApiResponse.success({"id": topo_id}, "删除成功")


@topology_router.post("/discover")
async def run_discovery(data: dict):
    """Agent 内部调用的网络嗅探 API（无需认证，仅内部使用）"""
    method = data.get("method", "lan")
    target = data.get("target", "")
    username = data.get("username", "admin")
    password = data.get("password", "")

    try:
        import subprocess, ipaddress, socket, asyncio as _aio
        from platform_info import get_gateway_ip

        target_subnets: list[str] = []
        if target:
            try:
                net = ipaddress.ip_network(target, strict=False)
                target_subnets.append(str(net))
            except ValueError:
                target_subnets.append(target)
        else:
            target_subnets = _detect_local_subnets() or [
                "10.0.0.0/24", "172.16.0.0/24", "192.168.0.0/24", "192.168.1.0/24"]

        hosts: list[str] = []
        for subnet_str in target_subnets[:3]:
            try:
                net = ipaddress.ip_network(subnet_str, strict=False)
                for h in net.hosts():
                    if str(h) not in hosts:
                        hosts.append(str(h))
                    if len(hosts) >= 256:
                        break
            except ValueError:
                hosts.append(subnet_str)
            if len(hosts) >= 256:
                break

        gw = get_gateway_ip()
        if gw and gw not in hosts:
            hosts.insert(0, gw)

        def _batch_ping(ip_list: list[str]) -> list[str]:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            def _ping_one(ip: str) -> str | None:
                try:
                    r = subprocess.run(
                        ["ping", "-n", "1", "-w", "500", ip],
                        capture_output=True, text=True, timeout=3
                    )
                    if "TTL=" in r.stdout:
                        return ip
                except Exception:
                    pass
                return None
            online = []
            with ThreadPoolExecutor(max_workers=60) as pool:
                for result in pool.map(_ping_one, ip_list):
                    if result:
                        online.append(result)
            return online

        loop = _aio.get_running_loop()
        online_ips = await loop.run_in_executor(None, _batch_ping, hosts)
        log.info(f"Ping完成，在线: {len(online_ips)}, IPs: {online_ips[:10]}")

        devices: list[dict] = []
        for ip in online_ips:
            open_ports = {}
            for port, svc_name in [(22, "ssh"), (23, "telnet"), (80, "http"),
                                   (443, "https"), (161, "snmp"), (8080, "http"), (8443, "https")]:
                try:
                    _, w = await _aio.wait_for(_aio.open_connection(ip, port), timeout=1.0)
                    w.close()
                    await w.wait_closed()
                    open_ports[svc_name] = port
                except Exception:
                    pass

            login = "ssh" if "ssh" in open_ports else ("telnet" if "telnet" in open_ports else None)
            dev_type = "unknown"
            if "snmp" in open_ports and ("http" in open_ports or "https" in open_ports):
                dev_type = "router"
            elif "http" in open_ports and not login:
                dev_type = "router"
            devices.append({
                "name": f"Device-{ip}", "ip": ip,
                "type": dev_type, "vendor": "unknown",
                "loginMethod": login,
                "username": username if login else "", "password": password or "" if login else "",
                "status": "online",
                "port": open_ports.get(login, 0) if login else 0,
                "open_ports": open_ports,
            })

        log.info(f"扫描完成，发现 {len(devices)} 台设备")

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

        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        name = data.get("name", "") or f"{method}-发现-{timestamp}"

        return ApiResponse.success({
            "name": name,
            "device_count": len(devices),
            "link_count": len(links),
            "runtime": runtime,
            "analysis": analysis,
            "devices": [{"name": d.get("name","?"), "type": d.get("type","?"),
                         "ip": d.get("ip","?"), "vendor": d.get("vendor","?"),
                         "loginMethod": d.get("loginMethod", "")} for d in devices],
            "device_data": devices,
            "link_data": links,
        }, "发现成功")
    except ImportError as ie:
        return ApiResponse.error(f"缺少依赖模块: {ie}。请确认容器已安装所需 Python 包。")
    except Exception as e:
        return ApiResponse.error(f"嗅探失败: {str(e)}")


@topology_router.post("/discover-seed")
async def run_seed_discovery(data: dict):
    """种子设备发现：从已知设备 SSH 登录，LLDP/CDP 递归发现全拓扑"""
    seeds = data.get("seeds", [])
    max_devices = data.get("max_devices", 50)
    max_depth = data.get("max_depth", 5)

    if not seeds:
        return ApiResponse.error("至少需要一台种子设备")

    try:
        from ..discovery.seed import SeedDiscovery

        engine = SeedDiscovery(
            seeds=seeds,
            max_devices=max_devices,
            max_depth=max_depth,
            global_password=data.get("global_password", ""),
        )
        result = await engine.run()

        async with async_session() as session:
            service = TopologyService(session)
            topo_data = {
                "name": data.get("name", "") or f"种子发现-{datetime.now().strftime('%Y%m%d-%H%M')}",
                "discovery_method": "seed",
                "device_count": result["device_count"],
                "link_count": result["link_count"],
                "device_data": result["devices"],
                "link_data": result["links"],
                "analysis": result.get("analysis", ""),
                "mermaid_code": result.get("mermaid_code", ""),
            }
            topo = await service.create_topology(topo_data)

        result["topo_id"] = topo["id"][:8]
        return ApiResponse.success(result, "发现成功")

    except Exception as e:
        log.error("Seed discovery failed", extra={"error": str(e)})
        return ApiResponse.error(f"种子发现失败: {str(e)}")


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

        async with async_session() as session:
            service = TopologyService(session)
            topo_data = {
                "name": data.get("name", "") or f"网络嗅探-{datetime.now().strftime('%Y%m%d-%H%M')}",
                "discovery_method": "scan",
                "device_count": result["device_count"],
                "link_count": 0,
                "device_data": result.get("devices", []),
                "link_data": [],
                "analysis": result.get("analysis", ""),
                "mermaid_code": "",
            }
            await service.create_topology(topo_data)

        return ApiResponse.success(result, "扫描成功")
    except Exception as e:
        log.error("Scan failed", extra={"error": str(e)})
        return ApiResponse.error(f"网络嗅探失败: {str(e)}")


@topology_router.post("/snmp-discover")
async def run_snmp_discovery(data: dict):
    """基于 SNMP/LLDP/CDP 的拓扑发现（类似 WeOps Topology-Scanner）"""
    target_ips = data.get("targets", [])
    snmp_community = data.get("snmp_community", "public")
    max_depth = data.get("max_depth", 3)

    if not target_ips:
        return ApiResponse.error("至少需要一台目标设备 IP")

    try:
        from ..scanner.snmp_lldp import query_device_lldp, get_cdp_neighbors_snmp

        discovered_devices = {}
        links = []
        queue = [(ip, 0) for ip in target_ips]
        visited = set()

        while queue:
            current_ip, depth = queue.pop(0)

            if current_ip in visited or depth > max_depth:
                continue
            visited.add(current_ip)

            device_info = await query_device_lldp(current_ip, snmp_community)

            if "error" in device_info:
                log.warning(f"Failed to query {current_ip}: {device_info['error']}")
                continue

            discovered_devices[current_ip] = device_info

            for neighbor in device_info.get("neighbors", []):
                remote_ip = neighbor.get("remote_ip", "")
                remote_name = neighbor.get("remote_name", "")

                if not remote_ip and remote_name:
                    try:
                        remote_ip = socket.gethostbyname(remote_name)
                    except:
                        pass

                if remote_ip and remote_ip not in visited:
                    queue.append((remote_ip, depth + 1))

                links.append({
                    "source": current_ip,
                    "target": remote_ip or remote_name,
                    "source_port": neighbor.get("local_port", ""),
                    "target_port": neighbor.get("remote_port", ""),
                    "confirmed": True,
                })

        devices = []
        for ip, info in discovered_devices.items():
            devices.append({
                "name": info.get("name", ip),
                "ip": ip,
                "type": "switch",
                "vendor": info.get("vendor", "unknown"),
                "status": "online",
            })

        async with async_session() as session:
            service = TopologyService(session)
            topo_data = {
                "name": data.get("name", "") or f"SNMP发现-{datetime.now().strftime('%Y%m%d-%H%M')}",
                "discovery_method": "snmp",
                "device_count": len(devices),
                "link_count": len(links),
                "device_data": devices,
                "link_data": links,
                "analysis": f"SNMP发现完成：发现 {len(devices)} 台设备，{len(links)} 条链路",
                "mermaid_code": "",
            }
            topo = await service.create_topology(topo_data)

        return ApiResponse.success({
            "topo_id": topo["id"][:8],
            "name": topo["name"],
            "device_count": len(devices),
            "link_count": len(links),
            "devices": [{"name": d["name"], "ip": d["ip"], "vendor": d["vendor"]} for d in devices[:10]],
            "analysis": f"SNMP发现完成：发现 {len(devices)} 台设备，{len(links)} 条链路",
        }, "发现成功")
    except Exception as e:
        log.error("SNMP discovery failed", extra={"error": str(e)})
        return ApiResponse.error(f"SNMP发现失败: {str(e)}")


@topology_router.post("/console-discover")
async def discover_console_ports(data: dict):
    """串口服务器端口自动发现"""
    server_ip = data.get("ip", "")
    start_port = data.get("start", 2001)
    end_port = data.get("end", 2100)

    if not server_ip:
        return ApiResponse.error("请输入串口服务器 IP")

    try:
        from ..scanner.console import auto_discover_ports
        ports = await auto_discover_ports(server_ip, range(start_port, end_port + 1))
        return ApiResponse.success({
            "active_ports": ports,
            "count": len(ports),
        }, "发现成功")
    except Exception as e:
        return ApiResponse.error(str(e))


@topology_router.post("/console-collect")
async def collect_console_devices(data: dict):
    """串口服务器批量采集"""
    server_ip = data.get("ip", "")
    brand = data.get("brand", "telnet")
    devices = data.get("devices", [])

    if not server_ip:
        return ApiResponse.error("请输入串口服务器 IP")
    if not devices:
        return ApiResponse.error("无设备列表")

    try:
        from ..scanner.console import ConsoleCollector
        collector = ConsoleCollector(server_ip=server_ip, brand=brand)
        results = await collector.collect_all(devices)

        success = sum(1 for r in results if "error" not in r)
        return ApiResponse.success({
            "total": len(results),
            "success": success,
            "failed": len(results) - success,
            "results": results,
        }, "采集完成")
    except Exception as e:
        return ApiResponse.error(str(e))