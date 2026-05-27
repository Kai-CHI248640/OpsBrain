"""
OpsBrain OOBM — Topology Builder

核心拓扑构建器。实现 Phase 3→4 的关键逻辑：
  1. 加载所有 parsed 数据
  2. 遍历邻居声明，双向确认端口关联
  3. 识别未确认链路
  4. 发现终端设备（从MAC表推断）
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger
from .linker import LinkEngine, TopologyLink
from .renderer import TopologyRenderer

log = get_logger(__name__)


class TopologyBuilder:
    """
    拓扑构建器
    接收采集 + 解析后的数据，构建全网络拓扑
    """

    def __init__(
        self,
        collected_dir: Path,
        output_dir: Path,
        parsed_dir: Path | None = None,
    ):
        self._collected_dir = collected_dir
        self._parsed_dir = parsed_dir or collected_dir.parent / "parsed"
        self._output_dir = output_dir

        self._devices: dict[str, dict] = {}
        self._raw_data: dict[str, dict] = {}
        self._parsed_data: dict[str, dict] = {}
        self._linker = LinkEngine()
        self._renderer = TopologyRenderer()

    # ── Public API ────────────────────────────────────────────────────

    def build(self) -> None:
        """执行完整拓扑构建流程"""
        log.info("Topology build started")

        # 1. 尝试加载 parsed 数据，失败则从 raw 重新解析
        if not self._load_parsed():
            self._parse_from_raw()

        if not self._parsed_data:
            log.warning("No parsed data available")
            return

        # 2. 聚合所有邻居声明
        self._aggregate_declarations()

        # 3. 双向确认
        self._linker.confirm_links()

        # 4. 推断终端设备
        self._discover_end_devices()

        log.info(
            "Topology build complete",
            extra={
                "devices": len(self._parsed_data),
                "confirmed_links": len(self._linker.confirmed_links),
                "unconfirmed_links": len(self._linker.unconfirmed_links),
                "end_devices": len(self._linker.end_devices),
            },
        )

    def save_output(
        self,
        formats: list[str] | None = None,
    ) -> None:
        """保存拓扑输出"""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._renderer.output_dir = self._output_dir

        fmt_list = formats or ["json", "dot", "mermaid"]

        if "json" in fmt_list:
            self._save_json()

        if "dot" in fmt_list:
            self._save_dot()

        if "mermaid" in fmt_list:
            self._save_mermaid()

    def summary(self) -> dict:
        """返回拓扑摘要"""
        return {
            "total_devices": len(self._parsed_data),
            "confirmed_links": len(self._linker.confirmed_links),
            "unconfirmed_links": len(self._linker.unconfirmed_links),
            "end_devices": len(self._linker.end_devices),
            "all_names": list(self._parsed_data.keys()),
        }

    @property
    def confirmed_links(self) -> list[TopologyLink]:
        return self._linker.confirmed_links

    @property
    def unconfirmed_links(self) -> list[TopologyLink]:
        return self._linker.unconfirmed_links

    # ── Data Loading ──────────────────────────────────────────────────

    def _load_parsed(self) -> bool:
        """尝试从 parsed 目录加载已解析的数据"""
        if not self._parsed_dir.exists():
            return False

        loaded = 0
        for f in sorted(self._parsed_dir.iterdir()):
            if f.suffix != ".json":
                continue
            try:
                with open(f, "r") as fh:
                    data = json.load(fh)
                device_name = data.get("device_name", f.stem)
                self._parsed_data[device_name] = data
                loaded += 1
            except Exception as e:
                log.warning("Failed to load parsed data",
                            extra={"file": f.name, "error": str(e)})

        log.info("Loaded parsed data", extra={"count": loaded})
        return loaded > 0

    def _parse_from_raw(self) -> None:
        """从原始采集数据解析"""
        if not self._collected_dir.exists():
            log.warning("Collected directory not found",
                        extra={"path": str(self._collected_dir)})
            return

        from ..parser.engine import parse_collected_data

        count = 0
        for f in sorted(self._collected_dir.iterdir()):
            if f.suffix != ".json" or f.name.startswith("_"):
                continue
            try:
                with open(f, "r") as fh:
                    raw = json.load(fh)

                device_name = raw.get("device_name", f.stem)
                vendor = raw.get("vendor_name", "cisco")

                parsed = parse_collected_data(
                    device_name=device_name,
                    collected_data=raw,
                    vendor=vendor,
                )
                self._parsed_data[device_name] = parsed

                # 保存 parsed 结果
                parsed_path = self._parsed_dir / f"{device_name}.json"
                parsed_path.parent.mkdir(parents=True, exist_ok=True)
                with open(parsed_path, "w") as pf:
                    json.dump(parsed, pf, indent=2, ensure_ascii=False)

                count += 1
            except Exception as e:
                log.warning("Parse failed for raw data",
                            extra={"file": f.name, "error": str(e)})

        log.info("Parsed raw collection data", extra={"count": count})

    # ── Link Aggregation ──────────────────────────────────────────────

    def _aggregate_declarations(self) -> None:
        """聚合所有设备的邻居声明"""
        for device_name, data in self._parsed_data.items():
            neighbors = data.get("neighbors", [])
            for nb in neighbors:
                neighbor_id = nb.get("neighbor_id", "").upper()
                neighbor_id = neighbor_id.rstrip(".")

                self._linker.add_declaration(
                    source_device=device_name,
                    source_port=nb.get("local_port", ""),
                    target_device=neighbor_id,
                    target_port=nb.get("neighbor_port", ""),
                    protocol=nb.get("protocol", "lldp"),
                    speed=nb.get("speed", ""),
                    vlan=nb.get("vlan", ""),
                    platform=nb.get("platform", ""),
                )

        log.info("Neighbor declarations aggregated",
                 extra={"count": len(self._linker.declarations)})

    # ── End Device Discovery ──────────────────────────────────────────

    def _discover_end_devices(self) -> None:
        """从 MAC 表推断终端设备"""
        target_ports: set[str] = set()

        for link in self._linker.confirmed_links:
            # 合法的交换机间链路端口，不标记为终端口
            target_ports.add(f"{link.device_a}:{link.port_a}")
            target_ports.add(f"{link.device_b}:{link.port_b}")

        for device_name, data in self._parsed_data.items():
            mac_entries = data.get("mac_entries", [])
            port_macs: dict[str, set[str]] = defaultdict(set)
            port_vendors: dict[str, str] = {}

            for entry in mac_entries:
                port = entry.get("interface", "")
                # 跳过交换机间链路端口
                if f"{device_name}:{port}" in target_ports:
                    continue
                mac = entry.get("mac", "")
                if mac and port:
                    port_macs[port].add(mac)
                    # 从 MAC 前 6 位判断厂商
                    oui = mac[:8].replace(".", "").upper()[:6]
                    port_vendors[port] = oui

            for port, macs in port_macs.items():
                # 如果某个非互连端口下只有少量 MAC → 终端设备
                if 1 <= len(macs) <= 5:
                    hostname = f"{device_name}_P{port.replace('/', '_')}"
                    self._linker.add_end_device(
                        name=hostname,
                        switch=device_name,
                        switch_port=port,
                        macs=list(macs),
                        mac_count=len(macs),
                    )

    # ── Output ────────────────────────────────────────────────────────

    def _save_json(self) -> None:
        """保存 JSON 格式拓扑"""
        data = {
            "metadata": {
                "total_devices": len(self._parsed_data),
                "confirmed_links": len(self._linker.confirmed_links),
                "unconfirmed_links": len(self._linker.unconfirmed_links),
                "end_devices": len(self._linker.end_devices),
            },
            "nodes": self._build_nodes(),
            "links": [{
                "source": l.device_a,
                "source_port": l.port_a,
                "target": l.device_b,
                "target_port": l.port_b,
                "speed": l.speed,
                "vlan": l.vlan,
                "status": l.status,
                "confirmed": True,
            } for l in self._linker.confirmed_links],
            "unconfirmed": [{
                "source": l.device_a,
                "source_port": l.port_a,
                "target": l.device_b,
                "target_port": l.port_b or "?",
                "status": "unconfirmed",
                "confirmed": False,
            } for l in self._linker.unconfirmed_links],
            "end_devices": [{
                "name": d["name"],
                "connected_to": d["switch"],
                "port": d["switch_port"],
                "macs": d.get("macs", [])[:3],
            } for d in self._linker.end_devices],
        }

        path = self._output_dir / "topology.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info("JSON topology saved", extra={"path": str(path)})

    def _save_dot(self) -> None:
        """保存 Graphviz DOT 格式拓扑"""
        path = self._output_dir / "topology.dot"
        dot = self._renderer.render_dot(
            self._parsed_data,
            self._linker.confirmed_links,
            self._linker.unconfirmed_links,
            self._linker.end_devices,
        )
        with open(path, "w") as f:
            f.write(dot)
        log.info("DOT topology saved", extra={"path": str(path)})

    def _save_mermaid(self) -> None:
        """保存 Mermaid 格式拓扑"""
        path = self._output_dir / "topology.mmd"
        mmd = self._renderer.render_mermaid(
            self._parsed_data,
            self._linker.confirmed_links,
            self._linker.unconfirmed_links,
            self._linker.end_devices,
        )
        with open(path, "w") as f:
            f.write(mmd)
        log.info("Mermaid topology saved", extra={"path": str(path)})

    def _build_nodes(self) -> list[dict]:
        """构建设备节点列表"""
        nodes = []
        for name, data in self._parsed_data.items():
            node = {
                "id": name,
                "type": "network_device",
                "vendor": data.get("vendor", "unknown"),
                "neighbor_count": len(data.get("neighbors", [])),
                "arp_count": len(data.get("arp_entries", [])),
                "mac_count": len(data.get("mac_entries", [])),
            }
            nodes.append(node)
        return nodes
