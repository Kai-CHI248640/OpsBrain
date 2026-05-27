"""
OpsBrain OOBM — Vendor Commands Registry

厂商专用命令集注册表，管理采集命令的加载和查询。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger
from .models import Vendor

log = get_logger(__name__)

# ─── 默认厂商命令集（内联）───────────────────────────────────────────────────
# 也可从 config/vendors.yml 加载

DEFAULT_COMMANDS: dict[str, dict[str, Any]] = {
    "cisco": {
        "label": "Cisco IOS/IOS-XE",
        "enter_privilege": "enable",
        "exit_privilege": "disable",
        "prompt_pattern": r">$|#$",
        "commands": {
            "lldp_neighbors": "show lldp neighbors detail",
            "cdp_neighbors": "show cdp neighbors detail",
            "arp_table": "show arp",
            "mac_table": "show mac address-table",
            "ip_route": "show ip route",
            "interfaces_ip": "show ip interface brief",
            "interfaces_desc": "show interfaces description",
            "vlan": "show vlan brief",
            "version": "show version",
        },
    },
    "cisco_nxos": {
        "label": "Cisco NX-OS",
        "enter_privilege": "enable",
        "exit_privilege": "disable",
        "prompt_pattern": r">$|#$",
        "commands": {
            "lldp_neighbors": "show lldp neighbors detail",
            "cdp_neighbors": "show cdp neighbors detail",
            "arp_table": "show ip arp",
            "mac_table": "show mac address-table",
            "ip_route": "show ip route",
            "interfaces_ip": "show ip interface brief",
            "vlan": "show vlan",
            "version": "show version",
        },
    },
    "huawei": {
        "label": "华为 VRP",
        "enter_privilege": "system-view",
        "exit_privilege": "return",
        "prompt_pattern": r">$|]$|~$|<",
        "commands": {
            "lldp_neighbors": "display lldp neighbor-information",
            "arp_table": "display arp",
            "mac_table": "display mac-address",
            "ip_route": "display ip routing-table",
            "interfaces_ip": "display ip interface brief",
            "interfaces_desc": "display interface brief",
            "vlan": "display vlan",
            "version": "display version",
        },
    },
    "h3c": {
        "label": "H3C Comware",
        "enter_privilege": "system-view",
        "exit_privilege": "return",
        "prompt_pattern": r">$|]$|<",
        "commands": {
            "lldp_neighbors": "display lldp neighbor-information",
            "arp_table": "display arp",
            "mac_table": "display mac-address",
            "ip_route": "display ip routing-table",
            "interfaces_ip": "display ip interface brief",
            "interfaces_desc": "display interface brief",
            "vlan": "display vlan",
            "version": "display version",
        },
    },
    "juniper": {
        "label": "Juniper JunOS",
        "enter_privilege": None,    # JunOS 不需要 enable
        "exit_privilege": "exit",
        "prompt_pattern": r">$",
        "commands": {
            "lldp_neighbors": "show lldp neighbors detail",
            "arp_table": "show arp no-resolve",
            "mac_table": "show ethernet-switching table",
            "ip_route": "show route",
            "interfaces": "show interfaces terse",
            "version": "show version",
        },
    },
    "fortinet": {
        "label": "FortiGate",
        "enter_privilege": None,
        "exit_privilege": "exit",
        "prompt_pattern": r"#$",
        "commands": {
            "lldp_neighbors": "diagnose lldprx neighbor list",
            "arp_table": "get system arp",
            "ip_route": "get router info routing-table all",
            "interfaces": "show system interface",
            "version": "get system status",
        },
    },
    "ruijie": {
        "label": "锐捷",
        "enter_privilege": "enable",
        "exit_privilege": "disable",
        "prompt_pattern": r">$|#$",
        "commands": {
            "lldp_neighbors": "show lldp neighbor detail",
            "arp_table": "show arp",
            "mac_table": "show mac-address-table",
            "ip_route": "show ip route",
            "interfaces_ip": "show ip interface brief",
            "vlan": "show vlan",
            "version": "show version",
        },
    },
}


class VendorCommands:
    """厂商命令集管理器"""

    def __init__(self, config_path: Path | None = None):
        self._commands = dict(DEFAULT_COMMANDS)
        if config_path and config_path.exists():
            self._load_override(config_path)

    def _load_override(self, config_path: Path) -> None:
        """从配置文件加载覆盖"""
        try:
            with open(config_path, "r") as f:
                override = json.load(f)
            self._commands.update(override)
            log.info("Vendor commands overridden",
                      extra={"source": str(config_path)})
        except Exception as e:
            log.warning("Failed to load vendor overrides",
                        extra={"error": str(e)})

    def get(self, vendor: str) -> dict[str, Any] | None:
        """获取指定厂商的命令集"""
        return self._commands.get(vendor.lower())

    def get_command(self, vendor: str, command_key: str) -> str | None:
        """获取指定厂商的特定命令"""
        vendor_cmds = self.get(vendor)
        if vendor_cmds is None:
            return None
        cmds = vendor_cmds.get("commands", {})
        return cmds.get(command_key)

    def get_command_list(self, vendor: str) -> list[str]:
        """获取指定厂商的所有命令列表（按顺序）"""
        vendor_cmds = self.get(vendor)
        if vendor_cmds is None:
            return []
        cmds = vendor_cmds.get("commands", {})
        return list(cmds.values())

    def is_supported(self, vendor: str) -> bool:
        """判断厂商是否被支持"""
        return vendor.lower() in self._commands

    def supported_vendors(self) -> list[str]:
        """获取所有支持的厂商列表"""
        return list(self._commands.keys())


def get_supported_vendors() -> list[str]:
    """获取支持的厂商列表（便捷函数）"""
    return list(DEFAULT_COMMANDS.keys())
