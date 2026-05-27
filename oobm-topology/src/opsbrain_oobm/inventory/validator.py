"""
OpsBrain OOBM — Inventory Validator

校验设备清单的完整性和一致性。
"""
from __future__ import annotations

from typing import Any

from ..logging_setup import get_logger
from .models import Device

log = get_logger(__name__)


class InventoryValidator:
    """设备清单校验器"""

    def validate(
        self,
        devices: list[Device],
        strict: bool = True,
    ) -> list[str]:
        """执行全部校验规则

        Args:
            devices: Device 对象列表
            strict: 严格模式（默认开启，所有错误都返回）

        Returns:
            错误消息列表
        """
        errors: list[str] = []

        # Rule 1: 设备名唯一性
        errors.extend(self._check_unique_names(devices))

        # Rule 2: Console 端口唯一性
        errors.extend(self._check_console_ports(devices))

        # Rule 3: 带内 IP 唯一性
        errors.extend(self._check_mgmt_ips(devices))

        # Rule 4: Console 连接性基本检查
        errors.extend(self._check_connectivity(devices))

        # Rule 5: 厂商命令集支持
        if strict:
            errors.extend(self._check_vendor_support(devices))

        return errors

    @staticmethod
    def _check_unique_names(devices: list[Device]) -> list[str]:
        """设备名必须唯一"""
        errors: list[str] = []
        seen: dict[str, list[int]] = {}

        for idx, device in enumerate(devices):
            name = device.device_name
            if name in seen:
                seen[name].append(idx)
            else:
                seen[name] = [idx]

        for name, indices in seen.items():
            if len(indices) > 1:
                rows = ", ".join(str(i + 2) for i in indices)
                errors.append(f"Duplicate device name '{name}' at rows: {rows}")

        return errors

    @staticmethod
    def _check_console_ports(devices: list[Device]) -> list[str]:
        """同一串口服务器上的端口不能重复"""
        errors: list[str] = []
        port_map: dict[tuple[str, int], list[str]] = {}

        for device in devices:
            key = (device.console_ip, device.console_port)
            if key in port_map:
                port_map[key].append(device.device_name)
            else:
                port_map[key] = [device.device_name]

        for (ip, port), names in port_map.items():
            if len(names) > 1:
                errors.append(
                    f"Console port {ip}:{port} assigned to multiple devices: "
                    f"{', '.join(names)}"
                )

        return errors

    @staticmethod
    def _check_mgmt_ips(devices: list[Device]) -> list[str]:
        """带内管理 IP 不能重复"""
        errors: list[str] = []
        ip_map: dict[str, list[str]] = {}

        for device in devices:
            if not device.mgmt_ip:
                continue
            ip = device.mgmt_ip.split("/")[0]  # 去掉掩码
            if ip in ip_map:
                ip_map[ip].append(device.device_name)
            else:
                ip_map[ip] = [device.device_name]

        for ip, names in ip_map.items():
            if len(names) > 1:
                errors.append(
                    f"Management IP {ip} assigned to multiple devices: "
                    f"{', '.join(names)}"
                )

        return errors

    @staticmethod
    def _check_connectivity(devices: list[Device]) -> list[str]:
        """Console 连接性基本检查"""
        errors: list[str] = []
        for device in devices:
            octets = [int(p) for p in device.console_ip.split(".")]
            if octets[0] == 0 or octets[0] >= 224:
                errors.append(
                    f"{device.device_name}: console IP {device.console_ip} "
                    f"is not routable"
                )
        return errors

    @staticmethod
    def _check_vendor_support(devices: list[Device]) -> list[str]:
        """检查厂商是否在已知命令集中"""
        from .commands import get_supported_vendors

        supported = get_supported_vendors()
        errors: list[str] = []

        for device in devices:
            if device.vendor.value not in supported and device.vendor.value != "unknown":
                errors.append(
                    f"{device.device_name}: vendor '{device.vendor.value}' "
                    f"not in supported command set "
                    f"(supported: {', '.join(supported)})"
                )
        return errors
