"""
OpsBrain Web — Database Models

SQLAlchemy ORM 模型：用户、设置、API Key、项目配置、Agent 配置。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


# ═══════════════════════════════════════════════════════════════════════════
# User
# ═══════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(32), default="admin")  # admin | operator

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "last_login": self.last_login.isoformat() if self.last_login else "",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Setting (Key-Value)
# ═══════════════════════════════════════════════════════════════════════════

class Setting(Base):
    """通用设置表（Key-Value 结构）"""
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="general")  # theme | paths | etc
    description: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


# ═══════════════════════════════════════════════════════════════════════════
# API Key (多 API 管理)
# ═══════════════════════════════════════════════════════════════════════════

class ApiKey(Base):
    """API Key 管理（参考 OpenClaw：多提供商、多 Key、启用/禁用）"""
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)       # 显示名称
    provider: Mapped[str] = mapped_column(String(64), nullable=False)     # openai | deepseek | custom
    api_base: Mapped[str] = mapped_column(String(256), default="")        # API 地址
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)     # API Key（加密存储）
    model: Mapped[str] = mapped_column(String(128), default="")           # 默认模型
    api_type: Mapped[str] = mapped_column(String(32), default="llm")       # llm | embedding
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)        # 启用/禁用
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)      # 是否为默认

    # 能力范围
    can_parse: Mapped[bool] = mapped_column(Boolean, default=True)
    can_describe: Mapped[bool] = mapped_column(Boolean, default=True)
    can_identify: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self, mask_key: bool = True) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "api_base": self.api_base,
            "api_key": f"****{self.api_key[-8:]}" if mask_key and len(self.api_key) > 8 else self.api_key,
            "model": self.model,
            "api_type": self.api_type,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "can_parse": self.can_parse,
            "can_describe": self.can_describe,
            "can_identify": self.can_identify,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Project Config（项目文件管理）
# ═══════════════════════════════════════════════════════════════════════════

class ProjectConfig(Base):
    """项目文件管理 — 拉取的项目、镜像等文件的存放地址配置"""
    __tablename__ = "project_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(256), default="")

    # 存储路径
    projects_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/projects")
    images_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/images")
    data_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/data")
    logs_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/logs")
    backup_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/backups")

    # Docker 镜像存储
    docker_registry: Mapped[str] = mapped_column(String(256), default="")
    image_cache_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/images/cache")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "projects_path": self.projects_path,
            "images_path": self.images_path,
            "data_path": self.data_path,
            "logs_path": self.logs_path,
            "backup_path": self.backup_path,
            "docker_registry": self.docker_registry,
            "image_cache_path": self.image_cache_path,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Topology Save（拓扑保存）
# ═══════════════════════════════════════════════════════════════════════════

class TopologySave(Base):
    """保存的拓扑数据"""
    __tablename__ = "topology_saves"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    discovery_method: Mapped[str] = mapped_column(String(64), default="lan")
    device_count: Mapped[int] = mapped_column(Integer, default=0)
    link_count: Mapped[int] = mapped_column(Integer, default=0)
    device_data: Mapped[str] = mapped_column(Text, default="[]")
    link_data: Mapped[str] = mapped_column(Text, default="[]")
    analysis: Mapped[str] = mapped_column(Text, default="")
    mermaid_code: Mapped[str] = mapped_column(Text, default="")
    subagent_id: Mapped[str] = mapped_column(String(32), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        import json as _json
        return {
            "id": self.id,
            "name": self.name,
            "discovery_method": self.discovery_method,
            "device_count": self.device_count,
            "link_count": self.link_count,
            "device_data": _json.loads(self.device_data) if self.device_data else [],
            "link_data": _json.loads(self.link_data) if self.link_data else [],
            "analysis": self.analysis,
            "mermaid_code": self.mermaid_code,
            "subagent_id": self.subagent_id,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Subagent（拓扑绑定的 Agent）
# ═══════════════════════════════════════════════════════════════════════════

class Subagent(Base):
    """每生成一个拓扑就自动生成一个 Subagent 绑定到这个拓扑"""
    __tablename__ = "subagents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    topology_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="idle")  # idle | working | error
    api_key_id: Mapped[str] = mapped_column(String(32), default="")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_active: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topology_id": self.topology_id,
            "name": self.name,
            "status": self.status,
            "api_key_id": self.api_key_id,
            "message_count": self.message_count,
            "last_active": self.last_active.isoformat() if self.last_active else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Agent Config（Agent 文件管理，参考 OpenClaw）
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# Feishu Config（飞书集成配置）
# ═══════════════════════════════════════════════════════════════════════════

class FeishuConfig(Base):
    """飞书机器人集成配置

    支持两种连接模式:
    - webhook : 飞书通过 HTTP POST 回调发送事件
    - websocket : OpenClaw/OpsBrain 主动连接飞书长连接
    """
    __tablename__ = "feishu_config"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # 通用
    app_id: Mapped[str] = mapped_column(String(64), default="")
    app_secret: Mapped[str] = mapped_column(String(256), default="")
    domain: Mapped[str] = mapped_column(String(16), default="feishu")  # feishu | lark

    # 连接模式: webhook | websocket
    connection_mode: Mapped[str] = mapped_column(String(16), default="webhook")

    # Webhook 模式专用
    verification_token: Mapped[str] = mapped_column(String(128), default="")
    encrypt_key: Mapped[str] = mapped_column(String(128), default="")
    webhook_path: Mapped[str] = mapped_column(String(128), default="/opsbrain/api/v1/agent/feishu-webhook")

    # 群聊策略
    group_policy: Mapped[str] = mapped_column(String(16), default="allowlist")  # open | allowlist | disabled
    require_mention: Mapped[bool] = mapped_column(Boolean, default=True)
    dm_policy: Mapped[str] = mapped_column(String(16), default="pairing")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    def to_dict(self, mask_secret: bool = True) -> dict:
        return {
            "id": self.id,
            "enabled": self.enabled,
            "app_id": self.app_id,
            "app_secret": f"****{self.app_secret[-4:]}" if mask_secret and len(self.app_secret) > 8 else self.app_secret,
            "domain": self.domain,
            "connection_mode": self.connection_mode,
            "verification_token": bool(self.verification_token),
            "encrypt_key": bool(self.encrypt_key),
            "webhook_path": self.webhook_path,
            "group_policy": self.group_policy,
            "require_mention": self.require_mention,
            "dm_policy": self.dm_policy,
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class AgentConfig(Base):
    """Agent 文件管理 — 参考 OpenClaw 的 Agent 机制"""
    __tablename__ = "agent_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(256), default="")

    # Agent 类型
    agent_type: Mapped[str] = mapped_column(String(64), default="oobm-topology")
    # 支持的 agent 类型: oobm-topology | network-monitor | log-analyzer | custom

    # Agent 技能文件路径
    skill_path: Mapped[str] = mapped_column(String(512), default="/etc/opsbrain/agent/skills")
    skill_files: Mapped[str] = mapped_column(Text, default="")  # JSON list of files

    # Agent 配置
    model_config_id: Mapped[str] = mapped_column(String(32), default="")  # 关联的 API Key ID
    max_workers: Mapped[int] = mapped_column(Integer, default=10)
    timeout: Mapped[int] = mapped_column(Integer, default=300)

    # Agent 运行时
    runtime_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/agent/runtime")
    log_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/agent/logs")
    state_path: Mapped[str] = mapped_column(String(512), default="/var/lib/opsbrain/agent/state")

    # 启用状态
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_start: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "skill_path": self.skill_path,
            "skill_files": self.skill_files,
            "model_config_id": self.model_config_id,
            "max_workers": self.max_workers,
            "timeout": self.timeout,
            "runtime_path": self.runtime_path,
            "log_path": self.log_path,
            "state_path": self.state_path,
            "is_enabled": self.is_enabled,
            "auto_start": self.auto_start,
        }
