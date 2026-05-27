"""
OpsBrain OOBM — Topology Diff

增量更新：对比新旧拓扑，输出变更报告。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger

log = get_logger(__name__)


class TopologyDiff:
    """
    拓扑差异比较器
    增量运行时，对比已有拓扑和最新拓扑的变化
    """

    def __init__(self, before_path: Path, after_path: Path):
        self.before_path = before_path
        self.after_path = after_path
        self._before: dict | None = None
        self._after: dict | None = None

    def compare(self) -> list[dict]:
        """比较新旧拓扑，返回变更列表"""
        self._before = self._load(self.before_path)
        self._after = self._load(self.after_path)

        if not self._before or not self._after:
            log.warning("Cannot compare: one or both topology files missing")
            return []

        changes: list[dict] = []

        # 比较设备
        changes.extend(self._compare_nodes())
        # 比较链路
        changes.extend(self._compare_links())
        # 比较终端设备
        changes.extend(self._compare_end_devices())

        log.info("Topology diff complete", extra={"changes": len(changes)})
        return changes

    def _load(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to load topology", extra={"path": str(path), "error": str(e)})
            return None

    def _compare_nodes(self) -> list[dict]:
        """比较设备节点"""
        changes: list[dict] = []

        before_nodes = {
            n["id"]: n
            for n in (self._before or {}).get("nodes", [])
        }
        after_nodes = {
            n["id"]: n
            for n in (self._after or {}).get("nodes", [])
        }

        before_set = set(before_nodes.keys())
        after_set = set(after_nodes.keys())

        # 新增
        for node_id in after_set - before_set:
            changes.append({
                "type": "added",
                "category": "device",
                "device_id": node_id,
                "description": f"New device discovered: {node_id}",
            })

        # 移除
        for node_id in before_set - after_set:
            changes.append({
                "type": "removed",
                "category": "device",
                "device_id": node_id,
                "description": f"Device removed: {node_id}",
            })

        return changes

    def _compare_links(self) -> list[dict]:
        """比较链路"""
        changes: list[dict] = []

        before_links = self._build_link_set(
            (self._before or {}).get("links", [])
        )
        after_links = self._build_link_set(
            (self._after or {}).get("links", [])
        )

        # 新增链路
        for link in after_links - before_links:
            link_parts = link.split("|||")
            changes.append({
                "type": "added",
                "category": "link",
                "source": link_parts[0] if len(link_parts) > 0 else "",
                "description": f"New link: {link}",
            })

        # 移除链路
        for link in before_links - after_links:
            changes.append({
                "type": "removed",
                "category": "link",
                "description": f"Link removed: {link}",
            })

        return changes

    @staticmethod
    def _build_link_set(links: list[dict]) -> set[str]:
        """将链路列表转为可比较的 set"""
        result = set()
        for link in links:
            key = tuple(sorted([
                f"{link.get('source', '?')}:{link.get('source_port', '')}",
                f"{link.get('target', '?')}:{link.get('target_port', '')}",
            ]))
            result.add("|||".join(key))
        return result

    def _compare_end_devices(self) -> list[dict]:
        """比较终端设备"""
        changes: list[dict] = []

        before = {
            d["name"]: d
            for d in (self._before or {}).get("end_devices", [])
        }
        after = {
            d["name"]: d
            for d in (self._after or {}).get("end_devices", [])
        }

        for name in set(after.keys()) - set(before.keys()):
            changes.append({
                "type": "added",
                "category": "end_device",
                "description": f"New end device: {name}",
            })

        for name in set(before.keys()) - set(after.keys()):
            changes.append({
                "type": "removed",
                "category": "end_device",
                "description": f"End device removed: {name}",
            })

        return changes
