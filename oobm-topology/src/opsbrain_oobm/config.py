"""
OpsBrain OOBM — Configuration Management

配置优先级: 环境变量 > 配置文件 > 默认值
遵循 12-Factor App: 配置与代码严格分离
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogFormat(str, Enum):
    JSON = "json"
    TEXT = "text"


class PipelineMode(str, Enum):
    """Pipeline execution modes"""
    FULL = "full"          # 全量：load → collect → parse → link → render
    COLLECT_ONLY = "collect"  # 仅采集
    TOPOLOGY_ONLY = "topology"  # 仅拓扑构建
    INCREMENTAL = "incremental"  # 增量：基于已有拓扑，只采集变化


class RetryStrategy(str, Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class BackoffStrategy(str, Enum):
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


class AppConfig(BaseSettings):
    """全局应用配置 — 所有可配置项集中管理"""

    model_config = SettingsConfigDict(
        env_prefix="OPSBRAIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Identity ──────────────────────────────────────────────────────
    role: str = Field(default="collector", description="运行时角色")
    instance_id: str = Field(default="", description="实例 ID（自动生成）")

    # ── Logging ───────────────────────────────────────────────────────
    log_level: LogLevel = Field(default=LogLevel.INFO, alias="OPSBRAIN_LOG_LEVEL")
    log_format: LogFormat = Field(default=LogFormat.JSON, alias="OPSBRAIN_LOG_FORMAT")

    # ── Inventory ─────────────────────────────────────────────────────
    inventory_file: Path = Field(
        default=Path("/etc/opsbrain/device-inventory.xlsx"),
        alias="OPSBRAIN_INVENTORY_FILE",
    )
    inventory_output: Path = Field(
        default=Path("/var/lib/opsbrain/inventory/devices.json"),
        alias="OPSBRAIN_INVENTORY_OUTPUT",
    )
    validate_strict: bool = Field(default=True, alias="OPSBRAIN_VALIDATE_STRICT")

    # ── Collector ─────────────────────────────────────────────────────
    workers: int = Field(default=10, ge=1, le=100, alias="OPSBRAIN_WORKERS")
    ssh_timeout: int = Field(default=30, ge=5, le=120, alias="OPSBRAIN_SSH_TIMEOUT")
    ssh_retries: int = Field(default=2, ge=0, le=5, alias="OPSBRAIN_SSH_RETRIES")
    ssh_backoff: BackoffStrategy = Field(
        default=BackoffStrategy.EXPONENTIAL_JITTER,
        alias="OPSBRAIN_SSH_BACKOFF",
    )
    ssh_banner_timeout: int = Field(default=10, alias="OPSBRAIN_SSH_BANNER_TIMEOUT")
    command_timeout: int = Field(default=15, ge=5, le=60, alias="OPSBRAIN_COMMAND_TIMEOUT")
    device_timeout: int = Field(default=90, ge=15, le=300, alias="OPSBRAIN_DEVICE_TIMEOUT")
    enable_timeout: int = Field(default=10, alias="OPSBRAIN_ENABLE_TIMEOUT")
    collected_dir: Path = Field(
        default=Path("/var/lib/opsbrain/collected"),
        alias="OPSBRAIN_COLLECTED_DIR",
    )

    # ── Discovery ─────────────────────────────────────────────────────
    max_discovery_rounds: int = Field(default=3, ge=1, le=5, alias="OPSBRAIN_MAX_ROUNDS")
    auto_discover: bool = Field(default=True, alias="OPSBRAIN_AUTO_DISCOVER")

    # ── Parser ─────────────────────────────────────────────────────────
    parsed_dir: Path = Field(
        default=Path("/var/lib/opsbrain/parsed"),
        alias="OPSBRAIN_PARSED_DIR",
    )

    # ── Topology ───────────────────────────────────────────────────────
    output_dir: Path = Field(
        default=Path("/var/lib/opsbrain/topology"),
        alias="OPSBRAIN_OUTPUT_DIR",
    )
    output_formats: list[str] = Field(
        default=["json", "dot", "mermaid"],
        alias="OPSBRAIN_OUTPUT_FORMATS",
    )
    render_images: bool = Field(default=False, alias="OPSBRAIN_RENDER_IMAGES")

    # ── Paths ──────────────────────────────────────────────────────────
    home_dir: Path = Field(default=Path("/var/lib/opsbrain"), alias="OPSBRAIN_HOME")
    config_dir: Path = Field(default=Path("/etc/opsbrain"), alias="OPSBRAIN_CONFIG")

    # ── Model ────────────────────────────────────────────────────────
    model_enabled: bool = Field(default=True, alias="OPSBRAIN_MODEL_ENABLED")
    model_provider: str = Field(
        default="deepseek",
        alias="OPSBRAIN_MODEL_PROVIDER",
        description="模型提供商",
    )
    model_api_base: str = Field(default="", alias="OPSBRAIN_MODEL_API_BASE")
    model_api_key: str = Field(default="", alias="OPSBRAIN_MODEL_API_KEY")
    model_model: str = Field(default="", alias="OPSBRAIN_MODEL_MODEL")
    model_max_tokens: int = Field(default=4096, alias="OPSBRAIN_MODEL_MAX_TOKENS")
    model_temperature: float = Field(
        default=0.3, alias="OPSBRAIN_MODEL_TEMPERATURE"
    )
    model_timeout: int = Field(default=60, alias="OPSBRAIN_MODEL_TIMEOUT")
    model_parse_neighbors: bool = Field(
        default=True, alias="OPSBRAIN_MODEL_PARSE_NEIGHBORS"
    )
    model_describe_topology: bool = Field(
        default=True, alias="OPSBRAIN_MODEL_DESCRIBE_TOPOLOGY"
    )

    # ── Pipeline ───────────────────────────────────────────────────────
    pipeline_mode: PipelineMode = Field(
        default=PipelineMode.FULL, alias="OPSBRAIN_PIPELINE_MODE"
    )

    @field_validator("instance_id", mode="before")
    @classmethod
    def default_instance_id(cls, v: str) -> str:
        if not v:
            import uuid
            return uuid.uuid4().hex[:12]
        return v

    @field_validator("workers", mode="after")
    @classmethod
    def clamp_workers(cls, v: int) -> int:
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        return min(v, cpu_count * 3)


# ── Global singleton ────────────────────────────────────────────────────────
config: AppConfig = AppConfig()
