"""
OpsBrain OOBM — CLI Output Parser Engine

基于 TextFSM + 正则的设备 CLI 输出解析引擎。
将原始 show/display 命令输出解析为结构化数据。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

from ..logging_setup import get_logger

log = get_logger(__name__)

try:
    import textfsm
    HAS_TEXTFSM = True
except ImportError:
    HAS_TEXTFSM = False
    log.warning("textfsm not installed; falling back to regex parsing")


class ParsedNeighbor:
    """标准化的邻居信息"""
    def __init__(
        self,
        local_device: str,
        local_port: str,
        neighbor_id: str,
        neighbor_port: str,
        protocol: str = "lldp",
        platform: str = "",
        vlan: str = "",
        speed: str = "",
    ):
        self.local_device = local_device
        self.local_port = local_port
        self.neighbor_id = neighbor_id
        self.neighbor_port = neighbor_port
        self.protocol = protocol
        self.platform = platform
        self.vlan = vlan
        self.speed = speed

    def to_dict(self) -> dict:
        return {
            "local_device": self.local_device,
            "local_port": self.local_port,
            "neighbor_id": self.neighbor_id,
            "neighbor_port": self.neighbor_port,
            "protocol": self.protocol,
            "platform": self.platform,
            "vlan": self.vlan,
            "speed": self.speed,
        }


class ParsedARP:
    """标准化的 ARP 表项"""
    def __init__(
        self,
        ip: str,
        mac: str,
        interface: str = "",
        age: str = "",
        type_: str = "",
    ):
        self.ip = ip
        self.mac = mac
        self.interface = interface
        self.age = age
        self.type = type_

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "interface": self.interface,
            "age": self.age,
            "type": self.type,
        }


class ParsedMAC:
    """标准化的 MAC 表项"""
    def __init__(
        self,
        vlan: str,
        mac: str,
        interface: str,
        type_: str = "",
    ):
        self.vlan = vlan
        self.mac = mac
        self.interface = interface
        self.type = type_

    def to_dict(self) -> dict:
        return {
            "vlan": self.vlan,
            "mac": self.mac,
            "interface": self.interface,
            "type": self.type,
        }


class ParserEngine:
    """
    CLI 输出解析引擎
    优先使用 TextFSM 模板，回退使用正则
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        self._templates_dir = templates_dir or Path(
            os.path.join(os.path.dirname(__file__), "textfsm_templates")
        )
        self._fsm_cache: dict[str, textfsm.TextFSM] = {}

    # ── Neighbor Parsing ────────────────────────────────────────────────

    def parse_neighbors(
        self,
        raw_output: str,
        vendor: str,
        protocol: str = "lldp",
        local_device: str = "",
    ) -> list[ParsedNeighbor]:
        """解析 LLDP/CDP 邻居信息"""
        if not raw_output or len(raw_output) < 10:
            return []

        # 尝试 TextFSM
        if HAS_TEXTFSM:
            result = self._parse_with_fsm(
                raw_output, vendor, protocol, "neighbors"
            )
            if result:
                return [
                    ParsedNeighbor(
                        local_device=local_device,
                        local_port=r.get("local_port", ""),
                        neighbor_id=r.get("neighbor_id", ""),
                        neighbor_port=r.get("neighbor_port", ""),
                        protocol=protocol,
                        platform=r.get("platform", ""),
                        vlan=r.get("vlan", ""),
                        speed=r.get("speed", ""),
                    )
                    for r in result
                ]

        # 回退正则
        return self._regex_parse_neighbors(raw_output, vendor, protocol, local_device)

    def _regex_parse_neighbors(
        self,
        raw: str,
        vendor: str,
        protocol: str,
        local_device: str,
    ) -> list[ParsedNeighbor]:
        """正则方式解析邻居信息"""
        neighbors: list[ParsedNeighbor] = []

        if protocol == "lldp":
            # LLDP 通用格式
            # Device ID: xxx
            # Interface: xxx
            # Port ID: xxx
            blocks = re.split(r"---+\n?", raw)

            for block in blocks:
                device_id = self._extract_field(block, r"Device ID[:\s]+(.+)", lines=1)
                local_int = self._extract_field(block, r"Interface[:\s]+(.+)", lines=1)
                port_id = self._extract_field(block, r"Port id[:\s]+(.+)", lines=1)
                platform = self._extract_field(block, r"Platform[:\s]+(.+)", lines=1)
                vlan = self._extract_field(block, r"VLAN[:\s]+(\S+)", lines=1)

                if device_id and local_int:
                    neighbors.append(ParsedNeighbor(
                        local_device=local_device,
                        local_port=local_int.strip(),
                        neighbor_id=device_id.strip().rstrip("."),
                        neighbor_port=port_id.strip() if port_id else "",
                        protocol=protocol,
                        platform=platform.strip() if platform else "",
                        vlan=vlan.strip() if vlan else "",
                    ))

        elif protocol == "cdp":
            # CDP 通用格式
            blocks = re.split(r"-+\n?", raw)

            for block in blocks:
                device_id = self._extract_field(block, r"Device ID[:\s]+(.+)", lines=1)
                local_int = self._extract_field(block, r"Interface[:\s]+(.+)", lines=1)
                port_id = self._extract_field(block, r"Port ID \(outgoing port\)[:\s]+(.+)", lines=1)
                platform = self._extract_field(block, r"Platform[:\s]+(.+)", lines=1)

                if device_id and local_int:
                    neighbors.append(ParsedNeighbor(
                        local_device=local_device,
                        local_port=local_int.strip(),
                        neighbor_id=device_id.strip().rstrip("."),
                        neighbor_port=port_id.strip() if port_id else "",
                        protocol=protocol,
                        platform=platform.strip() if platform else "",
                    ))

        # 华为/H3C display lldp neighbor-information
        if not neighbors:
            system_name = self._extract_field(raw, r"System Name\s+:\s+(.+)")
            local_int = self._extract_field(raw, r"Local Interface\s+:\s+(.+)")
            remote_port = self._extract_field(raw, r"Port ID local\s+:\s+(.+)")
            # 或: Port ID local : xxx
            if not remote_port:
                remote_port = self._extract_field(raw, r"Port ID\s+:\s+(.+)")

            if system_name and local_int:
                neighbors.append(ParsedNeighbor(
                    local_device=local_device,
                    local_port=local_int.strip(),
                    neighbor_id=system_name.strip().rstrip("."),
                    neighbor_port=remote_port.strip() if remote_port else "",
                    protocol=protocol,
                ))

        return neighbors

    # ── ARP Parsing ────────────────────────────────────────────────────

    def parse_arp(
        self, raw_output: str, vendor: str
    ) -> list[ParsedARP]:
        """解析 ARP 表"""
        if not raw_output:
            return []

        entries: list[ParsedARP] = []

        # Cisco 格式:
        # Protocol  Address          Age (min)  Hardware Addr   Type   Interface
        # Internet  10.0.0.1               0    aaaa.bbbb.cccc  ARPA   Vlan1
        cisco_pattern = re.compile(
            r"Internet\s+(\S+)\s+\d+\s+(\S+)\s+\S+\s+(\S+)"
        )
        for match in cisco_pattern.finditer(raw_output):
            ip, mac, interface = match.groups()
            entries.append(ParsedARP(ip=ip, mac=mac, interface=interface))

        # 华为/H3C format:
        # IP Address       MAC Address     Interface
        # 10.0.0.1         aaaa-bbbb-cccc  GE0/0/1
        if not entries:
            hw_pattern = re.compile(
                r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{14,17})\s+(\S+)"
            )
            for match in hw_pattern.finditer(raw_output):
                ip, mac, interface = match.groups()
                mac = mac.replace("-", ":")
                entries.append(ParsedARP(ip=ip, mac=mac, interface=interface))

        return entries

    # ── MAC Table Parsing ──────────────────────────────────────────────

    def parse_mac_table(
        self, raw_output: str, vendor: str
    ) -> list[ParsedMAC]:
        """解析 MAC 地址表"""
        if not raw_output:
            return []

        entries: list[ParsedMAC] = []

        # Cisco:
        # vlan    mac address     type    ports
        #   1     aaaa.bbbb.cccc  STATIC  Gi1/0/1
        cisco_pattern = re.compile(
            r"\s*(\d+)\s+([0-9a-fA-F.]+)\s+(\S+)\s+(\S+)"
        )
        for match in cisco_pattern.finditer(raw_output):
            vlan, mac, type_, port = match.groups()
            if port.lower() in ("cpu",):
                continue
            entries.append(ParsedMAC(
                vlan=vlan, mac=mac, interface=port, type_=type_
            ))

        # 华为/H3C:
        # MAC Address     VLAN  Port
        # aaaa-bbbb-cccc  1     GE0/0/1
        if not entries:
            hw_pattern = re.compile(
                r"([0-9a-fA-F-]{14,17})\s+(\d+)\s+(\S+)"
            )
            for match in hw_pattern.finditer(raw_output):
                mac, vlan, port = match.groups()
                mac = mac.replace("-", ".")
                entries.append(ParsedMAC(vlan=vlan, mac=mac, interface=port))

        return entries

    # ── Route Table Parsing ────────────────────────────────────────────

    def parse_route_table(self, raw_output: str) -> list[dict]:
        """提取路由表信息（仅摘要级, 不细解析每条路由）"""
        if not raw_output:
            return []

        routes: list[dict] = []
        gateway = ""
        for line in raw_output.split("\n"):
            # 找默认路由
            if "0.0.0.0/0" in line or "0.0.0.0" in line:
                parts = line.split()
                for part in parts:
                    if re.match(r"^\d+\.\d+\.\d+\.\d+$", part):
                        gateway = part
                        break

        if gateway:
            routes.append({"default_gateway": gateway})

        return routes

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_field(
        text: str,
        pattern: str,
        lines: int = 0,
    ) -> str:
        """提取字段"""
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_with_fsm(
        self,
        raw_output: str,
        vendor: str,
        protocol: str,
        data_type: str,
    ) -> list[dict]:
        """使用 TextFSM 模板解析"""
        template_name = f"{vendor}_show_{protocol}_{data_type}.textfsm"
        template_path = self._templates_dir / template_name

        if not template_path.exists():
            return []

        fsm = self._load_fsm(template_path)
        if not fsm:
            return []

        try:
            rows = fsm.ParseText(raw_output)
            return [
                dict(zip(fsm.header, row))
                for row in rows
            ]
        except Exception as e:
            log.warning("TextFSM parse failed",
                        extra={"template": template_name, "error": str(e)})
            return []

    def _load_fsm(self, path: Path) -> Optional[textfsm.TextFSM]:
        """加载 TextFSM 模板（缓存）"""
        path_str = str(path)
        if path_str in self._fsm_cache:
            return self._fsm_cache[path_str]

        try:
            with open(path, "r") as f:
                fsm = textfsm.TextFSM(f)
            self._fsm_cache[path_str] = fsm
            return fsm
        except Exception as e:
            log.warning("Failed to load TextFSM template",
                        extra={"path": str(path), "error": str(e)})
            return None


def parse_collected_data(
    device_name: str,
    collected_data: dict,
    vendor: str,
) -> dict:
    """
    解析单台设备的完整采集数据
    返回标准化的结构化数据
    """
    engine = ParserEngine()
    parsed: dict = {
        "device_name": device_name,
        "vendor": vendor,
        "neighbors": [],
        "arp_entries": [],
        "mac_entries": [],
        "routes": [],
        "version": {},
    }

    # 解析邻居
    for cmd_key in ("lldp_neighbors", "cdp_neighbors"):
        cmd_data = collected_data.get("commands", {}).get(cmd_key)
        if cmd_data:
            protocol = "cdp" if "cdp" in cmd_key else "lldp"
            neighbors = engine.parse_neighbors(
                cmd_data.get("stdout", ""),
                vendor,
                protocol=protocol,
                local_device=device_name,
            )
            parsed["neighbors"].extend([n.to_dict() for n in neighbors])

    # 解析 ARP
    for cmd_key in ("show_arp", "display_arp"):
        cmd_data = collected_data.get("commands", {}).get(cmd_key)
        if cmd_data:
            arp_entries = engine.parse_arp(
                cmd_data.get("stdout", ""), vendor
            )
            parsed["arp_entries"].extend([a.to_dict() for a in arp_entries])

    # 解析 MAC
    for cmd_key in ("show_mac_address-table", "show_mac-address-table",
                    "display_mac-address", "show_mac-address-table"):
        cmd_data = collected_data.get("commands", {}).get(cmd_key)
        if cmd_data:
            mac_entries = engine.parse_mac_table(
                cmd_data.get("stdout", ""), vendor
            )
            parsed["mac_entries"].extend([m.to_dict() for m in mac_entries])

    return parsed
