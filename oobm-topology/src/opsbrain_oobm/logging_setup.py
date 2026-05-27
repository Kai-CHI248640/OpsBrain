"""
OpsBrain OOBM — Structured Logging

所有日志以结构化 JSON 输出到 stdout/stderr，遵循 Docker 日志规范。
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class OpsBrainJSONFormatter(logging.Formatter):
    """JSON 格式化器 — 每条日志输出为单行 JSON"""

    def __init__(self):
        super().__init__()
        self._hostname = self._resolve_hostname()

    @staticmethod
    def _resolve_hostname() -> str:
        import socket
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "hostname": self._hostname,
            "message": record.getMessage(),
        }

        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra") and record.extra:
            entry["extra"] = record.extra

        return json.dumps(entry, ensure_ascii=False, default=str)


class OpsBrainTextFormatter(logging.Formatter):
    """人类可读的文本格式 — 本地开发用"""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-4]
        return (
            f"{timestamp} | {record.levelname:7} | "
            f"{record.module:15} | {record.getMessage()}"
        )


def setup_logging(
    level: str = "INFO",
    fmt: str = "json",
) -> None:
    """配置全局日志系统

    Args:
        level: 日志级别 (debug|info|warning|error|critical)
        fmt:   格式 (json|text)
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有 handler
    root.handlers.clear()

    # stdout 输出 INFO 及以上
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setLevel(logging.INFO)
    if fmt == "json":
        stdout.setFormatter(OpsBrainJSONFormatter())
    else:
        stdout.setFormatter(OpsBrainTextFormatter())
    root.addHandler(stdout)

    # stderr 输出 WARNING 及以上（异常/错误分离到 stderr）
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(logging.WARNING)
    if fmt == "json":
        stderr.setFormatter(OpsBrainJSONFormatter())
    else:
        stderr.setFormatter(OpsBrainTextFormatter())
    root.addHandler(stderr)

    # 第三方库降噪
    for noisy in ("paramiko", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Convenience ─────────────────────────────────────────────────────────────
get_logger = logging.getLogger
