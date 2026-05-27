"""
OpsBrain OOBM — Inventory Loader

Excel 设备清单加载器。
支持占位符密码解析和环境变量引用。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import openpyxl

from ..logging_setup import get_logger
from .models import Device, DeviceType, Vendor, DeviceRole, LoginMethod

log = get_logger(__name__)


class InventoryLoader:
    """设备清单加载器 — 读取 Excel 输出标准化 JSON"""

    # Excel 列名 → 模型字段映射
    COLUMN_MAP = {
        "device_name": "device_name",
        "设备名": "device_name",
        "名称": "device_name",

        "device_type": "device_type",
        "设备类型": "device_type",
        "类型": "device_type",

        "vendor": "vendor",
        "厂商": "vendor",

        "console_ip": "console_ip",
        "串口服务器IP": "console_ip",
        "console_ip": "console_ip",

        "console_port": "console_port",
        "串口端口": "console_port",
        "端口": "console_port",
        "port": "console_port",

        "login_method": "login_method",
        "登录方式": "login_method",

        "username": "username",
        "账号": "username",

        "password": "password",
        "密码": "password",

        "enable_password": "enable_password",
        "启用密码": "enable_password",
        "enable": "enable_password",

        "role": "role",
        "角色": "role",

        "mgmt_ip": "mgmt_ip",
        "管理IP": "mgmt_ip",
        "ip": "mgmt_ip",

        "location": "location",
        "位置": "location",

        "model": "model",
        "型号": "model",

        "description": "description",
        "描述": "description",

        "tags": "tags",
        "标签": "tags",
    }

    ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}|\{\{(ENV_\w+)\}\}")

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> list[Device]:
        """加载 Excel 并返回 Device 列表"""
        log.info("Parsing Excel inventory", extra={"file": str(self.file_path)})

        wb = openpyxl.load_workbook(
            self.file_path, read_only=True, data_only=True
        )
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            log.warning("Empty Excel sheet")
            return []

        # 解析表头
        headers = self._parse_headers(rows[0])
        if not headers:
            log.error("No recognizable headers found in Excel")
            return []

        log.debug("Parsed headers", extra={"headers": list(headers.keys())})

        # 解析数据行
        devices: list[Device] = []
        errors: list[str] = []

        for row_idx, row in enumerate(rows[1:], start=2):
            # 跳过空行
            if all(cell is None or str(cell).strip() == "" for cell in row):
                continue

            raw: dict[str, Any] = {}
            for col_idx, cell in enumerate(row):
                if col_idx < len(headers):
                    field = list(headers.keys())[col_idx]
                    raw[field] = self._resolve_value(cell)

            try:
                device = Device(**raw)
                devices.append(device)
                log.debug("Parsed device row",
                          extra={"row": row_idx, "name": device.device_name})
            except Exception as e:
                err_msg = f"Row {row_idx} ({raw.get('device_name', '?')}): {e}"
                errors.append(err_msg)
                log.warning("Skipping invalid row",
                            extra={"row": row_idx, "error": str(e)})

        if errors:
            log.warning("Rows with errors",
                        extra={"count": len(errors)})

        log.info(
            "Excel parsed",
            extra={
                "total_rows": len(rows) - 1,
                "valid_devices": len(devices),
                "errors": len(errors),
            },
        )
        return devices

    def _parse_headers(self, header_row: tuple) -> dict[str, str]:
        """解析表头：Excel 列名 → 模型字段名"""
        headers: dict[str, str] = {}
        for cell in header_row:
            if cell is None:
                continue
            cell_str = str(cell).strip().lower()
            # 匹配列名映射
            for excel_col, model_field in self.COLUMN_MAP.items():
                if cell_str == excel_col.lower():
                    headers[model_field] = model_field
                    break
            else:
                # 尝试直接匹配模型字段
                cleaned = cell_str.replace(" ", "_")
                if hasattr(Device, cleaned):
                    headers[cleaned] = cleaned
        return headers

    def _resolve_value(self, cell: Any) -> Any:
        """解析单元格值，支持环境变量引用"""
        if cell is None:
            return None

        value = str(cell).strip()

        # 空字符串 → None
        if not value:
            return None

        # 环境变量引用: ${VAR} 或 {{ENV_VAR}}
        match = self.ENV_VAR_PATTERN.match(value)
        if match:
            var_name = match.group(1) or match.group(2)
            resolved = os.environ.get(var_name)
            if resolved is None:
                log.warning(f"Environment variable {var_name} not set, "
                            f"using literal value")
                return value
            return resolved

        # 数字转换
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        return value

    @staticmethod
    def save(devices: list[Device], output_path: Path) -> None:
        """将设备列表保存为 JSON"""
        data = {
            "metadata": {
                "total": len(devices),
                "source": "opsbrain-excel-loader",
            },
            "devices": [d.to_dict() for d in devices],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info("Devices saved to JSON", extra={"path": str(output_path)})

    @staticmethod
    def load_json(path: Path) -> list[dict]:
        """从 JSON 加载设备列表"""
        if not path.exists():
            log.error("Inventory JSON not found", extra={"path": str(path)})
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        devices = data.get("devices", data if isinstance(data, list) else [])
        log.info("Loaded devices from JSON",
                 extra={"count": len(devices), "path": str(path)})
        return devices
