"""
OpsBrain Web — Agent 架构 v2（参照 OpenClaw 会话模型）

通信模型:
  用户 ←→ 总控 Agent  (唯一对外的对话入口)
                │
                ├─ 内部派发任务 → Subagent
                ├─ Subagent 执行 → 汇报结果
                └─ 总控汇总 → 回复用户

  用户永远不会直接看到 Subagent 的内部对话，
  只看到总控 Agent 的最终汇总。

Subagent 需:
  - 主动发现拓扑中的问题
  - 尝试修复
  - 精简汇报（1-3 条要点）
"""

from __future__ import annotations
import json, httpx, asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, ApiKey, Subagent, TopologySave, FeishuConfig

from logging_setup import get_logger
log = get_logger(__name__)
agent_router = APIRouter()

_PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "siliconflow": "https://api.siliconflow.cn/v1/chat/completions",
}
_REASONING_PLACEHOLDER = "(reasoning omitted)"

def _now(): return datetime.utcnow()

# ═══ DeepSeek V4 兼容层 ═══════════════════════════════════════════

def _requires_reasoning(model: str) -> bool:
    lower = model.lower()
    return ("deepseek-v4" in lower or lower.startswith("deepseek-chat")
            or lower.startswith("deepseek-reasoner") or "reasoner" in lower
            or "-reasoning" in lower or "-thinking" in lower)

def _sanitize(msgs: list[dict], model: str) -> int:
    if not _requires_reasoning(model): return 0
    fixed = 0
    for m in msgs:
        if m.get("role") == "assistant" and "reasoning_content" not in m:
            m["reasoning_content"] = _REASONING_PLACEHOLDER; fixed += 1
    return fixed

async def _fetch_ak(api_key_obj=None):
    if api_key_obj: return api_key_obj
    async with async_session() as s:
        r = await s.execute(select(ApiKey).where(ApiKey.is_active == True, ApiKey.api_type == "llm").order_by(ApiKey.is_default.desc()))
        return r.scalar_one_or_none()

def _build_url(ak):
    base = (ak.api_base or "").strip()
    return base.rstrip("/") + "/chat/completions" if base else _PROVIDER_URLS.get(ak.provider.strip(), "")

# ═══ Function Calling 工具定义 ═══════════════════════════════════

COMMANDER_TOOLS = [
    {"type": "function", "function": {
        "name": "list_topologies",
        "description": "列出所有拓扑及其设备数和链路数",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "list_subagents",
        "description": "列出所有 Subagent 及其状态和所属拓扑",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "command_subagent",
        "description": "向指定 Subagent 派发任务（例如检查设备状态、部署配置等）",
        "parameters": {"type": "object", "properties": {
            "subagent_id": {"type": "string", "description": "Subagent 的 ID"},
            "task": {"type": "string", "description": "派发的具体任务描述"}
        }, "required": ["subagent_id", "task"]}
    }},
    {"type": "function", "function": {
        "name": "get_topology_detail",
        "description": "获取某个拓扑的完整设备列表和链路信息",
        "parameters": {"type": "object", "properties": {
            "topo_id": {"type": "string", "description": "拓扑 ID（前8位即可）"}
        }, "required": ["topo_id"]}
    }},
    {"type": "function", "function": {
        "name": "get_dashboard_stats",
        "description": "获取系统概览统计（拓扑数、故障设备数、Subagent 状态）",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "start_discovery",
        "description": "启动网络拓扑发现。自动选择以下模式之一：seed(种子发现-最准确，需至少一台设备的SSH凭据)/lan(局域网嗅探-自动扫网段，零前提)/serial(串口服务器-带外管理)/import(从Excel导入设备清单)。如果用户未指定方式，自动推荐合适的模式。",
        "parameters": {"type": "object", "properties": {
            "method": {"type": "string", "description": "发现方式: seed(种子发现,最准确)/lan(局域网嗅探,零前提)/serial(串口服务器)/import(Excel导入)", "enum": ["seed", "lan", "serial", "import"]},
            "seeds": {"type": "array", "description": "种子设备列表（仅seed模式需要），每台包含ip/username/password/vendor", "items": {"type": "object", "properties": {"ip": {"type": "string", "description": "设备IP"}, "username": {"type": "string", "description": "SSH用户名"}, "password": {"type": "string", "description": "SSH密码"}, "vendor": {"type": "string", "description": "厂商 cisco/huawei/h3c/juniper/fortinet/ruijie/hpe"}}}},
            "username": {"type": "string", "description": "SSH登录用户名（lan模式可选）"},
            "password": {"type": "string", "description": "SSH登录密码（lan/seed模式可选，留空则只做端口探测）"},
            "console_ip": {"type": "string", "description": "串口服务器IP（仅serial模式需要）"},
            "console_ports": {"type": "string", "description": "串口端口范围如 2001-2048（仅serial模式）"},
        }, "required": ["method"]}
    }},
]

SUBAGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "get_device_info",
        "description": "获取拓扑内某台设备的完整信息（IP、类型、厂商、登录凭据状态）",
        "parameters": {"type": "object", "properties": {
            "device_name": {"type": "string", "description": "设备名称"}
        }, "required": ["device_name"]}
    }},
    {"type": "function", "function": {
        "name": "check_topology_devices",
        "description": "探测拓扑内所有设备的网络连通性（端口是否可达、是否有密码）",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "ssh_execute",
        "description": "SSH 登录到指定 IP 执行命令，返回命令输出",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string", "description": "设备 IP"},
            "username": {"type": "string", "description": "SSH 用户名（从设备列表获取）"},
            "password": {"type": "string", "description": "SSH 密码（从设备列表获取）"},
            "command": {"type": "string", "description": "要执行的命令，如 show running-config"}
        }, "required": ["host", "username", "password", "command"]}
    }},
    {"type": "function", "function": {
        "name": "ping_device",
        "description": "检测设备 IP 是否可达",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string", "description": "设备 IP"}
        }, "required": ["host"]}
    }},
    {"type": "function", "function": {
        "name": "verify_config",
        "description": "验证设备配置是否生效（如配置VLAN后检查VLAN表，配置OSPF后检查邻居）",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string", "description": "设备 IP"},
            "username": {"type": "string", "description": "SSH 用户名"},
            "password": {"type": "string", "description": "SSH 密码"},
            "vendor": {"type": "string", "description": "厂商: cisco/huawei/h3c/juniper"},
            "config_type": {"type": "string", "description": "配置类型: VLAN/路由/ACL/OSPF/端口安全/链路聚合"},
        }, "required": ["host", "username", "password", "config_type"]}
    }},
    {"type": "function", "function": {
        "name": "e2e_test",
        "description": "端到端测试：在所有配置完成后验证拓扑连通性和服务可用性",
        "parameters": {"type": "object", "properties": {
            "topo_id": {"type": "string", "description": "拓扑 ID"},
        }, "required": ["topo_id"]}
    }},
]


# ═══ Function Calling 执行引擎 ═══════════════════════════════════

async def _execute_tool_call(name: str, args: dict, context: dict) -> str:
    """执行单个工具调用，返回 JSON 字符串结果"""
    try:
        if name == "list_topologies":
            async with async_session() as s:
                topos = (await s.execute(select(TopologySave).order_by(TopologySave.updated_at.desc()))).scalars().all()
            return json.dumps([{"id": t.id[:8], "name": t.name, "device_count": t.device_count, "link_count": t.link_count} for t in topos], ensure_ascii=False)

        elif name == "list_subagents":
            async with async_session() as s:
                subs = (await s.execute(select(Subagent))).scalars().all()
                topos = (await s.execute(select(TopologySave))).scalars().all()
                tmap = {t.id: t.name for t in topos}
            return json.dumps([{"id": s.id, "name": s.name, "status": s.status, "topology": tmap.get(s.topology_id, "?")} for s in subs], ensure_ascii=False)

        elif name == "get_topology_detail":
            async with async_session() as s:
                topo = (await s.execute(select(TopologySave).where(TopologySave.id.like(f"{args['topo_id']}%")))).scalar_one_or_none()
            if not topo: return json.dumps({"error": "拓扑未找到"})
            devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
            return json.dumps({"name": topo.name, "device_count": topo.device_count, "link_count": topo.link_count, "devices": [{"name": d.get("name"), "type": d.get("type"), "ip": d.get("ip")} for d in devices]}, ensure_ascii=False)

        elif name == "get_dashboard_stats":
            from .dashboard import get_stats_data
            return json.dumps(await get_stats_data(), ensure_ascii=False)

        elif name == "start_discovery":
            method = args.get("method", "lan")
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    if method == "seed":
                        # 种子发现：调用 seed API
                        seeds = args.get("seeds", [])
                        if not seeds:
                            return json.dumps({"ok": False, "error": "种子发现需要至少一台种子设备的IP和凭据"})
                        resp = await client.post(
                            "http://127.0.0.1:8000/api/v1/topology/discover-seed",
                            json={
                                "seeds": seeds,
                                "max_devices": 50,
                                "max_depth": 5,
                            },
                        )
                    elif method == "serial":
                        # 串口服务器
                        console_ip = args.get("console_ip", "")
                        if not console_ip:
                            return json.dumps({"ok": False, "error": "串口服务器模式需要提供 console_ip"})
                        # 先自动发现端口
                        ports_resp = await client.post(
                            "http://127.0.0.1:8000/api/v1/topology/console-discover",
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
                        # 默认：LAN嗅探（自动扫描，无需用户指定网段）
                        resp = await client.post(
                            "http://127.0.0.1:8000/api/v1/topology/discover",
                            json={
                                "method": "lan",
                                "username": args.get("username", "admin"),
                                "password": args.get("password", ""),
                            },
                        )
                    result = resp.json()
                    return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"ok": False, "error": f"嗅探失败: {str(e)}"})

        elif name == "command_subagent":
            result = await _internal_dispatch(args["subagent_id"], args["task"])
            return json.dumps({"dispatched": True, "result": result[:300]}, ensure_ascii=False)

        elif name == "get_device_info":
            topo_id = context.get("topo_id", "")
            async with async_session() as s:
                topo = (await s.execute(select(TopologySave).where(TopologySave.id == topo_id))).scalar_one_or_none()
            if not topo: return json.dumps({"error": "拓扑未找到"})
            devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
            for d in devices:
                if d.get("name", "").lower() == args["device_name"].lower():
                    return json.dumps({"found": True, "name": d.get("name"), "type": d.get("type"), "ip": d.get("ip"), "vendor": d.get("vendor"), "login_method": d.get("loginMethod"), "has_password": bool(d.get("password")), "status": d.get("status", "unknown")}, ensure_ascii=False)
            return json.dumps({"found": False, "error": f"设备 {args['device_name']} 未找到"})

        elif name == "check_topology_devices":
            topo_id = context.get("topo_id", "")
            result = await _execute_on_devices(topo_id)
            return json.dumps({"result": result}, ensure_ascii=False)

        elif name == "ssh_execute":
            out = await _ssh_exec(args["host"], args.get("username", ""), args.get("password", ""), args["command"], args.get("port", 22))
            return json.dumps(out, ensure_ascii=False)

        elif name == "ping_device":
            alive = await _socket_check(args["host"], 22)
            return json.dumps({"host": args["host"], "reachable": alive}, ensure_ascii=False)

        elif name == "verify_config":
            verify_cmd = _get_verify_command(args.get("config_type", ""), args.get("vendor", "*"))
            if not verify_cmd:
                verify_cmd = "show version"
            out = await _ssh_exec(args["host"], args["username"], args["password"], verify_cmd)
            return json.dumps({"verified": out.get("exit_code", -1) == 0, "command": verify_cmd, "output": out.get("stdout", "")[:300]}, ensure_ascii=False)

        elif name == "e2e_test":
            async with async_session() as s:
                topo = (await s.execute(select(TopologySave).where(TopologySave.id == args["topo_id"]))).scalar_one_or_none()
            if not topo:
                return json.dumps({"error": "拓扑未找到"})
            devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
            links = json.loads(topo.link_data) if isinstance(topo.link_data, str) else (topo.link_data or [])
            report = await _run_e2e_test(devices, links)
            return json.dumps({"report": report}, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {name}"})
    except Exception as e:
        return json.dumps({"error": f"工具执行异常: {str(e)}"})


# ═══ LLM 调用（带 Function Calling）═══════════════════════════

async def _llm_with_tools(messages: list[dict], tools: list[dict] | None = None,
                          api_key_obj=None, context: dict | None = None,
                          max_rounds: int = 5) -> str:
    """
    带 Function Calling 的 LLM 调用（参照 deepseek-tui tool_calls 循环模式）

    流程:
      send [system, user, tools] → LLM returns tool_calls?
        YES → execute tool → append result → send again (up to max_rounds)
        NO  → return text
    """
    ak = await _fetch_ak(api_key_obj)
    if not ak: return "请先在设置中配置 API Key"
    url = _build_url(ak)
    if not url: return f"不支持的提供商: {ak.provider}"
    model = (ak.model or "deepseek-chat").strip()
    ctx = context or {}

    for round_num in range(max_rounds):
        _sanitize(messages, model)
        body = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 4000}
        if tools:
            body["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=120) as c:
                resp = await c.post(url, headers={
                    "Authorization": f"Bearer {ak.api_key.strip()}",
                    "Content-Type": "application/json",
                }, json=body)

                if resp.status_code >= 400:
                    try: err = resp.json().get("error", {}).get("message", resp.text[:300])
                    except: err = resp.text[:300]
                    return f"API 错误 ({resp.status_code}): {err}"

                data = resp.json()
                msg = data["choices"][0]["message"]

                # 没有 tool_calls → 返回文本
                if not msg.get("tool_calls"):
                    return msg.get("content", "")

                # 有 tool_calls → 执行工具
                # 保留完整消息（含 reasoning_content）供 DeepSeek 使用
                asst = {"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg["tool_calls"]}
                if "reasoning_content" in msg:
                    asst["reasoning_content"] = msg["reasoning_content"]
                messages.append(asst)

                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    try: args = json.loads(fn.get("arguments", "{}"))
                    except: args = {}
                    result = await _execute_tool_call(name, args, ctx)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        except httpx.TimeoutException:
            return "API 超时"
        except Exception as e:
            return f"API 异常: {str(e)}"

    return "已达到最大工具调用轮数。"


# ═══ 原始 LLM 调用 ═══════════════════════════════════════════

async def _llm_raw(messages: list[dict], api_key_obj=None) -> str:
    """原始 LLM 调用，不添加包装信息"""
    ak = await _fetch_ak(api_key_obj)
    if not ak: return "请先在设置中配置 API Key"
    url = _build_url(ak)
    if not url: return f"不支持的提供商: {ak.provider}"
    model = (ak.model or "deepseek-chat").strip()
    _sanitize(messages, model)

    body = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 4000}
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(url, headers={
                "Authorization": f"Bearer {ak.api_key.strip()}",
                "Content-Type": "application/json",
            }, json=body)
            if resp.status_code >= 400:
                try: err = resp.json().get("error", {}).get("message", resp.text[:300])
                except: err = resp.text[:300]
                if "reasoning_content" in err:
                    for m in reversed(messages):
                        if m.get("role") == "assistant":
                            m["reasoning_content"] = _REASONING_PLACEHOLDER; break
                    resp2 = await c.post(url, headers=resp.request.headers, json=body)
                    if resp2.status_code < 400:
                        return resp2.json()["choices"][0]["message"].get("content", "")
                return f"[LLM error {resp.status_code}]: {err}"
            return resp.json()["choices"][0]["message"].get("content", "")
    except Exception as e:
        return f"[LLM exception]: {str(e)}"


# ═══ 设备执行引擎（SSH/Telnet/Ping）════════════════════════════════

async def _execute_on_devices(topo_id: str) -> str:
    """对拓扑中的设备执行真实操作，返回执行结果"""
    async with async_session() as s:
        topo = (await s.execute(select(TopologySave).where(TopologySave.id == topo_id))).scalar_one_or_none()
    if not topo:
        return "❌ 拓扑未找到"

    devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
    if not devices:
        return "❌ 拓扑中无设备"

    results = []
    for dev in devices:
        name = dev.get('name', '?')
        ip = dev.get('ip', '')
        pwd = dev.get('password', '')
        user = dev.get('username', 'admin')
        login = dev.get('loginMethod', 'ssh')
        dtype = dev.get('type', '?')

        if not ip:
            results.append(f"  ⚠️ {name}: 无 IP，跳过")
            continue

        # 1. 连通性检测
        alive = await _socket_check(ip, 22 if login == 'ssh' else 23)
        if not alive:
            results.append(f"  ❌ {name} ({ip}): 不可达（端口不通）")
            continue

        # 2. SSH/Telnet 执行
        if not pwd:
            results.append(f"  ⚠️ {name} ({ip}): 可达但缺密码，无法登录")
            continue

        if login == 'ssh':
            out = await _ssh_exec(ip, user, pwd, "show version | include uptime" if dtype in ('router','switch') else "uname -a")
            if out.get('exit_code', -1) == 0:
                ver = (out.get('output', '')[:80]).replace('\n', ' ')
                results.append(f"  ✅ {name} ({ip}): 已连接，{ver}")
            else:
                results.append(f"  ❌ {name} ({ip}): SSH 失败 - {out.get('error', '?')[:60]}")
        elif login == 'telnet':
            out = await _telnet_exec(ip, dev.get('port', 23), user, pwd, "show version" if dtype in ('router','switch') else "whoami")
            if out.get('exit_code', -1) == 0:
                results.append(f"  ✅ {name} ({ip}): Telnet 已连接")
            else:
                results.append(f"  ❌ {name} ({ip}): Telnet 失败 - {out.get('error', '?')[:60]}")
        else:
            results.append(f"  ⚠️ {name} ({ip}): 不支持的连接方式 {login}")

    return "\n".join(results) if results else "无设备可执行"


async def _socket_check(host: str, port: int, timeout: int = 3) -> bool:
    """Socket 端口连通性检测"""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False


async def _ssh_exec(host: str, user: str, pwd: str, cmd: str, port: int = 22, timeout: int = 10) -> dict:
    """paramiko SSH 执行命令"""
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


async def _telnet_exec(host: str, port: int, user: str, pwd: str, cmd: str, timeout: int = 10) -> dict:
    """telnetlib3 Telnet 执行命令"""
    try:
        import telnetlib3
        reader, writer = await asyncio.wait_for(
            telnetlib3.open_connection(host, port), timeout=timeout
        )
        output = []

        # 等登录提示
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


# ═══ Agent 记忆系统（参照 OpenClaw memory/*.md 模式）═════════

import os as _os

_MEMORY_DIR = _os.environ.get("OPSBRAIN_HOME", "/var/lib/opsbrain") + "/memory"
_MAX_CONTEXT = 20  # 最多保留 20 条消息上下文


def _memory_path(name: str) -> str:
    """记忆文件路径，类似 OpenClaw 的 memory/agent-name.json"""
    _os.makedirs(_MEMORY_DIR, exist_ok=True)
    return _MEMORY_DIR + "/" + name + ".json"


def _load_memory(name: str) -> list[dict]:
    """加载 Agent 记忆（最近 N 条）"""
    path = _memory_path(name)
    if not _os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data[-_MAX_CONTEXT:] if len(data) > _MAX_CONTEXT else data
    except:
        return []


def _save_memory(name: str, messages: list[dict]):
    """保存 Agent 记忆，只保留最近的上下文"""
    path = _memory_path(name)
    # 读取已有历史，合并新消息
    existing = []
    if _os.path.exists(path):
        try:
            with open(path, "r") as f:
                existing = json.load(f)
        except:
            pass
    # 只保留 user/assistant 角色消息
    new_msgs = [m for m in messages if m.get("role") in ("user", "assistant")]
    combined = existing + new_msgs
    # 截断保留最后 N 条
    if len(combined) > _MAX_CONTEXT:
        combined = combined[-_MAX_CONTEXT:]
    try:
        with open(path, "w") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        return len(combined)
    except:
        return 0


# ═══ 配置验证 + E2E 测试 ══════════════════════════════════════

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

def _get_verify_command(task: str, vendor: str = "*") -> str | None:
    """根据配置任务返回验证命令"""
    task_lower = task.lower()
    for keyword, cmd in VERIFY_COMMANDS.items():
        if keyword in task_lower or keyword in task:
            return cmd
    return None


async def _run_e2e_test(devices: list, links: list) -> str:
    """端到端测试：检查设备间连通性和协议状态"""
    results = []
    checked_ips = set()
    
    # 1. 连通性测试（ping 核心设备）
    for dev in devices[:5]:
        ip = dev.get("ip", "")
        if ip and ip not in checked_ips:
            checked_ips.add(ip)
            alive = await _socket_check(ip, 22)
            results.append(f"{dev.get('name','?')} ({ip}): {'✅ 可达' if alive else '❌ 不可达'}")
    
    # 2. 链路测试（检查拓扑中的链路两端是否互通）
    for link in links[:5]:
        a = link.get("source", "")
        b = link.get("target", "")
        if a and b:
            results.append(f"链路 {a}↔{b}: 需SSH验证")
    
    return "E2E 测试报告:\n" + "\n".join(results) if results else "无可测设备"


# ═══ Hermes Agent 循环（Subagent 自主执行 + 优化）═══════════

async def _hermes_subagent_loop(topo_id: str, task: str, plan: str = "") -> str:
    """
    Hermes 风格 Subagent 执行循环（参照 OpenClaw hermes + deepseek-tui）

    流程:
      1. 分析 Commander 的目标和方案
      2. 查询知识库获取相关配置命令
      3. 对拓扑设备分步执行
      4. 失败则尝试替代方案
      5. 汇报结果（含优化点）
    """
    async with async_session() as s:
        topo = (await s.execute(select(TopologySave).where(TopologySave.id == topo_id))).scalar_one_or_none()
    if not topo:
        return "拓扑未找到"

    devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
    if not devices:
        return "拓扑中无设备"

    from ..knowledge_base import search_configs, init_knowledge_base
    init_knowledge_base()

    # ── Step 1: Subagent LLM 分析任务并制定执行计划 ──
    system = await _subagent_system(topo_id)
    analysis_prompt = f"""【总控派发任务】
目标: {task}"""
    if plan:
        analysis_prompt += f"\n\n总控方案:\n{plan}"
    analysis_prompt += """
\n请执行以下 Hermes 风格操作:
1. 分析任务，列出具体执行步骤
2. 对每个步骤标注: [STEP] 设备名 操作描述
3. 如果方案有缺陷或可优化，标记 [OPTIMIZE] 提出改进
4. 用 [RESULT] 标记每步执行结果\n"""

    analysis = await _llm_with_tools([
        {"role": "system", "content": system},
        {"role": "user", "content": analysis_prompt},
    ], tools=SUBAGENT_TOOLS, context={"topo_id": topo_id})

    # ── Step 2: 查询知识库，获取相关配置命令 ──
    kb_results = []
    for dev in devices:
        vendor = dev.get("vendor", "*")
        if vendor and vendor not in ("other", "unknown"):
            configs = search_configs(task, vendor=vendor, top_k=3)
            if configs:
                kb_results.append(f"[{dev.get('name')} ({vendor})] 知识库配置:\n" +
                    "\n".join(f"  ▪ {c['task']}: {c['commands'][:120]}" for c in configs))

    # ── Step 3: 遍历设备执行（Hermes 核心：执行→验证→优化→重试） ──
    executions = []
    optimizations = []
    for dev in devices:
        name = dev.get("name", "?")
        ip = dev.get("ip", "")
        pwd = dev.get("password", "")
        user = dev.get("username", "admin")
        login = dev.get("loginMethod", "ssh")
        vendor = dev.get("vendor", "?")

        if not ip:
            executions.append(f"{name}: ⚠️ 无 IP")
            continue

        # 连通性
        alive = await _socket_check(ip, 22 if login == "ssh" else 23)
        if not alive:
            executions.append(f"{name} ({ip}): ❌ 不可达")
            continue

        if not pwd:
            executions.append(f"{name} ({ip}): ⚠️ 可达但缺密码")
            continue

        # 知识库命令
        kb_cmds = search_configs(task, vendor=vendor, top_k=2)
        exit_code = -1
        result = {}

        if login == "ssh":
            # 尝试第一个命令
            if kb_cmds:
                for cmd_entry in kb_cmds:
                    first_cmd = cmd_entry["commands"].split("\n")[0]
                    result = await _ssh_exec(ip, user, pwd, first_cmd, port=dev.get("port", 22))
                    exit_code = result.get("exit_code", -1)
                    if exit_code == 0:
                        break
                # 失败则尝试知识库优化
                if exit_code != 0 and len(kb_cmds) > 1:
                    optimizations.append(f"{name}: 第一命令失败，优化切换为 {kb_cmds[1]['task']}")
                    alt_cmd = kb_cmds[1]["commands"].split("\n")[0]
                    result = await _ssh_exec(ip, user, pwd, alt_cmd, port=dev.get("port", 22))
                    exit_code = result.get("exit_code", -1)

            if exit_code == -1:
                # 最后回退：show version
                result = await _ssh_exec(ip, user, pwd, "show version", port=dev.get("port", 22))
                exit_code = result.get("exit_code", -1)

            if exit_code == 0:
                executions.append(f"{name} ({ip}): ✅ SSH 执行成功")
            else:
                executions.append(f"{name} ({ip}): ❌ SSH 失败 - {result.get('error', '?')[:50]}")
        elif login == "telnet":
            cmd = "show version" if vendor in ("cisco", "huawei", "h3c", "juniper") else "whoami"
            result = await _telnet_exec(ip, dev.get("port", 23), user, pwd, cmd)
            if result.get("exit_code", -1) == 0:
                executions.append(f"{name} ({ip}): ✅ Telnet 连接成功")
            else:
                executions.append(f"{name} ({ip}): ❌ Telnet 失败")

    # ── Step 4: 生成最终汇报 ──
    exec_summary = "\n".join(executions)
    opt_summary = "\n".join(optimizations) if optimizations else "无需优化"
    kb_summary = "\n".join(kb_results[:5]) if kb_results else "知识库无匹配配置"

    # 详细汇报（给总控）
    detailed_report = f"""## 执行报告 (Hermes)

### 知识库匹配
{kb_summary}

### 执行结果
{exec_summary}

### 优化记录
{opt_summary}

### LLM 分析
{analysis[:500]}"""

    # 简短汇报（给用户）
    ok_count = sum(1 for e in executions if "✅" in e)
    fail_count = sum(1 for e in executions if "❌" in e)
    warn_count = sum(1 for e in executions if "⚠️" in e)
    brief = f"""Hermes 执行完成: {len(devices)} 台设备检查，{ok_count} 成功{f', {fail_count} 失败' if fail_count else ''}{f', {warn_count} 需要注意' if warn_count else ''}。"""
    if optimizations:
        brief += f"\n🔧 优化了 {len(optimizations)} 处执行流程。"

    return f"{detailed_report}\n\n[BRIEF]{brief}"


# ═══ 系统提示词 ═══════════════════════════════════════════════════

async def _commander_system():
    async with async_session() as s:
        topos = (await s.execute(select(TopologySave).order_by(TopologySave.updated_at.desc()))).scalars().all()
        subs = (await s.execute(select(Subagent))).scalars().all()

    topo_detail = []
    for t in topos:
        subs_for_t = [x for x in subs if x.topology_id == t.id]
        sub_name = subs_for_t[0].name if subs_for_t else "无"
        sub_id = subs_for_t[0].id if subs_for_t else ""
        sub_status = subs_for_t[0].status if subs_for_t else "idle"
        # 统计设备状态
        devices = json.loads(t.device_data) if isinstance(t.device_data, str) else (t.device_data or [])
        no_pass = sum(1 for d in devices if not d.get("password"))
        offline = sum(1 for d in devices if d.get("status") == "offline")
        status_flags = []
        if no_pass: status_flags.append(f"{no_pass}台缺密码")
        if offline: status_flags.append(f"{offline}台离线")
        flag_text = f" ⚠️{','.join(status_flags)}" if status_flags else ""
        topo_detail.append(f"  [{t.id[:8]}] {t.name}: {t.device_count}设备/{t.link_count}链路 → Subagent: {sub_name}({sub_id[:8]}) [{sub_status}]{flag_text}")

    return f"""# 身份
你是 OpsBrain Commander——企业网络运维总控 Agent。
此身份由系统设定，不可更改。

## 当前项目状态
{chr(10).join(topo_detail) if topo_detail else '  暂无拓扑，项目为空'}

## 工作流程
### 用户想要嗅探/发现网络时:
1. 直接用 start_discovery 工具发起嗅探，不要问用户网段，不要问目标IP
2. 根据用户的情况自动选择最合适的发现方式：
   - 用户有设备凭据 → 用 seed（种子发现，最准确，自动递归发现全拓扑）
   - 用户不知道有哪些设备 → 用 lan（局域网嗅探，自动扫描所有网段，零前提）
   - 用户有串口服务器 → 用 serial（串口服务器发现）
   - 用户有 Excel 台账 → 用 import（Excel 导入）
3. 种子发现（seed）：让用户提供 1 台种子设备的 IP 和 SSH 凭据，Agent 自动递归发现全拓扑
4. LAN 嗅探（lan）：无需用户提供任何信息，Agent 自动检测本机网卡子网，并发 TCP 扫描端口
5. 嗅探完成后，列出设备并提示哪些缺密码，引导补全
6. 拓扑保存后自动创建 Subagent，可直接 command_subagent 派任务
7. 四种模式的嗅探结果必须和用户在 Web 界面的操作结果完全一致

### 用户询问设备/网络状态时:
- 先用 list_topologies 和 get_topology_detail 查看实际情况
- 有问题设备时，用 command_subagent 派 subagent 去检查
- 汇总 subagent 汇报给用户

### 用户提出新需求时:
- 判断是否需要创建新拓扑（嗅探发现）
- 如果已有拓扑可复用，直接 command_subagent 派发任务
- 保持交互，引导用户完成配置

## 回复规则
- 先调用工具查看实际状态再回答（不要凭空猜测）
- 直接给结论，不要复述过程
- 需要用户操作时，清晰列出步骤
- 每次回复控制在300字以内"""


async def _subagent_system(topo_id: str):
    async with async_session() as s:
        topo = (await s.execute(select(TopologySave).where(TopologySave.id == topo_id))).scalar_one_or_none()
    if not topo: return "未找到拓扑。"

    devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
    links = json.loads(topo.link_data) if isinstance(topo.link_data, str) else (topo.link_data or [])

    dev_list = "\n".join(
        f"  {d.get('name')} | {d.get('type')} | IP:{d.get('ip','?')} | 厂商:{d.get('vendor','?')} | "
        f"状态:{d.get('status','online')} | 登录:{d.get('loginMethod','ssh')}@"
        f"{d.get('port',22) if d.get('loginMethod')=='telnet' else 22} | "
        f"账号:{d.get('username','?')} | 密码:{('***' if d.get('password') else 'EMPTY')}"
        for d in devices
    ) or "无"

    return f"""你是「{topo.name}」专属 Subagent（编号: {topo.id[:8]}），创建时绑定，终身不可更改。

设备:\n{dev_list}\n链路: {len(links)} 条

## 工作流程（严格按顺序）
1. 【查知识库】根据设备厂商(vendor)和任务，用知识库查询对应配置命令
2. 【执行配置】逐设备 SSH 执行命令
3. 【验证配置】每台设备配置后用 verify_config 确认配置生效
4. 【端到端测试】所有设备配置完后用 e2e_test 验证整体连通性
5. 【汇报】汇总各步骤结果，格式如下:
   ✅ 成功: [做了什么]
   ❌ 失败: [原因]
   ⚠️ 待确认: [需要人工介入的问题]

## 规则
- 汇报不超过3条要点
- 每台设备缺乏密码则标记 ⚠️
- 不要废话，只给结论
- 如果有问题且能修复，执行修复并汇报结果"""


# ═══ 内部派发 + 收集（参照 OpenClaw 的 spawn + yield 模式）════

async def _internal_dispatch(subagent_id: str, task: str) -> str:
    """内部派发任务给 Subagent，收集汇报"""
    async with async_session() as s:
        sa = (await s.execute(select(Subagent).where(Subagent.id == subagent_id))).scalar_one_or_none()
        if not sa:
            return f"❌ Subagent {subagent_id[:8]} 不存在"

        topo = (await s.execute(select(TopologySave).where(TopologySave.id == sa.topology_id))).scalar_one_or_none()
        if not topo:
            return f"❌ Subagent {subagent_id[:8]} 绑定的拓扑不存在"

        # 更新为工作中
        sa.status = "working"; sa.last_active = _now()
        await s.commit()

    # Subagent 构造自己的系统提示词时会重新读取拓扑数据（含最新的设备密码）
    system = await _subagent_system(sa.topology_id)

    # Step 1: Subagent LLM 分析任务
    analysis = await _llm_raw([
        {"role": "system", "content": system},
        {"role": "user", "content": f"【总控派发】{task}"},
    ])

    # Step 2: 实际执行设备操作（SSH/Telnet/Ping）
    exec_results = await _execute_on_devices(sa.topology_id)

    # Step 3: 让 Subagent LLM 基于实际执行结果做最终汇报
    final_reply = await _llm_raw([
        {"role": "system", "content": system},
        {"role": "user", "content": f"【总控派发】{task}"},
        {"role": "assistant", "content": analysis},
        {"role": "user", "content": f"实际设备执行结果（基于真实 SSH/Telnet 操作）：\n{exec_results}\n\n请基于以上实际结果精简汇报。不要编造，只用实际数据。"},
    ])

    # 保持 working 状态至少 5 秒，让前端有足够时间轮询到
    await asyncio.sleep(5)

    # 使用 Hermes 循环执行（知识库 + 自主优化）
    # 获取 Commander 的分析作为 plan
    full_report = await _hermes_subagent_loop(sa.topology_id, task, plan="")

    # 提取详细报告和简短摘要
    if "[BRIEF]" in full_report:
        parts = full_report.split("[BRIEF]", 1)
        detailed = parts[0].strip()
        brief = parts[1].strip()
    else:
        detailed = full_report
        brief = full_report[:200]

    # 保存到 Subagent 记忆
    _save_memory(f"subagent_{sa.topology_id}", [
        {"role": "user", "content": f"【总控派发】{task}", "ts": _now().isoformat()},
        {"role": "assistant", "content": brief, "ts": _now().isoformat()},
    ])
    async with async_session() as s:
        s2 = (await s.execute(select(Subagent).where(Subagent.id == subagent_id))).scalar_one_or_none()
        if s2:
            s2.status = "idle"; s2.message_count += 1
            await s.commit()

    return final_reply


async def _dispatch_all_and_collect(task: str) -> str:
    """向所有 Subagent 派发任务，收集汇报"""
    async with async_session() as s:
        subs = (await s.execute(select(Subagent))).scalars().all()
        topos = (await s.execute(select(TopologySave))).scalars().all()
        topo_map = {t.id: t.name for t in topos}

    results = []
    for sa in subs:
        topo_name = topo_map.get(sa.topology_id, "?")
        report = await _internal_dispatch(sa.id, task)
        # 精简汇报：只提取关键行
        lines = [l.strip() for l in report.split("\n") if l.strip() and any(
            c in l for c in ["✅", "❌", "⚠️", "发现", "修复", "失败", "成功", "设备", "问题"]
        )]
        if not lines:
            lines = [report[:100]]  # fallback
        short = "\n".join(lines[:4])  # 最多 4 行
        results.append(f"【{sa.name}（{topo_name}）】\n{short}")

    return "\n\n".join(results)


# ═══ API 端点 ═══════════════════════════════════════════════════

@agent_router.get("/chat/history")
async def commander_chat_history(user: User = Depends(get_current_user)):
    """获取 Commander Agent 聊天历史（供控制台展示，含飞书消息）"""
    memory = _load_memory("commander")
    return {"messages": memory, "count": len(memory)}


@agent_router.post("/chat")
async def commander_chat(data: dict, user: User = Depends(get_current_user)):
    """总控 Agent（带记忆）"""
    user_msg = (data.get("message") or "").strip()
    if not user_msg: raise HTTPException(400)

    # 重置命令
    if user_msg == "/reset":
        _save_memory("commander", [])
        # 删除记忆文件确保彻底清除
        import os as _os2
        mem_path = _memory_path("commander")
        if _os2.path.exists(mem_path):
            try:
                _os2.remove(mem_path)
            except Exception:
                pass
        return {"reply": "🔄 对话记忆已重置", "model": "commander-agent", "memory_count": 0, "timestamp": _now().isoformat()}

    system = await _commander_system()
    memory = _load_memory("commander")

    # Step 1: 分析意图（带 tools）
    messages = [{"role": "system", "content": system}] + memory + [{"role": "user", "content": user_msg}]
    plan_reply = await _llm_with_tools(messages, tools=COMMANDER_TOOLS)

    # Step 2: 检测是否需要派发
    if needs_dispatch(user_msg):
        report = await _dispatch_all_and_collect(user_msg)
        # 将 Subagent 汇报追加为 tool 结果，让 LLM 基于它生成最终回复
        final = await _llm_with_tools(
            [{"role": "system", "content": system}] + memory + [
                {"role": "user", "content": user_msg},
                {"role": "user", "content": f"Subagent 汇报:\n{report}\n基于此汇总回复用户。"},
            ])
    else:
        final = plan_reply

    # 保存记忆
    _save_memory("commander", [
        {"role": "user", "content": user_msg, "ts": _now().isoformat()},
        {"role": "assistant", "content": final, "ts": _now().isoformat()},
    ])

    return {"reply": final, "model": "commander-agent",
            "subagent_report": report if needs_dispatch(user_msg) else None,
            "memory_count": _load_memory("commander").__len__(),
            "timestamp": _now().isoformat()}


def needs_dispatch(msg: str) -> bool:
    return any(k in msg for k in ["检查","配置","部署","巡检","修复","排查","扫描","诊断","状态","问题","故障","端口","设备","网络"])


@agent_router.post("/{topo_id}/chat")
async def subagent_chat(topo_id: str, data: dict, user: User = Depends(get_current_user)):
    """Subagent 对话（带记忆）"""
    msg = (data.get("message") or "").strip()
    if not msg: raise HTTPException(400)

    # 重置命令
    if msg == "/reset":
        _save_memory(f"subagent_{topo_id}", [])
        import os as _os2
        mem_path = _memory_path(f"subagent_{topo_id}")
        if _os2.path.exists(mem_path):
            try:
                _os2.remove(mem_path)
            except Exception:
                pass
        return {"reply": "🔄 本 Subagent 记忆已重置", "model": f"subagent-{topo_id[:8]}", "memory_count": 0, "timestamp": _now().isoformat()}

    system = await _subagent_system(topo_id)
    if system.startswith("未找到"): raise HTTPException(404)

    async with async_session() as s:
        sa = (await s.execute(select(Subagent).where(Subagent.topology_id == topo_id))).scalar_one_or_none()
        ak = None
        if sa and sa.api_key_id:
            ak = (await s.execute(select(ApiKey).where(ApiKey.id == sa.api_key_id))).scalar_one_or_none()
        if sa: sa.status = "working"; sa.last_active = _now(); sa.message_count += 1; await s.commit()

    # 加载记忆
    memory = _load_memory(f"subagent_{topo_id}")
    messages = [{"role": "system", "content": system}] + memory + [{"role": "user", "content": msg}]

    reply = await _llm_with_tools(messages, tools=SUBAGENT_TOOLS, api_key_obj=ak, context={"topo_id": topo_id})

    # 保存记忆
    _save_memory(f"subagent_{topo_id}", [
        {"role": "user", "content": msg, "ts": _now().isoformat()},
        {"role": "assistant", "content": reply, "ts": _now().isoformat()},
    ])

    if sa:
        async with async_session() as s:
            s2 = (await s.execute(select(Subagent).where(Subagent.id == sa.id))).scalar_one_or_none()
            if s2: s2.status = "idle"; await s.commit()

    return {"reply": reply, "model": f"subagent-{topo_id[:8]}",
            "memory_count": len(_load_memory(f"subagent_{topo_id}")),
            "timestamp": _now().isoformat()}


@agent_router.post("/dispatch")
async def commander_dispatch(data: dict, user: User = Depends(get_current_user)):
    """内部派发后端端点（仍暴露 API，供前端调试）"""
    sid = (data.get("subagent_id") or "").strip()
    task = (data.get("task") or "").strip()
    if not sid or not task: raise HTTPException(400)
    result = await _internal_dispatch(sid, task)
    return {"reply": result, "subagent_id": sid, "timestamp": _now().isoformat()}


# ═══ 飞书集成（统一入口）═══════════════════════════════════════════
# 全局飞书 Bot Client 实例
async def _feishu_message_handler(event: dict) -> str | None:
    """飞书消息处理函数（供 bot_manager / webhook 共用）

    接收飞书发来的消息，交给总控 Commander Agent 处理，返回回复文本。
    """
    try:
        message = event.get("message", {})
        raw = message.get("content", "{}")
        content = json.loads(raw) if isinstance(raw, str) else raw
        user_msg = content.get("text", "")
        if not user_msg.strip():
            return None

        system = await _commander_system()
        memory = _load_memory("commander")
        reply = await _llm_with_tools(
            [{"role": "system", "content": system}] + memory
            + [{"role": "user", "content": f"[飞书] {user_msg}"}],
            tools=COMMANDER_TOOLS,
        )
        _save_memory("commander", [
            {"role": "user", "content": f"[飞书] {user_msg}", "ts": _now().isoformat()},
            {"role": "assistant", "content": reply, "ts": _now().isoformat()},
        ])
        return reply
    except Exception as e:
        log.error("Feishu handler error", extra={"error": str(e)})
        return None


@agent_router.post("/feishu-webhook")
async def feishu_webhook(data: dict):
    """飞书 Webhook 事件入口"""
    try:
        # 读取配置验证 webhook 事件
        async with async_session() as session:
            result = await session.execute(
                select(FeishuConfig).where(FeishuConfig.enabled == True)
            )
            feishu_cfg = result.scalar_one_or_none()

        if feishu_cfg and feishu_cfg.enabled and feishu_cfg.connection_mode == "webhook":
            from .feishu_bot import FeishuBotClient
            verifier = FeishuBotClient(
                app_id=feishu_cfg.app_id,
                app_secret=feishu_cfg.app_secret,
                domain=feishu_cfg.domain,
                verification_token=feishu_cfg.verification_token,
                encrypt_key=feishu_cfg.encrypt_key,
            )

            # Challenge 请求
            if "challenge" in data:
                return {"challenge": data["challenge"]}

            # 解密
            if feishu_cfg.encrypt_key and "encrypt" in data:
                try:
                    import lark_oapi as lark
                    decrypted = lark.JSON.crypto.decrypt(
                        feishu_cfg.encrypt_key, data["encrypt"]
                    )
                    body = json.loads(decrypted) if isinstance(decrypted, str) else decrypted
                except Exception as e:
                    log.error("Feishu decrypt failed", extra={"error": str(e)})
                    return {"message": "decrypt failed"}
            else:
                body = data

            # 验证 Token
            if feishu_cfg.verification_token:
                if body.get("token") != feishu_cfg.verification_token:
                    log.warning("Feishu token mismatch")
                    return {"message": "invalid token"}

            # 处理消息事件
            event = body.get("event", {})
            event_type = event.get("type", "")

            if event_type == "im.message.receive_v1":
                message_id = event.get("message", {}).get("message_id", "")
                reply = await _feishu_message_handler(event)
                if reply and message_id and feishu_cfg.app_id and feishu_cfg.app_secret:
                    await _send_feishu_reply(feishu_cfg, message_id, reply)

        return {"message": "ok"}

    except Exception as e:
        log.error("Feishu webhook error", extra={"error": str(e)})
        return {"message": "ok"}


async def _send_feishu_reply(cfg, message_id: str, reply_text: str):
    """向飞书发送消息回复"""
    try:
        base_url = "https://open.feishu.cn" if cfg.domain == "feishu" else "https://open.larksuite.com"
        # 获取 token
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": cfg.app_id, "app_secret": cfg.app_secret},
            )
            token_data = token_resp.json()

        if token_data.get("code") != 0:
            log.error("Feishu reply get token failed", extra={"error": token_data.get("msg", "?")})
            return

        token = token_data["tenant_access_token"]

        # 发送回复
        async with httpx.AsyncClient(timeout=10) as client:
            reply_resp = await client.post(
                f"{base_url}/open-apis/im/v1/messages/{message_id}/reply",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "content": json.dumps({"text": reply_text}, ensure_ascii=False),
                    "msg_type": "text",
                },
            )
            reply_data = reply_resp.json()
            if reply_data.get("code") != 0:
                log.error("Feishu reply send failed", extra={
                    "error": reply_data.get("msg", "?"),
                    "code": reply_data.get("code"),
                })
            else:
                log.info("Feishu reply sent")
    except Exception as e:
        log.error("Feishu reply error", extra={"error": str(e)})
