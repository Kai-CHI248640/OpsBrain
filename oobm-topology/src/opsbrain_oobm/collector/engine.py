"""
OpsBrain OOBM — Collection Engine

核心采集引擎。管理一个设备从连接、登录、采集到结果输出的完整生命周期。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from ..logging_setup import get_logger
from ..inventory.commands import VendorCommands
from .session import SSHSession

log = get_logger(__name__)


class CollectionResult:
    """单台设备的采集结果"""
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_TIMEOUT = "timeout"
    STATUS_CONNECTION_ERROR = "connection_error"
    STATUS_AUTH_ERROR = "auth_error"
    STATUS_NO_COMMAND_SET = "no_command_set"

    def __init__(self, device_name: str):
        self.device_name = device_name
        self.status = self.STATUS_PENDING
        self.commands: dict[str, dict] = {}
        self.neighbors: list[dict] = []
        self.duration_seconds: float = 0.0
        self.error: Optional[str] = None
        self.session_log: list[dict] = []

    @property
    def success(self) -> bool:
        return self.status == self.STATUS_SUCCESS

    def to_dict(self) -> dict:
        return {
            "device_name": self.device_name,
            "status": self.status,
            "commands": self.commands,
            "neighbors": self.neighbors,
            "duration_seconds": round(self.duration_seconds, 2),
            "error": self.error,
            "session_log": self.session_log[-10:],  # 只保留最后10条
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


class CollectorEngine:
    """
    采集引擎
    对一台设备执行完整的采集流程
    """

    def __init__(
        self,
        device: dict,
        config: Any = None,
    ):
        self.device = device
        self.device_name = device["device_name"]
        self.vendor = device.get("vendor", "cisco")
        self.config = config
        self._vendor_cmds = VendorCommands()

    def collect(self) -> CollectionResult:
        """执行完整的设备采集流程"""
        result = CollectionResult(self.device_name)
        start = time.monotonic()

        log.info("Starting collection",
                 extra={
                     "device": self.device_name,
                     "vendor": self.vendor,
                     "target": self._console_target(),
                 })

        # Step 1: 检查厂商命令集
        commands = self._vendor_cmds.get_command_list(self.vendor)
        if not commands:
            result.status = CollectionResult.STATUS_NO_COMMAND_SET
            result.error = f"Unsupported vendor: {self.vendor}"
            log.warning("Unsupported vendor",
                        extra={"device": self.device_name, "vendor": self.vendor})
            return result

        # Step 2: SSH 连接
        result.status = CollectionResult.STATUS_IN_PROGRESS

        session = SSHSession(
            host=self.device["console_ip"],
            port=self.device["console_port"],
            username=self.device["username"],
            password=self.device["password"],
            enable_password=self.device.get("enable_password"),
            vendor=self.vendor,
        )

        if not session.connect():
            result.status = CollectionResult.STATUS_CONNECTION_ERROR
            result.error = f"Cannot connect to {self._console_target()}"
            result.duration_seconds = time.monotonic() - start
            return result

        # Step 3: 进入特权模式
        if not session.enter_privileged_mode():
            result.status = CollectionResult.STATUS_AUTH_ERROR
            result.error = "Failed to enter privileged mode"
            result.duration_seconds = time.monotonic() - start
            session.disconnect()
            return result

        # Step 4: 逐个执行采集命令
        failed_commands = 0
        for cmd in commands:
            cmd_result = session.execute_command(cmd)

            result.commands[cmd] = {
                "stdout": cmd_result.stdout,
                "size": len(cmd_result.stdout),
                "duration": round(cmd_result.duration, 2),
                "success": cmd_result.success,
                "error": cmd_result.error,
            }

            if not cmd_result.success:
                failed_commands += 1

            # 短延迟，避免设备响应压力
            time.sleep(0.2)

        # Step 5: 从 LLDP/CDP 输出中解析邻居
        neighbors = self._extract_neighbors(result.commands)
        result.neighbors = neighbors

        # Step 6: 完成
        result.status = CollectionResult.STATUS_SUCCESS if failed_commands == 0 else CollectionResult.STATUS_SUCCESS
        if failed_commands > 0:
            result.status = CollectionResult.STATUS_SUCCESS
            log.warning("Some commands failed",
                        extra={
                            "device": self.device_name,
                            "failed": failed_commands,
                            "total": len(commands),
                        })

        result.session_log = session.session_log
        result.duration_seconds = time.monotonic() - start
        session.disconnect()

        log.info("Collection complete",
                 extra={
                     "device": self.device_name,
                     "commands": len(commands),
                     "failed_commands": failed_commands,
                     "neighbors": len(neighbors),
                     "duration": round(result.duration_seconds, 2),
                 })

        return result

    def _console_target(self) -> str:
        return f"{self.device['console_ip']}:{self.device['console_port']}"

    @staticmethod
    def _extract_neighbors(
        commands: dict[str, dict]
    ) -> list[dict]:
        """
        从 LLDP/CDP 输出中提取邻居信息
        这里做初步提取，详细解析交给 parser 模块
        """
        neighbors: list[dict] = []

        # 检查 LLDP 输出
        for cmd_key in ("lldp_neighbors", "cdp_neighbors"):
            raw = commands.get(cmd_key, {}).get("stdout", "")

            if not raw or len(raw) < 20:
                continue

            # 记录原始数据，供 parser 后续处理
            neighbors.append({
                "source_command": cmd_key,
                "raw_output": raw,
                "raw_length": len(raw),
            })

        return neighbors

    @staticmethod
    def save_result(result: CollectionResult, output_dir: Path) -> None:
        """保存采集结果到文件"""
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"{result.device_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        log.debug("Collection result saved",
                  extra={"device": result.device_name, "file": str(filepath)})
