"""
OpsBrain OOBM — Topology Renderer

拓扑渲染器：输出 DOT / Mermaid / JSON 格式。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .linker import TopologyLink


class TopologyRenderer:
    """拓扑渲染器"""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir

    # ── DOT ──────────────────────────────────────────────────────────

    def render_dot(
        self,
        devices: dict[str, dict],
        confirmed_links: list[TopologyLink],
        unconfirmed_links: list[TopologyLink],
        end_devices: list[dict],
    ) -> str:
        """渲染为 Graphviz DOT"""
        lines = [
            "// OpsBrain OOBM — Network Topology",
            "digraph network {",
            "  rankdir=LR;",
            "  node [shape=box, style=rounded, fontname=Arial, fontsize=10];",
            "  edge [fontname=Arial, fontsize=9];",
            "",
            "  // ── Device Nodes ──",
        ]

        # 设备节点
        for name in sorted(devices.keys()):
            data = devices.get(name, {})
            vendor = data.get("vendor", "?")
            lines.append(f'  "{name}" [label="{name}\\n{vendor}"];')

        # 终端设备（椭圆形）
        for ed in end_devices:
            name = ed["name"]
            lines.append(f'  "{name}" [shape=ellipse, style=dashed, '
                         f'label="{name}"];')
            lines.append(
                f'  "{ed["switch"]}" -> "{name}" '
                f'[label="{ed["switch_port"]}" style=dashed, color=green];'
            )

        lines.append("")

        # ── Confirmed Links ──
        for link in confirmed_links:
            label = f"{link.port_a} ↔ {link.port_b}"
            if link.speed:
                label += f" ({link.speed})"
            if link.vlan:
                label += f" VLAN{link.vlan}"
            lines.append(
                f'  "{link.device_a}" -> "{link.device_b}" '
                f'[label="{label}" color=blue, penwidth=1.5];'
            )

        # ── Unconfirmed Links ──
        for link in unconfirmed_links:
            label = f"{link.port_a} → {link.port_b or '?'}"
            lines.append(
                f'  "{link.device_a}" -> "{link.device_b}" '
                f'[label="{label}" style=dashed, color=orange];'
            )

        lines.append("}")
        return "\n".join(lines)

    # ── Mermaid ──────────────────────────────────────────────────────

    def render_mermaid(
        self,
        devices: dict[str, dict],
        confirmed_links: list[TopologyLink],
        unconfirmed_links: list[TopologyLink],
        end_devices: list[dict],
    ) -> str:
        """渲染为 Mermaid 格式"""
        lines = ["graph LR"]

        # 设备节点
        for name in sorted(devices.keys()):
            clean = name.replace("-", "_").replace(" ", "_")
            lines.append(f"  {clean}[{name}]")

        # 终端设备
        for ed in end_devices:
            clean_name = ed["name"].replace("-", "_").replace(" ", "_")
            clean_sw = ed["switch"].replace("-", "_").replace(" ", "_")
            lines.append(f"  {clean_name}(({ed['name']}))")
            lines.append(
                f"  {clean_sw} -- \"{ed['switch_port']}\" -.-> {clean_name}"
            )

        lines.append("")

        # 确认链路
        for link in confirmed_links:
            a = link.device_a.replace("-", "_")
            b = link.device_b.replace("-", "_")
            label = f"{link.port_a} --- {link.port_b}"
            lines.append(f"  {a} -- \"{label}\" --> {b}")

        # 未确认链路
        for link in unconfirmed_links:
            a = link.device_a.replace("-", "_")
            b = link.device_b.replace("-", "_")
            label = f"{link.port_a} → ?"
            lines.append(f"  {a} -. \"{label}\" .-> {b}")

        return "\n".join(lines)
