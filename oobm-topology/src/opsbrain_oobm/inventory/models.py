"""
OpsBrain OOBM — Inventory Models

基于 Pydantic 的设备数据模型，严格类型校验。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DeviceType(str, Enum):
    SWITCH = "switch"
    ROUTER = "router"
    FIREWALL = "firewall"
    SERVER = "server"
    AP_CONTROLLER = "ap_controller"
    LOAD_BALANCER = "load_balancer"
    UNKNOWN = "unknown"


class Vendor(str, Enum):
    CISCO = "cisco"
    CISCO_NXOS = "cisco_nxos"
    CISCO_XR = "cisco_xr"
    HUAWEI = "huawei"
    H3C = "h3c"
    JUNIPER = "juniper"
    HP_PROCURVE = "hp_procurve"
    FORTINET = "fortinet"
    RUIJIE = "ruijie"
    UNKNOWN = "unknown"


class DeviceRole(str, Enum):
    CORE = "core"
    DISTRIBUTION = "distribution"
    ACCESS = "access"
    BORDER = "border"
    MGMT = "mgmt"
    SERVER = "server"
    UNKNOWN = "unknown"


class LoginMethod(str, Enum):
    SSH = "ssh"
    TELNET = "telnet"


class Device(BaseModel):
    """单个网络设备模型"""
    device_name: str = Field(..., min_length=1, max_length=128)
    device_type: DeviceType = Field(default=DeviceType.UNKNOWN)
    vendor: Vendor = Field(default=Vendor.UNKNOWN)
    console_ip: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    console_port: int = Field(..., ge=1, le=65535)
    login_method: LoginMethod = Field(default=LoginMethod.SSH)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    enable_password: Optional[str] = Field(default=None)
    role: DeviceRole = Field(default=DeviceRole.UNKNOWN)
    mgmt_ip: Optional[str] = Field(default=None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$")
    location: Optional[str] = Field(default=None, max_length=256)
    model: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    tags: list[str] = Field(default_factory=list)

    # 运行时字段（不会出现在 Excel 中）
    raw_vendor: Optional[str] = Field(default=None, exclude=True)
    collected_at: Optional[datetime] = Field(default=None, exclude=True)
    collection_status: Optional[str] = Field(
        default="pending", exclude=True
    )

    @field_validator("device_name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """标准化设备名：去空格、大写"""
        return v.strip().upper()

    @field_validator("console_ip")
    @classmethod
    def validate_console_ip(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 4:
            raise ValueError(f"Invalid console IP: {v}")
        for p in parts:
            n = int(p)
            if n < 0 or n > 255:
                raise ValueError(f"Invalid console IP octet: {v}")
        return v

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return [t.strip().lower() for t in v if t.strip()]

    @model_validator(mode="after")
    def check_vendor_support(self) -> "Device":
        """检查厂商是否在已知列表中"""
        known_vendors = {e.value for e in Vendor}
        if self.vendor.value not in known_vendors:
            self.raw_vendor = self.vendor.value
            self.vendor = Vendor.UNKNOWN
        return self

    def to_dict(self) -> dict:
        """导出为字典（含运行时字段）"""
        return self.model_dump(mode="json", exclude_none=True)

    def console_target(self) -> str:
        """SSH/Telnet 目标地址: console_ip:console_port"""
        return f"{self.console_ip}:{self.console_port}"


class Inventory(BaseModel):
    """设备清单集合"""
    devices: list[Device] = Field(default_factory=list)
    loaded_at: datetime = Field(default_factory=datetime.utcnow)
    source_file: Optional[str] = Field(default=None)
    total: int = 0

    @model_validator(mode="after")
    def set_total(self) -> "Inventory":
        self.total = len(self.devices)
        return self

    def by_role(self, role: DeviceRole) -> list[Device]:
        return [d for d in self.devices if d.role == role]

    def by_vendor(self, vendor: Vendor) -> list[Device]:
        return [d for d in self.devices if d.vendor == vendor]

    def by_type(self, device_type: DeviceType) -> list[Device]:
        return [d for d in self.devices if d.device_type == device_type]
