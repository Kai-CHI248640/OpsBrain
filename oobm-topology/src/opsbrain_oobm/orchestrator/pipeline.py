"""
OpsBrain OOBM — Pipeline Orchestrator

全流程编排器。协调 Inventory → Collector → Parser → Topology Builder → Renderer 的完整流水线。
支持全量 / 增量 / 仅采集 / 仅拓扑 四种模式。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..config import config
from ..logging_setup import get_logger
from .state_machine import Phase, PipelineState

log = get_logger(__name__)


class Pipeline:
    """
    Pipeline 编排器
    管理整个发现流程的执行
    """

    def __init__(self, mode: str = "full"):
        self.mode = mode
        self.state = PipelineState.load()
        self.state.mode = mode
        self.state.save()

        # 路径
        home = config.home_dir
        self._inventory_file = config.inventory_file
        self._inventory_json = config.inventory_output
        self._collected_dir = config.collected_dir
        self._parsed_dir = config.parsed_dir
        self._output_dir = config.output_dir

    def execute(self) -> dict:
        """执行 Pipeline"""
        start_time = __import__("time").monotonic()
        error: str | None = None

        try:
            if self.mode == "full":
                self._full_pipeline()
            elif self.mode == "collect":
                self._collect_only()
            elif self.mode == "topology":
                self._topology_only()
            elif self.mode == "incremental":
                self._incremental_pipeline()
            else:
                error = f"Unknown pipeline mode: {self.mode}"

        except Exception as e:
            error = str(e)
            self.state.set_error(error)
            log.exception("Pipeline failed")

        duration = __import__("time").monotonic() - start_time
        status = "failed" if error else "success"

        return {
            "status": status,
            "mode": self.mode,
            "duration_seconds": round(duration, 2),
            "error": error,
        }

    # ── Pipeline Variants ─────────────────────────────────────────────

    def _full_pipeline(self) -> None:
        """全量 Pipeline"""
        self.state.transition(Phase.LOADING)
        self._load_inventory()

        self.state.transition(Phase.COLLECTING)
        self._run_collection()

        self.state.transition(Phase.CONVERGING)
        self._converge()

        self.state.transition(Phase.PARSING)
        self._parse_results()

        self.state.transition(Phase.LINKING)
        self._build_topology()

        self.state.transition(Phase.RENDERING)
        self._render_topology()

        self.state.transition(Phase.DONE)

    def _collect_only(self) -> None:
        """仅采集"""
        self.state.transition(Phase.LOADING)
        self._load_inventory()

        self.state.transition(Phase.COLLECTING)
        self._run_collection()

        self.state.transition(Phase.DONE)

    def _topology_only(self) -> None:
        """仅拓扑构建（基于已有采集数据）"""
        self.state.transition(Phase.PARSING)
        self._parse_results()

        self.state.transition(Phase.LINKING)
        self._build_topology()

        self.state.transition(Phase.RENDERING)
        self._render_topology()

        self.state.transition(Phase.DONE)

    def _incremental_pipeline(self) -> None:
        """
        增量 Pipeline
        只采集新发现的设备 + uptime 有变化的设备
        与已有拓扑合并
        """
        log.info("Starting incremental pipeline")

        # 1. 检查已有采集数据
        before_topology = self._output_dir / "topology.json"

        # 2. 只采集新设备
        self.state.transition(Phase.COLLECTING)
        new_devices = self._discover_new_devices()

        if new_devices:
            # 增量采集
            from ..inventory.loader import InventoryLoader
            existing = InventoryLoader.load_json(self._inventory_json)
            existing.extend(new_devices)

            # 重新执行全量采集（但数据量小，只新增）
            self._run_collection(devices_override=new_devices)
        else:
            log.info("No new devices discovered")

        # 3. 重新构建拓扑
        self.state.transition(Phase.PARSING)
        self._parse_results()

        self.state.transition(Phase.LINKING)
        self._build_topology()

        self.state.transition(Phase.RENDERING)
        self._render_topology()

        # 4. 与上次拓扑比较
        if before_topology.exists():
            from ..topology.diff import TopologyDiff
            diffs = TopologyDiff(before_topology, self._output_dir / "topology.json")
            changes = diffs.compare()
            log.info("Incremental changes", extra={"change_count": len(changes)})

        self.state.transition(Phase.DONE)

    # ── Steps ────────────────────────────────────────────────────────

    def _load_inventory(self) -> None:
        """加载设备清单"""
        from ..inventory.loader import InventoryLoader

        if not self._inventory_file.exists():
            log.warning("Inventory file not found",
                        extra={"path": str(self._inventory_file)})
            return

        loader = InventoryLoader(self._inventory_file)
        devices = loader.load()
        loader.save(devices, self._inventory_json)

        self.state.total_devices = len(devices)
        self.state.update_counts(collected=0)
        log.info("Inventory loaded",
                 extra={"device_count": len(devices)})

    def _run_collection(
        self, devices_override: list[dict] | None = None
    ) -> None:
        """执行采集"""
        from ..inventory.loader import InventoryLoader
        from ..collector.pool import CollectorPool

        if devices_override:
            devices_source = devices_override
        else:
            devices_source = InventoryLoader.load_json(self._inventory_json)

        if not devices_source:
            log.warning("No devices to collect")
            return

        pool = CollectorPool(
            devices=devices_source,
            output_dir=self._collected_dir,
            max_workers=config.workers,
            max_retries=config.ssh_retries,
            backoff_strategy=config.ssh_backoff.value,
            max_discovery_rounds=config.max_discovery_rounds,
            on_progress=self._on_collect_progress,
        )
        results = pool.run()

        self.state.update_counts(
            collected=results["success"],
            failed=results["failed"],
            discovered=results["discovered"],
        )

    def _converge(self) -> None:
        """收敛阶段 — 检查是否有新发现设备需要继续采集"""
        discovered_file = self._collected_dir / "_discovered.json"
        if not discovered_file.exists():
            return

        import json
        with open(discovered_file, "r") as f:
            discovered = json.load(f)

        if discovered:
            log.info("Discovered devices pending collection",
                     extra={"count": len(discovered)})

    def _parse_results(self) -> None:
        """解析所有采集结果"""
        from ..parser.engine import parse_collected_data
        import json

        count = 0
        for f in sorted(self._collected_dir.iterdir()):
            if f.suffix != ".json" or f.name.startswith("_"):
                continue

            with open(f, "r") as fh:
                raw = json.load(fh)

            device_name = raw.get("device_name", f.stem)
            vendor = raw.get("vendor", "cisco")

            parsed = parse_collected_data(device_name, raw, vendor)

            parsed_path = self._parsed_dir / f"{device_name}.json"
            parsed_path.parent.mkdir(parents=True, exist_ok=True)
            with open(parsed_path, "w") as pf:
                json.dump(parsed, pf, indent=2, ensure_ascii=False)

            count += 1

        self.state.update_counts(parsed=count)
        log.info("Parsed collection results", extra={"count": count})

    def _build_topology(self) -> None:
        """构建拓扑"""
        from ..topology.builder import TopologyBuilder

        builder = TopologyBuilder(
            collected_dir=self._collected_dir,
            parsed_dir=self._parsed_dir,
            output_dir=self._output_dir,
        )
        builder.build()

        summary = builder.summary()
        log.info("Topology built",
                 extra={
                     "devices": summary["total_devices"],
                     "links": summary["confirmed_links"],
                     "unconfirmed": summary["unconfirmed_links"],
                 })

    def _render_topology(self) -> None:
        """渲染拓扑输出"""
        from ..topology.builder import TopologyBuilder

        builder = TopologyBuilder(
            collected_dir=self._collected_dir,
            parsed_dir=self._parsed_dir,
            output_dir=self._output_dir,
        )
        builder.save_output(formats=config.output_formats)

    def _discover_new_devices(self) -> list[dict]:
        """发现新设备（增量模式用）"""
        return []

    def _on_collect_progress(
        self, success: int, total: int, device_name: str
    ) -> None:
        """采集进度回调"""
        self.state.update_counts(collected=success)
