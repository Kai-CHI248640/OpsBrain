"""
OpsBrain — Console Server Collector（模式 3：串口服务器采集）

支持主流串口服务器品牌，通过带外管理链路接入网络设备。
即使网络不通，也能通过 Console 口采集设备信息。
"""

from __future__ import annotations

import asyncio
import socket
import re
from typing import Optional

from logging_setup import get_logger

log = get_logger(__name__)

# ═══ 串口服务器品牌适配 ═════════════════════════════════════

CONSOLE_ADAPTERS = {
    "opengear": {
        "connect_port": lambda ip, port: (ip, port),
        "login_prompt": b"login:",
        "password_prompt": b"Password:",
        "use_ssh": True,
    },
    "digi": {
        "connect_port": lambda ip, port: (ip, port),
        "login_prompt": b"User:",
        "password_prompt": b"Password:",
        "use_ssh": True,
    },
    "raritan": {
        "connect_port": lambda ip, port: (ip, port + 3000),
        "login_prompt": b"login:",
        "password_prompt": b"Password:",
        "use_ssh": True,
    },
    "telnet": {
        "connect_port": lambda ip, port: (ip, port),
        "login_prompt": re.compile(rb"(login|Username|user)[\s:]*$"),
        "password_prompt": re.compile(rb"(Password|password)[\s:]*$"),
        "use_ssh": False,
    },
}


# ═══ 端口自动发现 ════════════════════════════════════════════

async def auto_discover_ports(server_ip: str, 
                               port_range: range = range(2001, 2101),
                               timeout: float = 2.0) -> list[int]:
    """
    自动探测串口服务器哪些端口有设备连接。
    尝试 TCP 连接，发送回车，检查是否有回显。
    """
    active = []
    
    async def check_port(port: int) -> int | None:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(server_ip, port), timeout=timeout
            )
            writer.write(b"\r\n")
            try:
                data = await asyncio.wait_for(writer.read(128), timeout=1.0)
                if data and len(data) > 2:
                    active.append(port)
            except asyncio.TimeoutError:
                pass
            writer.close()
            await writer.wait_closed()
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            pass
    
    tasks = [check_port(p) for p in port_range]
    await asyncio.gather(*tasks)
    return sorted(active)


# ═══ 串口采集器 ══════════════════════════════════════════════

class ConsoleCollector:
    """
    串口服务器采集器。
    
    用法:
        cc = ConsoleCollector(server_ip="10.0.0.100", brand="opengear")
        result = await cc.collect_port(2001, "admin", "***", "cisco")
    """
    
    def __init__(self, server_ip: str, brand: str = "telnet",
                 port_range: tuple[int, int] = (2001, 2048)):
        self.server_ip = server_ip
        self.adapter = CONSOLE_ADAPTERS.get(brand, CONSOLE_ADAPTERS["telnet"])
        self.port_range = port_range
    
    async def collect_port(self, port: int, username: str, password: str,
                           vendor: str, timeout: int = 30) -> dict:
        """采集单个串口端口的设备信息"""
        target_ip, target_port = self.adapter["connect_port"](self.server_ip, port)
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target_ip, target_port), timeout=5
            )
        except Exception as e:
            return {"port": port, "error": f"连接失败: {str(e)}"}
        
        result = {"port": port, "outputs": {}}
        
        try:
            # 等待登录提示
            data = await asyncio.wait_for(reader.read(4096), timeout=3)
            
            # 发送用户名
            writer.write(username.encode() + b"\n")
            await writer.drain()
            await asyncio.sleep(0.5)
            
            # 发送密码
            data = await reader.read(4096)
            writer.write(password.encode() + b"\n")
            await writer.drain()
            await asyncio.sleep(0.5)
            
            # 进入特权模式
            data = await reader.read(4096)
            if vendor in ("cisco", "ruijie"):
                writer.write(b"enable\n")
                await writer.drain()
                await asyncio.sleep(0.3)
                data = await reader.read(4096)
                writer.write(password.encode() + b"\n")
                await writer.drain()
                await asyncio.sleep(0.3)
            
            # 执行采集命令
            commands = {
                "version": "show version",
                "lldp": "show lldp neighbors detail" if vendor != "huawei" else "display lldp neighbor-information",
            }
            
            for cmd_key, cmd in commands.items():
                writer.write(cmd.encode() + b"\n")
                await writer.drain()
                await asyncio.sleep(1.0)
                try:
                    output = await asyncio.wait_for(reader.read(8192), timeout=5)
                    result["outputs"][cmd_key] = output.decode(errors="replace")
                except asyncio.TimeoutError:
                    result["outputs"][cmd_key] = ""
            
        except Exception as e:
            result["error"] = f"采集异常: {str(e)}"
        finally:
            writer.close()
            await writer.wait_closed()
        
        return result
    
    async def collect_all(self, devices: list[dict]) -> list[dict]:
        """批量采集多个端口"""
        results = []
        for dev in devices:
            port = dev.get("consolePort", 0)
            if not port:
                continue
            log.info("Console collect", extra={"port": port, "device": dev.get("name", "?")})
            r = await self.collect_port(
                port=port,
                username=dev.get("username", "admin"),
                password=dev.get("password", ""),
                vendor=dev.get("vendor", "cisco"),
            )
            results.append(r)
        return results
