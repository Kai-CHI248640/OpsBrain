"""
OpsBrain — Host Network Scanner（模式 2：主机网络嗅探）

运行在 host 网络模式的容器中，直接访问物理网络栈。
使用原生 ARP 扫描 + TCP 端口探测 + SNMP 查询识别设备。

不依赖任何设备的 SSH 凭证，纯被动/低影响探测。
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from typing import Optional

from logging_setup import get_logger

log = get_logger(__name__)


# ═══ 常用端口探测 ═══════════════════════════════════════════════

PROBE_PORTS = [22, 23, 80, 161, 443, 8080, 8443]

VENDOR_BANNERS = {
    "SSH-2.0-Cisco": "cisco",
    "SSH-2.0-Huawei": "huawei",
    "SSH-2.0-H3C": "h3c",
    "SSH-2.0-Juniper": "juniper",
    "SSH-2.0-FortiGate": "fortinet",
    "SSH-2.0-Ruijie": "ruijie",
    "SSH-2.0-Aruba": "hpe",
    "SSH-2.0-OpenSSH": "linux",
}


# ═══ 网络接口检测 ═════════════════════════════════════════════

def get_local_subnets() -> list[str]:
    """检测本机所有活跃网卡的子网（跨平台）"""
    from platform_info import detect_local_subnets
    return detect_local_subnets()


# ═══ TCP 端口探测（async，比 ping 可靠） ═════════════════════

async def tcp_probe(host: str, port: int, timeout: float = 1.5) -> str:
    """
    探测主机端口是否开放。
    返回 "ssh"/"telnet"/"http"/"https"/"snmp"/""（关闭）
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        # 读取 banner 识别服务
        banner = b""
        try:
            banner = await asyncio.wait_for(
                writer.read(256), timeout=0.5
            )
        except (asyncio.TimeoutError, Exception):
            pass
        writer.close()
        await writer.wait_closed()
        
        banner_str = banner.decode(errors="replace").strip()
        return _identify_service(port, banner_str)
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return ""


def _identify_service(port: int, banner: str) -> str:
    """根据端口和 banner 识别服务类型"""
    service_map = {22: "ssh", 23: "telnet", 80: "http", 
                   443: "https", 161: "snmp", 8080: "http", 8443: "https"}
    return service_map.get(port, "")


# ═══ ARP 扫描（需要 root 权限） ═══════════════════════════════

async def arp_scan(subnet: str, timeout: float = 3.0) -> list[dict]:
    """
    ARP 扫描子网，返回活跃主机列表。
    需要 root 权限 + raw socket。
    如果无权限则降级为 TCP 探测。
    """
    hosts = []
    try:
        import pyarp
        net = ipaddress.ip_network(subnet, strict=False)
        for ip in net.hosts():
            mac = pyarp.query(str(ip), timeout=timeout)
            if mac:
                hosts.append({"ip": str(ip), "mac": mac, "source": "arp"})
    except ImportError:
        # pyarp 不可用，降级
        pass
    return hosts


# ═══ SNMP 查询 ════════════════════════════════════════════════

async def snmp_query(host: str, community: str = "public", timeout: float = 2.0) -> dict:
    """SNMP v2c 查询设备基本信息"""
    from .snmp_lldp import get_snmp_sysinfo
    return await get_snmp_sysinfo(host, community)


# ═══ 厂商识别 ═════════════════════════════════════════════════

def identify_vendor(service: str, banner: str = "") -> str:
    """根据服务类型和 banner 识别厂商"""
    if banner:
        for keyword, vendor in VENDOR_BANNERS.items():
            if keyword.lower() in banner.lower():
                return vendor
        # 通用关键字
        bl = banner.lower()
        if "cisco" in bl or "ios" in bl:
            return "cisco"
        if "huawei" in bl or "vrp" in bl:
            return "huawei"
        if "h3c" in bl or "comware" in bl:
            return "h3c"
    return "unknown"


# ═══ 扫描引擎 ═════════════════════════════════════════════════

class NetworkScanner:
    """
    主机网络嗅探引擎。
    优先 ARP 扫描，降级 TCP 探测，尝试 SNMP 识别。
    支持 WeOps 风格的拓扑发现（CDP/LLDP SNMP 查询）。
    """
    
    def __init__(self, subnets: list[str] | None = None,
                 max_hosts: int = 256, snmp_community: str = "public",
                 probes: list[int] | None = None,
                 discovery_method: str = "standard"):  # "standard" or "topology"
        self.subnets = subnets or get_local_subnets()
        self.max_hosts = max_hosts
        self.snmp_community = snmp_community
        self.probes = probes or PROBE_PORTS
        self.discovery_method = discovery_method
        self._devices: list[dict] = []
        self._links: list[dict] = []
    
    async def scan(self) -> dict:
        """执行扫描，返回结果"""
        log.info("Scanner starting", extra={"subnets": self.subnets, "method": self.discovery_method})
        
        all_ips: set[str] = set()
        for sn in self.subnets:
            try:
                net = ipaddress.ip_network(sn, strict=False)
                per_subnet = self.max_hosts // max(len(self.subnets), 1)
                for h in list(net.hosts())[:per_subnet]:
                    all_ips.add(str(h))
            except ValueError:
                all_ips.add(sn)
        
        ip_list = sorted(all_ips)[:self.max_hosts]
        log.info("Scanning hosts", extra={"total": len(ip_list)})
        
        # 并发 TCP 探测
        sem = asyncio.Semaphore(50)  # 控制并发
        
        async def probe_host(ip: str) -> dict | None:
            async with sem:
                services = {}
                for port in self.probes:
                    svc = await tcp_probe(ip, port, timeout=1.0)
                    if svc:
                        services[svc] = port
                if not services:
                    return None
                
                device = {
                    "ip": ip,
                    "services": services,
                    "vendor": "unknown",
                    "type": "unknown",
                    "name": f"Device-{ip}",
                }
                
                # 尝试 SSH banner 识别
                if "ssh" in services:
                    try:
                        r, w = await asyncio.wait_for(
                            asyncio.open_connection(ip, services["ssh"]), timeout=3
                        )
                        banner = (await asyncio.wait_for(r.read(256), timeout=1)).decode(errors="replace")
                        device["vendor"] = identify_vendor("ssh", banner)
                        w.close()
                        await w.wait_closed()
                    except Exception:
                        pass
                
                # 尝试 SNMP
                if "snmp" in services:
                    from .snmp_lldp import get_snmp_sysinfo
                    snmp_info = await get_snmp_sysinfo(ip, self.snmp_community)
                    if snmp_info and "error" not in snmp_info:
                        device["name"] = snmp_info.get("sysName", device["name"])
                        device["vendor"] = snmp_info.get("vendor", device["vendor"])
                        device["snmp_info"] = snmp_info
                
                # 推断类型
                device["type"] = self._infer_type(device["vendor"], services)
                return device
        
        tasks = [probe_host(ip) for ip in ip_list]
        results = await asyncio.gather(*tasks)
        
        devices_with_snmp = [d for d in results if d is not None and "snmp_info" in d]
        self._devices = [d for d in results if d is not None]
        
        log.info("Scan complete", extra={"found": len(self._devices), "snmp_devices": len(devices_with_snmp)})
        
        # 如果启用拓扑发现，尝试获取邻居信息
        if self.discovery_method == "topology" and devices_with_snmp:
            await self._discover_topology(devices_with_snmp)
        
        return {
            "ok": True,
            "method": "host-scan" if self.discovery_method == "standard" else "topology-scan",
            "device_count": len(self._devices),
            "link_count": len(self._links),
            "scanned": len(ip_list),
            "subnets": self.subnets,
            "devices": self._devices,
            "links": self._links,
            "analysis": (
                f"扫描完成：检查了 {len(ip_list)} 个 IP，"
                f"发现 {len(self._devices)} 台设备"
                f"，生成 {len(self._links)} 条拓扑链路"
            ),
        }
    
    async def _discover_topology(self, snmp_devices: list[dict]):
        """从 SNMP 设备获取邻居信息，构建拓扑关系"""
        from .snmp_lldp import get_lldp_neighbors_snmp, get_cdp_neighbors_snmp
        
        all_neighbors = []
        
        for device in snmp_devices:
            ip = device["ip"]
            vendor = device.get("vendor", "unknown")
            
            try:
                # 根据厂商选择邻居发现协议
                if vendor == "cisco":
                    # 思科设备优先使用 CDP
                    neighbors = await get_cdp_neighbors_snmp(ip, self.snmp_community)
                    if not neighbors:
                        # CDP 失败则尝试 LLDP
                        neighbors = await get_lldp_neighbors_snmp(ip, self.snmp_community)
                else:
                    # 其他厂商使用 LLDP
                    neighbors = await get_lldp_neighbors_snmp(ip, self.snmp_community)
                
                for neighbor in neighbors:
                    neighbor["source_device"] = device.get("name", ip)
                    neighbor["source_ip"] = ip
                    all_neighbors.append(neighbor)
                    
            except Exception as e:
                log.warning(f"Failed to get neighbors from {ip}: {e}")
        
        # 构建链路关系
        self._links = self._build_links(all_neighbors)
    
    def _build_links(self, neighbors: list[dict]) -> list[dict]:
        """从邻居信息构建拓扑链路"""
        links = []
        
        for neighbor in neighbors:
            # 确定远程设备信息
            remote_name = neighbor.get("remote_name", "unknown")
            remote_ip = neighbor.get("remote_ip", "")
            remote_port = neighbor.get("remote_port", "unknown")
            
            # 如果远程设备不在已发现设备列表中，添加为未知设备
            if remote_ip and not any(d["ip"] == remote_ip for d in self._devices):
                self._devices.append({
                    "ip": remote_ip,
                    "name": remote_name,
                    "vendor": "unknown",
                    "type": "unknown",
                    "status": "discovered-via-neighbor",
                })
            
            # 创建链路
            link = {
                "source": neighbor.get("source_device", "unknown"),
                "source_port": neighbor.get("local_port", "unknown"),
                "target": remote_name,
                "target_port": remote_port,
                "confirmed": True,  # 从协议获取，确认度高
            }
            links.append(link)
        
        return links
    
    @staticmethod
    def _infer_type(vendor: str, services: dict) -> str:
        """根据服务和厂商推断设备类型"""
        has_ssh = "ssh" in services
        has_http = "http" in services or "https" in services
        has_snmp = "snmp" in services
        
        if vendor in ("cisco", "huawei", "h3c", "ruijie", "hpe"):
            if has_ssh and not has_http:
                return "switch"
            return "router"
        if vendor == "fortinet":
            return "firewall"
        if vendor == "linux" and has_ssh:
            return "server"
        if has_snmp and has_http:
            return "switch"
        if has_http and not has_ssh:
            return "unknown"
        return "unknown"
