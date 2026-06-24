"""
OpsBrain — Tool Executor

Extracted from agent_chat.py. Handles Function Calling tool execution
(Commander + Subagent tools).
"""

from __future__ import annotations

import json
import asyncio
from typing import Optional

import httpx
from sqlalchemy import select

from ..database import async_session
from ..models import TopologySave, Subagent

from logging_setup import get_logger

log = get_logger(__name__)


# ═══ Device Operations ════════════════════════════════════════════

async def socket_check(host: str, port: int, timeout: int = 3) -> bool:
    """Socket port connectivity check."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def ssh_exec(host: str, user: str, pwd: str, cmd: str,
                   port: int = 22, timeout: int = 10) -> dict:
    """paramiko SSH command execution."""
    try:
        loop = asyncio.get_running_loop()

        def _do():
            import paramiko
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(host, port=port, username=user, password=pwd,
                      timeout=timeout, allow_agent=False, look_for_keys=False)
            stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode(errors='replace')
            err = stderr.read().decode(errors='replace')
            code = stdout.channel.recv_exit_status()
            c.close()
            return {'output': out, 'error': err, 'exit_code': code}

        return await loop.run_in_executor(None, _do)
    except Exception as e:
        return {'output': '', 'error': str(e), 'exit_code': -1}


async def telnet_exec(host: str, port: int, user: str, pwd: str,
                      cmd: str, timeout: int = 10) -> dict:
    """telnetlib3 Telnet command execution."""
    try:
        import telnetlib3
        reader, writer = await asyncio.wait_for(
            telnetlib3.open_connection(host, port), timeout=timeout
        )
        output = []

        try:
            data = await asyncio.wait_for(reader.readuntil(b'ogin:'), timeout=8)
            output.append(data.decode(errors='replace'))
            writer.write(user + '\n')
            data = await asyncio.wait_for(reader.readuntil(b'assword:'), timeout=8)
            output.append(data.decode(errors='replace'))
            writer.write(pwd + '\n')
            await asyncio.sleep(1)
        except asyncio.TimeoutError:
            pass

        writer.write(cmd + '\n')
        await asyncio.sleep(2)
        try:
            rest = await asyncio.wait_for(reader.read(4096), timeout=timeout)
            output.append(rest.decode(errors='replace'))
        except asyncio.TimeoutError:
            pass

        writer.close()
        return {'output': ''.join(output), 'error': '', 'exit_code': 0}
    except Exception as e:
        return {'output': '', 'error': str(e), 'exit_code': -1}


# ═══ Device Batch Execution ═══════════════════════════════════════

async def execute_on_devices(topo_id: str) -> str:
    """Execute real operations on topology devices, return results."""
    async with async_session() as s:
        topo = (await s.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )).scalar_one_or_none()
    if not topo:
        return "拓扑未找到"

    devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
    if not devices:
        return "拓扑中无设备"

    results = []
    for dev in devices:
        name = dev.get('name', '?')
        ip = dev.get('ip', '')
        pwd = dev.get('password', '')
        user = dev.get('username', 'admin')
        login = dev.get('loginMethod', 'ssh')
        dtype = dev.get('type', '?')

        if not ip:
            results.append(f"  {name}: 无 IP，跳过")
            continue

        alive = await socket_check(ip, 22 if login == 'ssh' else 23)
        if not alive:
            results.append(f"  {name} ({ip}): 不可达（端口不通）")
            continue

        if not pwd:
            results.append(f"  {name} ({ip}): 可达但缺密码，无法登录")
            continue

        if login == 'ssh':
            cmd = "show version | include uptime" if dtype in ('router', 'switch') else "uname -a"
            out = await ssh_exec(ip, user, pwd, cmd)
            if out.get('exit_code', -1) == 0:
                ver = (out.get('output', '')[:80]).replace('\n', ' ')
                results.append(f"  {name} ({ip}): 已连接，{ver}")
            else:
                results.append(f"  {name} ({ip}): SSH 失败 - {out.get('error', '?')[:60]}")
        elif login == 'telnet':
            cmd = "show version" if dtype in ('router', 'switch') else "whoami"
            out = await telnet_exec(ip, dev.get('port', 23), user, pwd, cmd)
            if out.get('exit_code', -1) == 0:
                results.append(f"  {name} ({ip}): Telnet 已连接")
            else:
                results.append(f"  {name} ({ip}): Telnet 失败 - {out.get('error', '?')[:60]}")
        else:
            results.append(f"  {name} ({ip}): 不支持的连接方式 {login}")

    return "\n".join(results) if results else "无设备可执行"


# ═══ Config Verification ══════════════════════════════════════════

VERIFY_COMMANDS = {
    "端口": "show interface status | include connected",
    "VLAN": "show vlan brief",
    "路由": "show ip route | include ^[OSB]",
    "生成树": "show spanning-tree | include Root|Desg",
    "ACL": "show access-lists | include permit|deny",
    "OSPF": "show ip ospf neighbor",
    "链路聚合": "show etherchannel summary",
    "DHCP": "show ip dhcp binding",
    "端口安全": "show port-security",
    "状态": "show version",
}


def get_verify_command(task: str, vendor: str = "*") -> Optional[str]:
    """Return verification command for a config task."""
    task_lower = task.lower()
    for keyword, cmd in VERIFY_COMMANDS.items():
        if keyword in task_lower or keyword in task:
            return cmd
    return None


async def run_e2e_test(devices: list, links: list) -> str:
    """End-to-end test: check device connectivity and protocol status."""
    results = []
    checked_ips = set()

    for dev in devices[:5]:
        ip = dev.get("ip", "")
        if ip and ip not in checked_ips:
            checked_ips.add(ip)
            alive = await socket_check(ip, 22)
            results.append(f"{dev.get('name', '?')} ({ip}): {'可达' if alive else '不可达'}")

    for link in links[:5]:
        a = link.get("source", "")
        b = link.get("target", "")
        if a and b:
            results.append(f"链路 {a}<->{b}: 需SSH验证")

    return "E2E 测试报告:\n" + "\n".join(results) if results else "无可测设备"


# ═══ Tool Call Router ═════════════════════════════════════════════

async def execute_tool_call(name: str, args: dict, context: dict) -> str:
    """Execute a single tool call, return JSON string result."""
    try:
        if name == "list_topologies":
            async with async_session() as s:
                topos = (await s.execute(
                    select(TopologySave).order_by(TopologySave.updated_at.desc())
                )).scalars().all()
            return json.dumps([
                {"id": t.id[:8], "name": t.name, "device_count": t.device_count, "link_count": t.link_count}
                for t in topos
            ], ensure_ascii=False)

        elif name == "list_subagents":
            async with async_session() as s:
                subs = (await s.execute(select(Subagent))).scalars().all()
                topos = (await s.execute(select(TopologySave))).scalars().all()
                tmap = {t.id: t.name for t in topos}
            return json.dumps([
                {"id": s.id, "name": s.name, "status": s.status, "topology": tmap.get(s.topology_id, "?")}
                for s in subs
            ], ensure_ascii=False)

        elif name == "get_topology_detail":
            async with async_session() as s:
                topo = (await s.execute(
                    select(TopologySave).where(TopologySave.id.like(f"{args['topo_id']}%"))
                )).scalar_one_or_none()
            if not topo:
                return json.dumps({"error": "拓扑未找到"})
            devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
            return json.dumps({
                "name": topo.name, "device_count": topo.device_count, "link_count": topo.link_count,
                "devices": [{"name": d.get("name"), "type": d.get("type"), "ip": d.get("ip")} for d in devices]
            }, ensure_ascii=False)

        elif name == "get_dashboard_stats":
            from ..routes.dashboard import get_stats_data
            return json.dumps(await get_stats_data(), ensure_ascii=False)

        elif name == "start_discovery":
            return await _tool_start_discovery(args)

        elif name == "command_subagent":
            from ..routes.agent_chat import _internal_dispatch
            result = await _internal_dispatch(args["subagent_id"], args["task"])
            return json.dumps({"dispatched": True, "result": result[:300]}, ensure_ascii=False)

        elif name == "get_device_info":
            return await _tool_get_device_info(args, context)

        elif name == "check_topology_devices":
            topo_id = context.get("topo_id", "")
            result = await execute_on_devices(topo_id)
            return json.dumps({"result": result}, ensure_ascii=False)

        elif name == "ssh_execute":
            out = await ssh_exec(args["host"], args.get("username", ""), args.get("password", ""), args["command"], args.get("port", 22))
            return json.dumps(out, ensure_ascii=False)

        elif name == "ping_device":
            alive = await socket_check(args["host"], 22)
            return json.dumps({"host": args["host"], "reachable": alive}, ensure_ascii=False)

        elif name == "verify_config":
            verify_cmd = get_verify_command(args.get("config_type", ""), args.get("vendor", "*"))
            if not verify_cmd:
                verify_cmd = "show version"
            out = await ssh_exec(args["host"], args["username"], args["password"], verify_cmd)
            return json.dumps({
                "verified": out.get("exit_code", -1) == 0,
                "command": verify_cmd,
                "output": out.get("stdout", "")[:300]
            }, ensure_ascii=False)

        elif name == "e2e_test":
            async with async_session() as s:
                topo = (await s.execute(
                    select(TopologySave).where(TopologySave.id == args["topo_id"])
                )).scalar_one_or_none()
            if not topo:
                return json.dumps({"error": "拓扑未找到"})
            devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
            links = json.loads(topo.link_data) if isinstance(topo.link_data, str) else (topo.link_data or [])
            report = await run_e2e_test(devices, links)
            return json.dumps({"report": report}, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {name}"})

    except Exception as e:
        return json.dumps({"error": f"工具执行异常: {str(e)}"})


# ═══ Tool Helpers ═════════════════════════════════════════════════

async def _tool_start_discovery(args: dict) -> str:
    """Handle start_discovery tool call."""
    method = args.get("method", "lan")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if method == "seed":
                seeds = args.get("seeds", [])
                if not seeds:
                    return json.dumps({"ok": False, "error": "种子发现需要至少一台种子设备的IP和凭据"})
                resp = await client.post(
                    "http://127.0.0.1:8000/opsbrain/api/v1/topology/discover-seed",
                    json={"seeds": seeds, "max_devices": 50, "max_depth": 5},
                )
            elif method == "serial":
                console_ip = args.get("console_ip", "")
                if not console_ip:
                    return json.dumps({"ok": False, "error": "串口服务器模式需要提供 console_ip"})
                ports_resp = await client.post(
                    "http://127.0.0.1:8000/opsbrain/api/v1/topology/console-discover",
                    json={"ip": console_ip, "start": 2001, "end": 2048},
                )
                return json.dumps(ports_resp.json(), ensure_ascii=False)
            elif method == "import":
                return json.dumps({
                    "ok": False,
                    "error": "Excel导入请通过Web界面的知识库导入按钮上传文件",
                    "hint": "打开 Knowledge Base 页面，点击右上角 导入 按钮上传 CSV/XLSX",
                })
            else:
                resp = await client.post(
                    "http://127.0.0.1:8000/opsbrain/api/v1/topology/discover",
                    json={"method": "lan", "username": args.get("username", "admin"), "password": args.get("password", "")},
                )
            result = resp.json()
            return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"嗅探失败: {str(e)}"})


async def _tool_get_device_info(args: dict, context: dict) -> str:
    """Handle get_device_info tool call."""
    topo_id = context.get("topo_id", "")
    async with async_session() as s:
        topo = (await s.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )).scalar_one_or_none()
    if not topo:
        return json.dumps({"error": "拓扑未找到"})
    devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
    for d in devices:
        if d.get("name", "").lower() == args["device_name"].lower():
            return json.dumps({
                "found": True, "name": d.get("name"), "type": d.get("type"),
                "ip": d.get("ip"), "vendor": d.get("vendor"),
                "login_method": d.get("loginMethod"), "has_password": bool(d.get("password")),
                "status": d.get("status", "unknown")
            }, ensure_ascii=False)
    return json.dumps({"found": False, "error": f"设备 {args['device_name']} 未找到"})
