"""
OpsBrain OOBM — Link Confirmation Engine

核心等待机制的实现：
  1. 收集所有设备声明的邻居关系
  2. 双向匹配端口关联
  3. 标记未确认链路
  4. 推断终端设备
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class TopologyLink:
    """拓扑链路"""
    def __init__(
        self,
        device_a: str,
        port_a: str,
        device_b: str,
        port_b: str = "",
        protocol: str = "lldp",
        speed: str = "",
        vlan: str = "",
        platform: str = "",
        status: str = "up",
        confirmed: bool = False,
    ):
        self.device_a = device_a
        self.port_a = port_a
        self.device_b = device_b
        self.port_b = port_b
        self.protocol = protocol
        self.speed = speed
        self.vlan = vlan
        self.platform = platform
        self.status = status
        self.confirmed = confirmed

    def __repr__(self) -> str:
        return (
            f"Link({self.device_a}:{self.port_a} ↔ "
            f"{self.device_b}:{self.port_b or '?'}"
            f"{' ✓' if self.confirmed else ' ?'})"
        )


class Declaration:
    """单条邻居声明（有向边）"""
    def __init__(
        self,
        source_device: str,
        source_port: str,
        target_device: str,
        target_port: str = "",
        protocol: str = "lldp",
        speed: str = "",
        vlan: str = "",
        platform: str = "",
    ):
        self.source_device = source_device
        self.source_port = source_port
        self.target_device = target_device
        self.target_port = target_port
        self.protocol = protocol
        self.speed = speed
        self.vlan = vlan
        self.platform = platform


class LinkEngine:
    """
    链路确认引擎
    实现双向匹配（Phase 4 核心逻辑）
    """

    def __init__(self):
        self.declarations: list[Declaration] = []
        self.confirmed_links: list[TopologyLink] = []
        self.unconfirmed_links: list[TopologyLink] = []
        self.end_devices: list[dict] = []
        self._link_map: dict[tuple, list[Declaration]] = defaultdict(list)

    # ── Declaration ───────────────────────────────────────────────────

    def add_declaration(
        self,
        source_device: str,
        source_port: str,
        target_device: str,
        target_port: str = "",
        protocol: str = "lldp",
        speed: str = "",
        vlan: str = "",
        platform: str = "",
    ) -> None:
        """添加一条邻居声明"""
        decl = Declaration(
            source_device=source_device.upper(),
            source_port=source_port,
            target_device=target_device.upper(),
            target_port=target_port,
            protocol=protocol,
            speed=speed,
            vlan=vlan,
            platform=platform,
        )
        self.declarations.append(decl)

        # 添加到映射：{(较小的设备名, 较大的设备名)}
        key = tuple(sorted([decl.source_device, decl.target_device]))
        self._link_map[key].append(decl)

    # ── Confirmation ──────────────────────────────────────────────────

    def confirm_links(self) -> None:
        """
        执行双向确认

        对每对设备 (A, B):
          - 找 A→B 的声明（forward）
          - 找 B→A 的声明（reverse）
          - 如果两者都存在 → 双向确认，建立 TopologyLink
          - 如果只有单向 → 标记为未确认
        """
        for key, decls in self._link_map.items():
            device_a, device_b = key

            forward = [
                d for d in decls
                if d.source_device == device_a and d.target_device == device_b
            ]
            reverse = [
                d for d in decls
                if d.source_device == device_b and d.target_device == device_a
            ]

            if forward and reverse:
                self._confirm(forward[0], reverse[0])
            elif forward:
                self._unconfirmed(forward[0])

    def _confirm(self, forward: Declaration, reverse: Declaration) -> None:
        """双向确认 → 建立链路"""
        link = TopologyLink(
            device_a=forward.source_device,
            port_a=forward.source_port,
            device_b=reverse.source_device,
            port_b=reverse.source_port,
            protocol=f"{forward.protocol}+{reverse.protocol}",
            speed=forward.speed or reverse.speed,
            vlan=forward.vlan or reverse.vlan,
            platform=forward.platform or reverse.platform,
            confirmed=True,
        )
        self.confirmed_links.append(link)

    def _unconfirmed(self, decl: Declaration) -> None:
        """单向声明 → 标记未确认"""
        link = TopologyLink(
            device_a=decl.source_device,
            port_a=decl.source_port,
            device_b=decl.target_device,
            port_b=decl.target_port,
            protocol=decl.protocol,
            speed=decl.speed,
            vlan=decl.vlan,
            platform=decl.platform,
            confirmed=False,
        )
        self.unconfirmed_links.append(link)

    # ── End Devices ───────────────────────────────────────────────────

    def add_end_device(
        self,
        name: str,
        switch: str,
        switch_port: str,
        macs: list[str] | None = None,
        mac_count: int = 0,
    ) -> None:
        """添加终端设备"""
        self.end_devices.append({
            "name": name,
            "switch": switch,
            "switch_port": switch_port,
            "macs": macs or [],
            "mac_count": mac_count,
        })

    # ── Export ────────────────────────────────────────────────────────

    def export_declarations(self) -> list[dict]:
        """导出所有声明（调试用）"""
        return [
            {
                "source_device": d.source_device,
                "source_port": d.source_port,
                "target_device": d.target_device,
                "target_port": d.target_port,
                "protocol": d.protocol,
            }
            for d in self.declarations
        ]

    def summary(self) -> dict:
        """链路摘要"""
        return {
            "declarations": len(self.declarations),
            "device_pairs": len(self._link_map),
            "confirmed_links": len(self.confirmed_links),
            "unconfirmed_links": len(self.unconfirmed_links),
            "end_devices": len(self.end_devices),
        }
