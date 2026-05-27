"""OpsBrain Web — Pydantic Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Auth ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class SetupRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Settings ───────────────────────────────────────────────────────────────

class SettingUpdate(BaseModel):
    key: str = Field(..., max_length=128)
    value: str = Field(..., max_length=65536)
    category: str = Field(default="general", max_length=64)
    description: str = Field(default="", max_length=256)


class SettingResponse(BaseModel):
    id: str
    key: str
    value: str
    category: str
    description: str
    updated_at: str


# ── API Keys ───────────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(..., max_length=64)
    api_base: str = Field(default="", max_length=256)
    api_key: str = Field(..., min_length=1, max_length=512)
    model: str = Field(default="", max_length=128)
    api_type: str = Field(default="llm", max_length=32)
    is_default: bool = False
    can_parse: bool = True
    can_describe: bool = True
    can_identify: bool = False


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    can_parse: Optional[bool] = None
    can_describe: Optional[bool] = None
    can_identify: Optional[bool] = None


# ── Project Config ─────────────────────────────────────────────────────────

class ProjectConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=256)
    projects_path: str = Field(default="/var/lib/opsbrain/projects")
    images_path: str = Field(default="/var/lib/opsbrain/images")
    data_path: str = Field(default="/var/lib/opsbrain/data")
    logs_path: str = Field(default="/var/lib/opsbrain/logs")
    backup_path: str = Field(default="/var/lib/opsbrain/backups")
    docker_registry: str = Field(default="")
    image_cache_path: str = Field(default="/var/lib/opsbrain/images/cache")


class ProjectConfigUpdate(BaseModel):
    description: Optional[str] = None
    projects_path: Optional[str] = None
    images_path: Optional[str] = None
    data_path: Optional[str] = None
    logs_path: Optional[str] = None
    backup_path: Optional[str] = None
    docker_registry: Optional[str] = None
    image_cache_path: Optional[str] = None


# ── Agent Config ───────────────────────────────────────────────────────────

class AgentConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=256)
    agent_type: str = Field(default="oobm-topology", max_length=64)
    skill_path: str = Field(default="/etc/opsbrain/agent/skills")
    skill_files: str = Field(default="")
    model_config_id: str = Field(default="", max_length=32)
    max_workers: int = Field(default=10, ge=1, le=100)
    timeout: int = Field(default=300, ge=30, le=3600)
    runtime_path: str = Field(default="/var/lib/opsbrain/agent/runtime")
    log_path: str = Field(default="/var/lib/opsbrain/agent/logs")
    state_path: str = Field(default="/var/lib/opsbrain/agent/state")
    is_enabled: bool = True
    auto_start: bool = False


class AgentConfigUpdate(BaseModel):
    description: Optional[str] = None
    agent_type: Optional[str] = None
    skill_path: Optional[str] = None
    skill_files: Optional[str] = None
    model_config_id: Optional[str] = None
    max_workers: Optional[int] = None
    timeout: Optional[int] = None
    runtime_path: Optional[str] = None
    log_path: Optional[str] = None
    state_path: Optional[str] = None
    is_enabled: Optional[bool] = None
    auto_start: Optional[bool] = None


# ── Theme ──────────────────────────────────────────────────────────────────

# ── Feishu Config ────────────────────────────────────────────────────────────

class FeishuConfigCreate(BaseModel):
    enabled: bool = Field(default=False)
    app_id: str = Field(default="", max_length=64)
    app_secret: str = Field(default="", max_length=256)
    domain: str = Field(default="feishu", pattern=r"^(feishu|lark)$")
    connection_mode: str = Field(default="webhook", pattern=r"^(webhook|websocket)$")
    verification_token: str = Field(default="", max_length=128)
    encrypt_key: str = Field(default="", max_length=128)
    webhook_path: str = Field(default="/opsbrain/api/v1/agent/feishu-webhook", max_length=128)
    group_policy: str = Field(default="allowlist", pattern=r"^(open|allowlist|disabled)$")
    require_mention: bool = Field(default=True)
    dm_policy: str = Field(default="pairing", max_length=16)


class FeishuConfigUpdate(BaseModel):
    enabled: bool | None = None
    app_id: str | None = None
    app_secret: str | None = None
    domain: str | None = None
    connection_mode: str | None = None
    verification_token: str | None = None
    encrypt_key: str | None = None
    webhook_path: str | None = None
    group_policy: str | None = None
    require_mention: bool | None = None
    dm_policy: str | None = None


class FeishuTestRequest(BaseModel):
    connection_mode: str = Field(default="webhook", pattern=r"^(webhook|websocket)$")
    app_id: str = Field(..., min_length=1, max_length=64)
    app_secret: str = Field(default="", max_length=256)
    domain: str = Field(default="feishu", pattern=r"^(feishu|lark)$")
    verification_token: str = Field(default="", max_length=128)
    encrypt_key: str = Field(default="", max_length=128)


class QRBeginRequest(BaseModel):
    domain: str = Field(default="feishu", pattern=r"^(feishu|lark)$")


class QRPollRequest(BaseModel):
    device_code: str = Field(..., min_length=1)
    domain: str = Field(default="feishu", pattern=r"^(feishu|lark)$")
    interval: int = Field(default=5, ge=1, le=30)


# ── Theme ──────────────────────────────────────────────────────────────────

class ThemeUpdate(BaseModel):
    theme: str = Field(..., pattern=r"^(light|dark)$")
