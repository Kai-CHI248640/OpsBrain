"""
OpsBrain OOBM — SSH Session Manager

Paramiko-based SSH session with expect-style CLI interaction.
支持不同厂商的登录方式和命令执行模式。
"""

from __future__ import annotations

import re
import time
import socket
from typing import Any, Optional

import paramiko

from ..logging_setup import get_logger

log = get_logger(__name__)


# ─── 厂商 Prompt 模式 ──────────────────────────────────────────────────────

class PromptMode:
    """不同厂商的 CLI Prompt 匹配模式"""
    CISCO = r"[\w.-]+[>#]\s*$"
    CISCO_NXOS = r"[\w.-]+[>#]\s*$"
    HUAWEI = r"[\w.-]+[>\]~]\s*$"
    H3C = r"[\w.-]+[>\]~]\s*$"
    JUNIPER = r"[\w.-]+>\s*$"
    FORTINET = r"[\w.-]+#\s*$"
    RUIJIE = r"[\w.-]+[>#]\s*$"
    GENERIC = r"[\w.-]+[>#$%]\s*$"

    @staticmethod
    def for_vendor(vendor: str) -> str:
        mapping = {
            "cisco": PromptMode.CISCO,
            "cisco_nxos": PromptMode.CISCO_NXOS,
            "huawei": PromptMode.HUAWEI,
            "h3c": PromptMode.H3C,
            "juniper": PromptMode.JUNIPER,
            "fortinet": PromptMode.FORTINET,
            "ruijie": PromptMode.RUIJIE,
        }
        return mapping.get(vendor.lower(), PromptMode.GENERIC)


class SSHResult:
    """SSH 命令执行结果"""
    def __init__(
        self,
        command: str,
        stdout: str,
        stderr: str = "",
        exit_code: int = 0,
        duration: float = 0.0,
        error: Optional[str] = None,
    ):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration = duration
        self.error = error

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and self.error is None

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration, 2),
        }


class SSHSession:
    """
    SSH 会话管理器
    管理到 Console 端口的 SSH 连接、登录、命令执行
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        enable_password: str | None = None,
        vendor: str = "cisco",
        timeout: int = 30,
        command_timeout: int = 15,
        banner_timeout: int = 10,
        enable_timeout: int = 10,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.vendor = vendor.lower()
        self.timeout = timeout
        self.command_timeout = command_timeout
        self.banner_timeout = banner_timeout
        self.enable_timeout = enable_timeout

        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None
        self._connected = False
        self._privileged = False
        self._session_log: list[dict] = []

    # ── Connection Management ──────────────────────────────────────────

    def connect(self) -> bool:
        """建立 SSH 连接"""
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                banner_timeout=self.banner_timeout,
                allow_agent=False,
                look_for_keys=False,
                compress=True,
            )

            self._channel = self._client.invoke_shell(
                term="vt100",
                width=300,
                height=100,
            )
            self._channel.settimeout(self.command_timeout)

            # 等待初始 prompt
            initial = self._read_until_prompt(timeout=self.banner_timeout)
            self._connected = True

            log.debug("SSH connected",
                      extra={
                          "target": f"{self.host}:{self.port}",
                          "initial_output": initial[:200],
                      })
            return True

        except (paramiko.SSHException, socket.timeout,
                socket.gaierror, OSError) as e:
            log.warning("SSH connect failed",
                        extra={
                            "target": f"{self.host}:{self.port}",
                            "error": str(e),
                        })
            self._session_log.append({
                "action": "connect",
                "error": str(e),
            })
            return False

    def disconnect(self) -> None:
        """断开 SSH 连接"""
        self._connected = False
        try:
            if self._channel:
                self._channel.close()
        except Exception:
            pass
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass
        log.debug("SSH disconnected",
                  extra={"target": f"{self.host}:{self.port}"})

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    # ── Privilege Escalation ───────────────────────────────────────────

    def enter_privileged_mode(self) -> bool:
        """进入特权模式 (enable)"""
        if self._privileged:
            return True

        if not self._channel:
            return False

        # 判断是否需要 enable
        if self.vendor in ("juniper", "fortinet"):
            self._privileged = True
            return True

        try:
            self._channel.send("enable\n")
            time.sleep(1)

            # 检查是否需要密码
            output = self._read_until_prompt(timeout=self.enable_timeout)

            if "Password" in output or "password" in output:
                if self.enable_password:
                    self._channel.send(f"{self.enable_password}\n")
                    time.sleep(1)
                    self._read_until_prompt(timeout=self.enable_timeout)
                else:
                    log.warning("Enable password required but not provided")
                    return False

            # 确认已处于特权模式
            if self._channel:
                self._channel.send("\n")
                time.sleep(0.5)
                output = self._read_until_prompt(timeout=5)
                if "#" in output:
                    self._privileged = True
                    log.debug("Entered privileged mode")
                    return True

            log.warning("Failed to enter privileged mode")
            return False

        except Exception as e:
            log.warning("Enable failed", extra={"error": str(e)})
            return False

    # ── Command Execution ──────────────────────────────────────────────

    def execute_command(self, command: str) -> SSHResult:
        """执行单个命令并返回结果"""
        if not self._channel or not self._connected:
            return SSHResult(
                command=command,
                stdout="",
                exit_code=-1,
                error="Not connected",
            )

        start = time.monotonic()

        try:
            # 发送命令
            self._channel.send(f"{command}\n")

            # 读取输出
            output = self._read_until_prompt(timeout=self.command_timeout)
            duration = time.monotonic() - start

            result = SSHResult(
                command=command,
                stdout=output,
                duration=duration,
            )

            self._session_log.append({
                "action": "command",
                "command": command,
                "duration": round(duration, 2),
                "output_size": len(output),
            })

            return result

        except socket.timeout:
            duration = time.monotonic() - start
            return SSHResult(
                command=command,
                stdout="",
                exit_code=-1,
                duration=duration,
                error="Command timed out",
            )
        except Exception as e:
            duration = time.monotonic() - start
            return SSHResult(
                command=command,
                stdout="",
                exit_code=-1,
                duration=duration,
                error=str(e),
            )

    def execute_commands(
        self, commands: list[str]
    ) -> dict[str, SSHResult]:
        """批量执行命令"""
        results: dict[str, SSHResult] = {}

        for cmd in commands:
            # 命令名提取（简短描述）
            cmd_name = cmd.replace(" ", "_")[:50]
            results[cmd_name] = self.execute_command(cmd)

        return results

    # ── Internal ───────────────────────────────────────────────────────

    def _read_until_prompt(
        self,
        timeout: float = 10.0,
        prompt_pattern: str | None = None,
    ) -> str:
        """
        读取直到匹配 prompt 或超时
        使用状态机逐字节读取
        """
        if not self._channel:
            return ""

        pattern = prompt_pattern or PromptMode.for_vendor(self.vendor)
        compiled = re.compile(pattern, re.MULTILINE)

        output = ""
        start = time.monotonic()
        buffer = ""

        while time.monotonic() - start < timeout:
            try:
                if self._channel.recv_ready():
                    data = self._channel.recv(4096).decode("utf-8", errors="replace")
                    buffer += data
                    output += data

                    # 批量检查 prompt
                    lines = buffer.split("\n")
                    for line in lines:
                        if compiled.search(line):
                            # 去掉最后一条 prompt 行
                            output = output.rstrip()
                            return output

                    # 保留最后 200 字符用于 prompt 匹配
                    if len(buffer) > 2000:
                        buffer = buffer[-200:]
                else:
                    time.sleep(0.05)

            except socket.timeout:
                break
            except Exception:
                break

        # 超时，返回已读内容
        return output.rstrip()

    @property
    def session_log(self) -> list[dict]:
        return list(self._session_log)

    @property
    def connected(self) -> bool:
        return self._connected
