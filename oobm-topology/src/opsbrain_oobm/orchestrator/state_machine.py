"""
OpsBrain OOBM — Pipeline State Machine

管理发现流程的各个阶段转换。
IDLE → LOADING → COLLECTING → CONVERGING → PARSING → LINKING → RENDERING → DONE
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from ..logging_setup import get_logger

log = get_logger(__name__)

STATE_FILE = "/var/lib/opsbrain/state.json"


class Phase(str, Enum):
    IDLE = "idle"
    LOADING = "loading"
    COLLECTING = "collecting"
    CONVERGING = "converging"
    PARSING = "parsing"
    LINKING = "linking"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


class PipelineState:
    """
    Pipeline 状态机
    持久化到文件，支持中断恢复
    """

    def __init__(self):
        self.phase: Phase = Phase.IDLE
        self.mode: str = "full"
        self.current_round: int = 0
        self.total_devices: int = 0
        self.collected_count: int = 0
        self.parsed_count: int = 0
        self.failed_count: int = 0
        self.discovered_count: int = 0
        self.started_at: Optional[str] = None
        self.updated_at: Optional[str] = None
        self.error: Optional[str] = None
        self._dirty: bool = False

    def transition(self, new_phase: Phase) -> None:
        """状态转换"""
        valid = self._valid_transition(self.phase, new_phase)
        if not valid:
            log.warning(
                "Invalid state transition",
                extra={"from": self.phase.value, "to": new_phase.value},
            )
            return

        old_phase = self.phase
        self.phase = new_phase
        self.updated_at = self._now()

        if new_phase == Phase.COLLECTING:
            self.started_at = self.started_at or self._now()

        log.info(
            "Pipeline state transition",
            extra={
                "from": old_phase.value,
                "to": new_phase.value,
                "round": self.current_round,
            },
        )
        self._dirty = True
        self.save()

    def increment_round(self) -> None:
        self.current_round += 1
        self._dirty = True

    def update_counts(
        self,
        collected: int | None = None,
        parsed: int | None = None,
        failed: int | None = None,
        discovered: int | None = None,
    ) -> None:
        if collected is not None:
            self.collected_count = collected
        if parsed is not None:
            self.parsed_count = parsed
        if failed is not None:
            self.failed_count = failed
        if discovered is not None:
            self.discovered_count += discovered
        self.updated_at = self._now()
        self._dirty = True

    def set_error(self, error: str) -> None:
        self.phase = Phase.FAILED
        self.error = error
        self.updated_at = self._now()
        self._dirty = True
        self.save()

    def is_terminal(self) -> bool:
        return self.phase in (Phase.DONE, Phase.FAILED)

    @staticmethod
    def _valid_transition(from_phase: Phase, to_phase: Phase) -> bool:
        transitions = {
            Phase.IDLE: {Phase.LOADING, Phase.COLLECTING},
            Phase.LOADING: {Phase.COLLECTING, Phase.FAILED},
            Phase.COLLECTING: {Phase.CONVERGING, Phase.COLLECTING, Phase.FAILED},
            Phase.CONVERGING: {Phase.PARSING, Phase.COLLECTING, Phase.FAILED},
            Phase.PARSING: {Phase.LINKING, Phase.FAILED},
            Phase.LINKING: {Phase.RENDERING, Phase.FAILED},
            Phase.RENDERING: {Phase.DONE, Phase.FAILED},
            Phase.DONE: set(),
            Phase.FAILED: {Phase.IDLE},
        }
        return to_phase in transitions.get(from_phase, set())

    # ── Persistence ──────────────────────────────────────────────────

    def save(self) -> None:
        """持久化状态到文件"""
        if not self._dirty:
            return
        path = Path(STATE_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "phase": self.phase.value,
            "mode": self.mode,
            "current_round": self.current_round,
            "total_devices": self.total_devices,
            "collected_count": self.collected_count,
            "parsed_count": self.parsed_count,
            "failed_count": self.failed_count,
            "discovered_count": self.discovered_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._dirty = False

    @classmethod
    def load(cls) -> "PipelineState":
        """从文件恢复状态"""
        path = Path(STATE_FILE)
        if not path.exists():
            return cls()

        try:
            with open(path, "r") as f:
                data = json.load(f)
            state = cls()
            state.phase = Phase(data.get("phase", "idle"))
            state.mode = data.get("mode", "full")
            state.current_round = data.get("current_round", 0)
            state.total_devices = data.get("total_devices", 0)
            state.collected_count = data.get("collected_count", 0)
            state.parsed_count = data.get("parsed_count", 0)
            state.failed_count = data.get("failed_count", 0)
            state.discovered_count = data.get("discovered_count", 0)
            state.started_at = data.get("started_at")
            state.updated_at = data.get("updated_at")
            state.error = data.get("error")
            return state
        except Exception as e:
            log.warning("Failed to load state, starting fresh",
                        extra={"error": str(e)})
            return cls()

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat() + "Z"
