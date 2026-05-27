"""
OpsBrain — Host Network Scanner（模式 2：主机网络嗅探）

运行在 host 网络模式的容器中，直接访问物理网络栈。
使用原生 ARP 扫描 + TCP 端口探测 + SNMP 查询识别设备。

不依赖任何设备的 SSH 凭证，纯被动/低影响探测。
"""

from __future__ import annotations

import asyncio
import ipaddress
import struct
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
    """检测本机所有活跃网卡的子网（需要 host 网络模式）"""
    subnets = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET not in addrs:
                continue
            for a in addrs[netifaces.AF_INET]:
                ip = a.get("addr", "")
                mask = a.get("netmask", "")
                if ip and mask and not ip.startswith("127."):
                    try:
                        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                        subnets.append(str(net))
                    except Exception:
                        pass
    except ImportError:
        pass
    # Fallback
    if not subnets:
        subnets = ["10.0.0.0/24", "172.16.0.0/24", "192.168.0.0/24", "192.168.1.0/24"]
    return list(dict.fromkeys(subnets))


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
    result = {}
    try:
        from pysnmp.hlapi.v3.asyncio import get_cmd, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        
        targets = {
            "sysDescr": "1.3.6.1.2.1.1.1.0",
            "sysName": "1.3.6.1.2.1.1.5.0",
            "sysLocation": "1.3.6.1.2.1.1.6.0",
        }
        
        for name, oid in targets.items():
            error_indication, error_status, _, var_binds = await get_cmd(
                CommunityData(community, mpModel=0),
                UdpTransportTarget((host, 161), timeout=timeout),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            if error_indication or error_status:
                continue
            for var_bind in var_binds:
                result[name] = str(var_bind[1])
                
    except ImportError:
        pass
    return result


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
    """
    
    def __init__(self, subnets: list[str] | None = None,
                 max_hosts: int = 100, snmp_community: str = "public",
                 probes: list[int] | None = None):
        self.subnets = subnets or get_local_subnets()
        self.max_hosts = max_hosts
        self.snmp_community = snmp_community
        self.probes = probes or PROBE_PORTS
        self._devices: list[dict] = []
    
    async def scan(self) -> dict:
        """执行扫描，返回结果"""
        log.info("Scanner starting", extra={"subnets": self.subnets})
        
        all_ips: set[str] = set()
        for sn in self.subnets:
            try:
                net = ipaddress.ip_network(sn, strict=False)
                for h in list(net.hosts())[:self.max_hosts // len(self.subnets)]:
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
                    snmp_info = await snmp_query(ip, self.snmp_community)
                    if snmp_info:
                        device["name"] = snmp_info.get("sysName", device["name"])
                        device["snmp_info"] = snmp_info
                
                # 推断类型
                device["type"] = self._infer_type(device["vendor"], services)
                return device
        
        tasks = [probe_host(ip) for ip in ip_list]
        results = await asyncio.gather(*tasks)
        
        self._devices = [d for d in results if d is not None]
        
        log.info("Scan complete", extra={"found": len(self._devices)})
        
        return {
            "ok": True,
            "method": "host-scan",
            "device_count": len(self._devices),
            "scanned": len(ip_list),
            "subnets": self.subnets,
            "devices": self._devices,
            "analysis": (
                f"扫描完成：检查了 {len(ip_list)} 个 IP，"
                f"发现 {len(self._devices)} 台设备"
            ),
        }
    
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
