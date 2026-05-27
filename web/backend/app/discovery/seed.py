"""
OpsBrain — Seed Device Discovery (模式 1)

原理：从一台已知设备开始，SSH 登录后通过 LLDP/CDP 递归发现全网拓扑。
自动适配 Cisco/华为/H3C/Juniper/FortiGate/锐捷/HPE 厂商命令。

流程：
  用户提供种子设备 → SSH 采集 → 解析 LLDP 邻居 → 递归发现 → 双向链路确认
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

from logging_setup import get_logger

log = get_logger(__name__)


# ═══ 厂商命令集 ═══════════════════════════════════════════════════════

VENDOR_COMMANDS = {
    "cisco": {
        "enter": "enable",
        "lldp_neighbors": "show lldp neighbors detail",
        "cdp_neighbors": "show cdp neighbors detail",
        "version": "show version",
        "mac_table": "show mac address-table",
        "interfaces": "show ip interface brief",
    },
    "huawei": {
        "enter": "system-view",
        "lldp_neighbors": "display lldp neighbor-information",
        "version": "display version",
        "mac_table": "display mac-address",
        "interfaces": "display ip interface brief",
    },
    "h3c": {
        "enter": "system-view",
        "lldp_neighbors": "display lldp neighbor-information",
        "version": "display version",
        "mac_table": "display mac-address",
        "interfaces": "display ip interface brief",
    },
    "juniper": {
        "enter": "",
        "lldp_neighbors": "show lldp neighbors detail",
        "version": "show version",
        "interfaces": "show interfaces terse",
    },
    "fortinet": {
        "enter": "",
        "lldp_neighbors": "diagnose lldprx neighbor list",
        "version": "get system status",
        "interfaces": "get system interface physical",
    },
    "ruijie": {
        "enter": "enable",
        "lldp_neighbors": "show lldp neighbors detail",
        "cdp_neighbors": "show cdp neighbors detail",
        "version": "show version",
        "interfaces": "show interface status",
    },
    "hpe": {
        "enter": "enable",
        "lldp_neighbors": "show lldp neighbors detail",
        "version": "show version",
        "interfaces": "show interfaces brief",
    },
}

# LLDP 输出解析正则（通用格式）
# Device ID: Core-SW-01
# Local Interface: gi1/0/1
# Remote Interface: gi0/2
# 或: Interface: gi0/2, via: gi1/0/1
LLDP_ENTRY_RE = re.compile(
    r"(?:Device\s*[Ii][Dd]\s*[:=]\s*(\S+))"
    r"(?:.*?)"
    r"(?:Local\s+[Ii]nterface\s*[:=]\s*(\S+))"
    r"(?:.*?)"
    r"(?:Remote\s+[Ii]nterface\s*[:=]\s*(\S+))",
    re.DOTALL
)

LLDP_SIMPLE_RE = re.compile(
    r"(?:Interface\s*:\s*(\S+).*?via\s*:\s*(\S+))"
    r"|(?:(\S+)\s+has\s+(\S+)\s+on\s+(\S+))"
)


# ═══ 数据结构 ════════════════════════════════════════════════════════

class DiscoveredDevice:
    """被发现的设备"""
    def __init__(self, name: str, ip: str, vendor: str = "unknown",
                 model: str = "", via: str = "", collected: bool = False):
        self.name = name
        self.ip = ip
        self.vendor = vendor
        self.model = model
        self.via = via        # 通过哪个设备发现的
        self.collected = collected  # 是否已完成采集
        self.neighbors: list[dict] = []
        self.interfaces: list[dict] = []

    def to_dict(self):
        return {
            "name": self.name, "ip": self.ip,
            "vendor": self.vendor, "model": self.model,
            "collected": self.collected,
            "neighbor_count": len(self.neighbors),
        }


class TopologyLink:
    """双向确认的拓扑链路"""
    def __init__(self, a_name: str, a_port: str, b_name: str, b_port: str,
                 confirmed: bool = False):
        self.a_name = a_name
        self.a_port = a_port
        self.b_name = b_name
        self.b_port = b_port
        self.confirmed = confirmed

    def to_dict(self):
        return {
            "source": self.a_name, "source_port": self.a_port,
            "target": self.b_name, "target_port": self.b_port,
            "confirmed": self.confirmed,
        }


# ═══ SSH 采集引擎（轻量，无需 paramiko 同步问题） ═══════════════

async def ssh_collect(host: str, username: str, password: str,
                      vendor: str, port: int = 22,
                      enable_password: str = "",
                      timeout: int = 15) -> dict:
    """
    SSH 到设备执行采集命令（使用 paramiko，在 executor 中运行避免阻塞事件循环）。
    """
    cmds = VENDOR_COMMANDS.get(vendor, {})
    if not cmds:
        return {"error": f"Unsupported vendor: {vendor}"}

    def _run():
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port, username, password,
                       timeout=timeout, allow_agent=False, look_for_keys=False)
        result = {}
        if cmds.get("enter"):
            try:
                _, stdout, _ = client.exec_command(cmds["enter"], timeout=timeout)
                stdout.read()
            except Exception:
                pass
        for cmd_key, cmd in cmds.items():
            if cmd_key == "enter":
                continue
            try:
                _, stdout, _ = client.exec_command(cmd, timeout=timeout)
                result[cmd_key] = stdout.read().decode(errors="replace")
            except Exception as e:
                log.warning("Command failed", extra={
                    "cmd": cmd_key, "host": host, "error": str(e)
                })
                result[cmd_key] = ""
        client.close()
        return result

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run)
    except Exception as e:
        return {"error": f"SSH failed: {str(e)}"}


# ═══ LLDP 解析 ═══════════════════════════════════════════════════════

def parse_lldp_output(output: str) -> list[dict]:
    """
    解析 LLDP/CDP 输出，提取邻居设备名、本地端口、对端端口。
    支持 Cisco / 华为 / Juniper 等多种格式。
    """
    neighbors = []

    if not output or len(output) < 10:
        return neighbors

    # 尝试逐行解析
    current = {}
    for line in output.split("\n"):
        line = line.strip()

        # Device ID: Core-SW-01 或 Device ID: core-sw-01 (xx:xx:xx:xx:xx:xx)
        m = re.match(r"Device\s+[Ii][Dd]\s*:\s*(\S+)", line)
        if m:
            if current and current.get("device_id"):
                neighbors.append(current)
            current = {"device_id": m.group(1).rstrip(")")}

        # Local Interface: gi1/0/1
        m = re.match(r"(?:Local\s+)?[Ii]nterface\s*:\s*(\S+)", line)
        if m and current is not None:
            current["local_interface"] = m.group(1)

        # Port id: gi0/2 或 Remote Interface: gi0/2
        m = re.match(r"(?:Port\s+[Ii]d|Remote\s+[Ii]nterface)\s*:\s*(\S+)", line)
        if m and current is not None:
            current["remote_interface"] = m.group(1)

    if current and current.get("device_id"):
        neighbors.append(current)

    # 华为格式：Neighbor index : 1, Neighbor : Dist-SW-01
    if not neighbors:
        hw_matches = re.finditer(
            r"Neighbor\s+(?:index\s*:\s*\d+\s*,\s*)?:?\s*(\S+).*?"
            r"Port\s+(?:ID\s*)?:?\s*(\S+).*?"
            r"Local\s+(?:Port\s*)?:?\s*(\S+)",
            output, re.DOTALL
        )
        for m in hw_matches:
            neighbors.append({
                "device_id": m.group(1),
                "local_interface": m.group(3),
                "remote_interface": m.group(2),
            })

    # FortiGate 格式：port1: Dist-SW-01 via gi0/24
    if not neighbors:
        fg_matches = re.finditer(
            r"(\S+?)\s*:\s*(\S+)\s+via\s+(\S+)",
            output
        )
        for m in fg_matches:
            neighbors.append({
                "device_id": m.group(2),
                "local_interface": m.group(1),
                "remote_interface": m.group(3),
            })

    return neighbors


def identify_vendor_from_version(version_output: str) -> str:
    """根据 show version 输出判断厂商"""
    vl = version_output.lower()
    if "cisco" in vl or "ios" in vl or "catalyst" in vl or "nexus" in vl:
        return "cisco"
    if "huawei" in vl or "vrp" in vl:
        return "huawei"
    if "h3c" in vl or "comware" in vl:
        return "h3c"
    if "juniper" in vl or "junos" in vl:
        return "juniper"
    if "fortinet" in vl or "fortigate" in vl or "fgt_" in vl:
        return "fortinet"
    if "ruijie" in vl or "rg-" in vl:
        return "ruijie"
    if "hpe" in vl or "provision" in vl or "aruba" in vl:
        return "hpe"
    return "unknown"


# ═══ 种子发现引擎 ═══════════════════════════════════════════════════

class SeedDiscovery:
    """
    种子设备发现引擎

    用法:
        engine = SeedDiscovery(
            seeds=[{"ip": "10.0.0.1", "username": "admin", "password": "***", "vendor": "cisco"}],
            max_devices=50, max_depth=5
        )
        result = await engine.run()
    """

    def __init__(self, seeds: list[dict], max_devices: int = 50,
                 max_depth: int = 5, global_password: str = ""):
        self.seeds = seeds
        self.max_devices = max_devices
        self.max_depth = max_depth
        self.global_password = global_password

        self._devices: dict[str, DiscoveredDevice] = {}  # name → device
        self._ip_index: dict[str, str] = {}                # ip → name
        self._links: list[TopologyLink] = []
        self._pending: list[dict] = []                     # 待采集的队列

    async def run(self) -> dict:
        """执行种子发现，返回拓扑结果"""
        log.info("Starting seed discovery", extra={"seeds": len(self.seeds)})

        # Step 1: 初始化种子设备
        for seed in self.seeds:
            dev = DiscoveredDevice(
                name=seed.get("name", f"Seed-{seed['ip']}"),
                ip=seed["ip"],
                vendor=seed.get("vendor", "unknown"),
                via="seed",
            )
            self._devices[dev.name] = dev
            self._ip_index[dev.ip] = dev.name
            self._pending.append(seed)

        # Step 2: 递归采集
        depth = 0
        while self._pending and len(self._devices) < self.max_devices and depth < self.max_depth:
            batch = list(self._pending)
            self._pending = []
            depth += 1

            log.info("Discovery round", extra={"depth": depth, "batch": len(batch)})

            # 并发采集
            tasks = [self._collect_one(d) for d in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    log.warning("Collection error", extra={"error": str(result)})
                    continue

        # Step 3: 构建拓扑
        self._build_topology()

        # Step 4: 生成输出
        return self._to_result()

    async def _collect_one(self, device_info: dict):
        """采集一台设备"""
        ip = device_info["ip"]
        username = device_info.get("username", "admin")
        password = device_info.get("password", self.global_password)
        vendor = device_info.get("vendor", "unknown")
        name = self._ip_index.get(ip, f"Device-{ip}")

        dev = self._devices.get(name)
        if not dev:
            dev = DiscoveredDevice(name=name, ip=ip, vendor=vendor)
            self._devices[name] = dev
            self._ip_index[ip] = name

        if dev.collected:
            return

        log.info("Collecting", extra={"device": name, "ip": ip, "vendor": vendor})

        # SSH 采集
        result = await ssh_collect(ip, username, password, vendor)

        if "error" in result:
            log.warning("Collect failed", extra={"device": name, "error": result["error"]})
            return

        # 识别厂商（如果之前的未知）
        version_out = result.get("version", "")
        if dev.vendor == "unknown" and version_out:
            dev.vendor = identify_vendor_from_version(version_out)

        # 解析 LLDP 邻居
        lldp_out = result.get("lldp_neighbors", "")
        cdp_out = result.get("cdp_neighbors", "")
        neighbors = parse_lldp_output(lldp_out) + parse_lldp_output(cdp_out)
        dev.neighbors = neighbors

        # 处理发现的邻居
        for nb in neighbors:
            nb_name = nb.get("device_id", "")
            if not nb_name or nb_name in self._devices:
                continue
            if len(self._devices) >= self.max_devices:
                break

            # 新设备加入队列
            new_dev = DiscoveredDevice(
                name=nb_name, ip="", vendor="unknown",
                via=f"{name}:{nb.get('local_interface', '?')}"
            )
            self._devices[nb_name] = new_dev
            self._pending.append({
                "name": nb_name,
                "ip": nb_name,  # 先用设备名当 IP，后续看能否解析
                "username": username,
                "password": password,
                "vendor": "unknown",
            })

        dev.collected = True
        log.info("Collect done", extra={
            "device": name, "neighbors": len(neighbors),
            "total": len(self._devices),
        })

    def _build_topology(self):
        """构建双向确认的拓扑链路"""
        # 收集所有单向链路
        one_way: list[tuple[str, str, str, str]] = []  # (a_name, a_port, b_name, b_port)

        for name, dev in self._devices.items():
            for nb in dev.neighbors:
                nb_name = nb.get("device_id", "")
                local_port = nb.get("local_interface", "?")
                remote_port = nb.get("remote_interface", "?")
                one_way.append((name, local_port, nb_name, remote_port))

        # 双向确认
        used = set()
        for a_name, a_port, b_name, b_port in one_way:
            key = tuple(sorted([a_name, b_name]))
            if key in used:
                continue

            # 检查反向链路是否存在
            reverse = (b_name, b_port, a_name, a_port)
            confirmed = reverse in one_way

            # 检查是否有反向链路但端口不同（部分确认）
            if not confirmed:
                for ow in one_way:
                    if ow[0] == b_name and ow[2] == a_name:
                        confirmed = True
                        break

            used.add(key)
            self._links.append(TopologyLink(
                a_name=a_name, a_port=a_port,
                b_name=b_name, b_port=b_port,
                confirmed=confirmed,
            ))

    def _to_result(self) -> dict:
        """生成最终结果"""
        devices = [d.to_dict() for d in self._devices.values()]
        links = [l.to_dict() for l in self._links]

        # 生成 Mermaid 拓扑图
        mermaid_lines = ["graph LR"]
        for l in self._links:
            style = "-." if not l.confirmed else "---"
            mermaid_lines.append(
                f"  {l.a_name}{style}|\"{l.a_port} ↔ {l.b_port}\"|{l.b_name}"
            )
        mermaid_code = "\n".join(mermaid_lines)

        return {
            "ok": True,
            "method": "seed",
            "device_count": len(devices),
            "link_count": len(links),
            "confirmed_links": sum(1 for l in self._links if l.confirmed),
            "unconfirmed_links": sum(1 for l in self._links if not l.confirmed),
            "devices": devices,
            "links": links,
            "mermaid_code": mermaid_code,
            "analysis": (
                f"种子发现完成：发现 {len(devices)} 台设备，"
                f"{len(links)} 条链路"
                f"（已确认 {sum(1 for l in self._links if l.confirmed)} 条）"
            ),
        }
