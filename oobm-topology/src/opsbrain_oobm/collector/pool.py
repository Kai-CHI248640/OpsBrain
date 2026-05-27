"""
OpsBrain OOBM — Collector Worker Pool

并发 Worker 池，管理多台设备的并行采集。
支持指数退避重试和进度反馈。
"""

from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Callable, Optional

from ..inventory.loader import InventoryLoader
from ..logging_setup import get_logger
from .engine import CollectorEngine, CollectionResult

log = get_logger(__name__)


class CollectorPool:
    """
    采集器 Worker 池
    管理 N 个并行采集线程，处理重试和发现
    """

    def __init__(
        self,
        devices: list[dict],
        output_dir: Path,
        max_workers: int = 10,
        max_retries: int = 2,
        backoff_strategy: str = "exponential_jitter",
        max_discovery_rounds: int = 3,
        on_progress: Optional[Callable] = None,
    ):
        self._devices = list(devices)
        self._output_dir = output_dir
        self._max_workers = max(1, min(max_workers, 50))
        self._max_retries = max_retries
        self._backoff_strategy = backoff_strategy
        self._max_discovery_rounds = max_discovery_rounds
        self._on_progress = on_progress

        self._results: dict[str, CollectionResult] = {}
        self._failed_devices: list[str] = []
        self._discovered_names: set[str] = set()
        self._lock = threading.Lock()
        self._start_time: float = 0.0

    @property
    def device_names(self) -> list[str]:
        return [d["device_name"] for d in self._devices]

    def run(self) -> dict[str, Any]:
        """
        启动采集流程

        Returns:
            {
                "success": int,
                "failed": int,
                "skipped": int,
                "duration_seconds": float,
                "discovered": int,
                "discovered_files": str | None,
                "failed_devices": list[str],
            }
        """
        self._start_time = time.monotonic()

        all_devices = list(self._devices)
        seen_names = {d["device_name"] for d in all_devices}
        total_discovered = 0

        # ── 多轮采集 ──────────────────────────────────────────────────
        for round_num in range(1, self._max_discovery_rounds + 1):
            if not all_devices:
                break

            log.info("Collection round start",
                     extra={
                         "round": round_num,
                         "devices": len(all_devices),
                         "max_workers": self._max_workers,
                     })

            self._collect_batch(all_devices)

            # 检查是否有新发现设备
            if round_num < self._max_discovery_rounds and self._devices_remaining():
                discovered = self._load_new_devices(seen_names)
                if discovered:
                    all_devices = discovered
                    seen_names.update(d["device_name"] for d in discovered)
                    total_discovered += len(discovered)
                    log.info("Discovered new devices",
                             extra={
                                 "round": round_num,
                                 "count": len(discovered),
                                 "names": [d["device_name"] for d in discovered],
                             })
                else:
                    break
            else:
                break

        # ── 保存发现记录 ──────────────────────────────────────────────
        discovered_file = None
        if self._discovered_names:
            discovered_file = self._output_dir / "_discovered.json"
            with open(discovered_file, "w") as f:
                json.dump(
                    sorted(list(self._discovered_names)),
                    f, indent=2,
                )

        duration = time.monotonic() - self._start_time

        summary = {
            "success": sum(
                1 for r in self._results.values() if r.success
            ),
            "failed": len(self._failed_devices),
            "skipped": sum(
                1 for r in self._results.values()
                if r.status == CollectionResult.STATUS_SKIPPED
            ),
            "duration_seconds": round(duration, 2),
            "discovered": total_discovered,
            "discovered_files": str(discovered_file) if discovered_file else None,
            "failed_devices": list(self._failed_devices),
        }

        log.info("Collection pool complete", extra=summary)
        return summary

    def _collect_batch(self, devices: list[dict]) -> None:
        """并采集一批设备"""
        queue: Queue = Queue()
        for dev in devices:
            queue.put(dev)

        threads: list[threading.Thread] = []
        for _ in range(min(self._max_workers, len(devices))):
            t = threading.Thread(
                target=self._worker_loop,
                args=(queue,),
                daemon=True,
            )
            t.start()
            threads.append(t)

        # 等待所有 Worker 完成
        for t in threads:
            t.join()

    def _worker_loop(self, queue: Queue) -> None:
        """Worker 主循环"""
        while True:
            try:
                device = queue.get_nowait()
            except Empty:
                break

            result = self._collect_device_with_retry(device)

            with self._lock:
                self._results[device["device_name"]] = result

                if result.success:
                    # 可选的进度回调
                    if self._on_progress:
                        success_count = sum(
                            1 for r in self._results.values() if r.success
                        )
                        total = len(self._results)
                        self._on_progress(success_count, total, result.device_name)
                else:
                    self._failed_devices.append(device["device_name"])

            queue.task_done()

    def _collect_device_with_retry(
        self, device: dict
    ) -> CollectionResult:
        """带重试的采集逻辑"""
        last_result: Optional[CollectionResult] = None

        for attempt in range(self._max_retries + 1):
            engine = CollectorEngine(device)
            result = engine.collect()

            if result.success:
                CollectorEngine.save_result(result, self._output_dir)
                return result

            last_result = result

            if attempt < self._max_retries:
                delay = self._compute_backoff(attempt)
                log.warning(
                    "Retrying collection",
                    extra={
                        "device": device["device_name"],
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay": round(delay, 1),
                        "error": result.error,
                    },
                )
                time.sleep(delay)

        # 所有重试都失败
        last_result.status = CollectionResult.STATUS_FAILED
        CollectorEngine.save_result(last_result, self._output_dir)
        return last_result

    def _compute_backoff(self, attempt: int) -> float:
        """计算退避延迟"""
        base = 2.0
        if self._backoff_strategy == "linear":
            return base * (attempt + 1)
        elif self._backoff_strategy == "exponential":
            return base * (2 ** attempt)
        elif self._backoff_strategy == "exponential_jitter":
            delay = base * (2 ** attempt)
            jitter = random.uniform(0, delay * 0.5)
            return delay + jitter
        return 5.0

    def _devices_remaining(self) -> bool:
        """检查是否还有设备未采集（基于文件系统）"""
        collected = set()
        if self._output_dir.exists():
            for f in self._output_dir.iterdir():
                if f.suffix == ".json":
                    collected.add(f.stem)
        device_set = set(self.device_names)
        return bool(device_set - collected)

    def _load_new_devices(
        self, seen: set[str]
    ) -> list[dict]:
        """
        从 LLDP 发现结果中加载新设备
        这里由外部提供清单（或 Agent 决策）
        """
        return []
