"""
OpsBrain — 单 Agent + 工具分组架构

架构:
  用户 ←→ Agent (唯一入口)
              │
              ├─ 直接调用工具 (拓扑/设备/知识库/系统)
              ├─ 多轮 Function Calling
              └─ 直接回复用户

工具分组:
  - 拓扑工具: list_topologies / get_topology / start_discovery
  - 设备工具: ssh_exec / ping_device / verify_config / check_devices
  - 知识库工具: search_knowledge
  - 系统工具: get_dashboard_stats
"""

from __future__ import annotations
import json, httpx, asyncio, os as _os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, ApiKey, TopologySave, FeishuConfig

from logging_setup import get_logger
log = get_logger(__name__)
agent_router = APIRouter()

_PROVIDERS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "siliconflow": "https://api.siliconflow.cn/v1/chat/completions",
}
_REASONING_PH = "(reasoning omitted)"

def _get_memory_dir() -> str:
    from platform_info import get_data_dir
    return str(get_data_dir() / "memory")

_MEMORY_DIR = _get_memory_dir()
_MAX_CTX = 20


def _now(): return datetime.utcnow()


# ═══ LLM 基础层 ═══════════════════════════════════════════════

def _needs_reasoning(model: str) -> bool:
    m = model.lower()
    return any(k in m for k in ("deepseek-v4", "deepseek-chat", "deepseek-reasoner",
                                 "reasoner", "-reasoning", "-thinking"))


def _sanitize(msgs: list[dict], model: str):
    if not _needs_reasoning(model): return
    for m in msgs:
        if m.get("role") == "assistant" and "reasoning_content" not in m:
            m["reasoning_content"] = _REASONING_PH


async def _fetch_ak(api_key_obj=None):
    if api_key_obj: return api_key_obj
    async with async_session() as s:
        r = await s.execute(select(ApiKey).where(
            ApiKey.is_active == True, ApiKey.api_type == "llm"
        ).order_by(ApiKey.is_default.desc()))
        return r.scalar_one_or_none()


def _build_url(ak):
    base = (ak.api_base or "").strip()
    return base.rstrip("/") + "/chat/completions" if base else _PROVIDERS.get(ak.provider.strip(), "")


# ═══ 记忆系统 ═══════════════════════════════════════════════════

def _mem_path(name: str) -> str:
    _os.makedirs(_MEMORY_DIR, exist_ok=True)
    return _os.path.join(_MEMORY_DIR, f"{name}.json")


def _load_mem(name: str) -> list[dict]:
    p = _mem_path(name)
    if not _os.path.exists(p): return []
    try:
        with open(p) as f: data = json.load(f)
        return data[-_MAX_CTX:]
    except: return []


def _save_mem(name: str, msgs: list[dict]):
    p = _mem_path(name)
    existing = []
    if _os.path.exists(p):
        try:
            with open(p) as f: existing = json.load(f)
        except: pass
    new = [m for m in msgs if m.get("role") in ("user", "assistant")]
    combined = (existing + new)[- _MAX_CTX:]
    try:
        with open(p, "w") as f: json.dump(combined, f, ensure_ascii=False, indent=2)
    except: pass


# ═══ 工具定义（按分组）═════════════════════════════════════════

TOOLS = [
    # ── 拓扑工具 ──
    {"type": "function", "function": {
        "name": "list_topologies",
        "description": "列出所有拓扑及其设备数、链路数、发现方式",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_topology",
        "description": "获取指定拓扑的完整设备列表和链路信息",
        "parameters": {"type": "object", "properties": {
            "topo_id": {"type": "string", "description": "拓扑 ID（前8位即可）"}
        }, "required": ["topo_id"]}
    }},
    {"type": "function", "function": {
        "name": "start_discovery",
        "description": "启动网络拓扑发现。模式: seed(种子发现,最准确,需SSH凭据)/lan(局域网嗅探,零前提)/serial(串口服务器)/import(Excel导入)。",
        "parameters": {"type": "object", "properties": {
            "method": {"type": "string", "enum": ["seed", "lan", "serial", "import"],
                       "description": "发现方式"},
            "seeds": {"type": "array", "items": {"type": "object", "properties": {
                "ip": {"type": "string"}, "username": {"type": "string"},
                "password": {"type": "string"}, "vendor": {"type": "string"}
            }}, "description": "种子设备列表（seed模式）"},
            "username": {"type": "string", "description": "SSH用户名（lan/seed可选）"},
            "password": {"type": "string", "description": "SSH密码（lan/seed可选）"},
            "console_ip": {"type": "string", "description": "串口服务器IP（serial模式）"},
            "console_ports": {"type": "string", "description": "端口范围如2001-2048（serial模式）"},
        }, "required": ["method"]}
    }},

    # ── 设备工具 ──
    {"type": "function", "function": {
        "name": "ssh_exec",
        "description": "SSH登录设备执行命令，返回输出。可用于查看配置、检查状态、验证协议等。",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string", "description": "设备IP"},
            "username": {"type": "string", "description": "SSH用户名"},
            "password": {"type": "string", "description": "SSH密码"},
            "command": {"type": "string", "description": "要执行的命令"},
            "vendor": {"type": "string", "description": "厂商(cisco/huawei/h3c/juniper)，影响命令翻译"}
        }, "required": ["host", "command"]}
    }},
    {"type": "function", "function": {
        "name": "ping_device",
        "description": "检测设备IP是否可达（TCP端口探测）",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string", "description": "设备IP"},
            "port": {"type": "integer", "description": "端口，默认22"}
        }, "required": ["host"]}
    }},
    {"type": "function", "function": {
        "name": "check_devices",
        "description": "批量检查拓扑内所有设备的连通性和登录状态",
        "parameters": {"type": "object", "properties": {
            "topo_id": {"type": "string", "description": "拓扑ID"}
        }, "required": ["topo_id"]}
    }},
    {"type": "function", "function": {
        "name": "verify_config",
        "description": "验证设备配置是否生效（如VLAN/OSPF/ACL等）",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string", "description": "设备IP"},
            "username": {"type": "string"}, "password": {"type": "string"},
            "vendor": {"type": "string", "description": "厂商"},
            "config_type": {"type": "string", "description": "配置类型: VLAN/路由/ACL/OSPF/端口安全/链路聚合"}
        }, "required": ["host", "config_type"]}
    }},

    # ── 知识库工具 ──
    {"type": "function", "function": {
        "name": "search_knowledge",
        "description": "搜索知识库中的配置模板和运维命令",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "搜索关键词，如VLAN配置、OSPF排错"},
            "vendor": {"type": "string", "description": "厂商过滤"}
        }, "required": ["query"]}
    }},

    # ── 系统工具 ──
    {"type": "function", "function": {
        "name": "get_dashboard_stats",
        "description": "获取系统概览统计（拓扑数、设备数、故障数）",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
]


# ═══ 工具执行引擎 ═══════════════════════════════════════════════

async def _exec_tool(name: str, args: dict) -> str:
    """执行单个工具调用，返回JSON字符串"""
    try:
        # ── 拓扑工具 ──
        if name == "list_topologies":
            async with async_session() as s:
                topos = (await s.execute(
                    select(TopologySave).order_by(TopologySave.updated_at.desc())
                )).scalars().all()
            return json.dumps([{
                "id": t.id[:8], "name": t.name,
                "device_count": t.device_count, "link_count": t.link_count,
                "method": t.discovery_method,
            } for t in topos], ensure_ascii=False)

        elif name == "get_topology":
            async with async_session() as s:
                topo = (await s.execute(
                    select(TopologySave).where(TopologySave.id.like(f"{args['topo_id']}%"))
                )).scalar_one_or_none()
            if not topo: return json.dumps({"error": "拓扑未找到"})
            devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
            links = json.loads(topo.link_data) if isinstance(topo.link_data, str) else (topo.link_data or [])
            return json.dumps({
                "name": topo.name, "device_count": topo.device_count,
                "link_count": topo.link_count,
                "devices": [{"name": d.get("name"), "type": d.get("type"), "ip": d.get("ip"),
                             "vendor": d.get("vendor"), "status": d.get("status", "online"),
                             "has_password": bool(d.get("password"))} for d in devices],
                "links": links[:50],
            }, ensure_ascii=False)

        elif name == "start_discovery":
            return await _do_discovery(args)

        # ── 设备工具 ──
        elif name == "ssh_exec":
            host = args["host"]
            user = args.get("username", "admin")
            pwd = args.get("password", "")
            cmd = args["command"]
            if not pwd:
                return json.dumps({"error": f"设备 {host} 缺少密码，请提供"})
            out = await _ssh_exec(host, user, pwd, cmd)
            return json.dumps(out, ensure_ascii=False)

        elif name == "ping_device":
            port = args.get("port", 22)
            alive = await _socket_check(args["host"], port)
            return json.dumps({"host": args["host"], "port": port, "reachable": alive})

        elif name == "check_devices":
            return json.dumps({"result": await _check_all_devices(args["topo_id"])}, ensure_ascii=False)

        elif name == "verify_config":
            cmd = _verify_cmd(args.get("config_type", ""), args.get("vendor", "*"))
            if not cmd: cmd = "show version"
            host = args["host"]
            user = args.get("username", "admin")
            pwd = args.get("password", "")
            if not pwd:
                return json.dumps({"error": f"设备 {host} 缺少密码"})
            out = await _ssh_exec(host, user, pwd, cmd)
            return json.dumps({
                "verified": out.get("exit_code", -1) == 0,
                "command": cmd,
                "output": out.get("stdout", "")[:500],
            }, ensure_ascii=False)

        # ── 知识库工具 ──
        elif name == "search_knowledge":
            from ..knowledge_base import search_commands, init_knowledge_base
            init_knowledge_base()
            results = search_commands(args["query"], vendor=args.get("vendor", ""), top_k=5)
            return json.dumps({"results": results}, ensure_ascii=False)

        # ── 系统工具 ──
        elif name == "get_dashboard_stats":
            from .dashboard import get_stats_data
            return json.dumps(await get_stats_data(), ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {name}"})
    except Exception as e:
        return json.dumps({"error": f"工具异常: {str(e)}"})


# ═══ 发现引擎 ═══════════════════════════════════════════════════

async def _do_discovery(args: dict) -> str:
    method = args.get("method", "lan")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if method == "seed":
                seeds = args.get("seeds", [])
                if not seeds:
                    return json.dumps({"ok": False, "error": "种子发现需要至少一台设备的IP和凭据"})
                resp = await client.post(
                    "http://127.0.0.1:8000/api/v1/topology/discover-seed",
                    json={"seeds": seeds, "max_devices": 50, "max_depth": 5},
                )
            elif method == "serial":
                console_ip = args.get("console_ip", "")
                if not console_ip:
                    return json.dumps({"ok": False, "error": "串口模式需要 console_ip"})
                resp = await client.post(
                    "http://127.0.0.1:8000/api/v1/topology/console-discover",
                    json={"ip": console_ip, "start": 2001, "end": 2048},
                )
            elif method == "import":
                return json.dumps({
                    "ok": False,
                    "error": "Excel导入请通过Web界面的知识库导入按钮上传",
                    "hint": "打开 Knowledge Base 页面，点击导入按钮上传 CSV/XLSX",
                })
            else:
                resp = await client.post(
                    "http://127.0.0.1:8000/api/v1/topology/discover",
                    json={"method": "lan", "username": args.get("username", "admin"),
                          "password": args.get("password", "")},
                )
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"发现失败: {str(e)}"})


# ═══ 设备执行引擎 ═══════════════════════════════════════════════

async def _socket_check(host: str, port: int, timeout: int = 3) -> bool:
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        w.close(); await w.wait_closed()
        return True
    except: return False


async def _ssh_exec(host: str, user: str, pwd: str, cmd: str, port: int = 22, timeout: int = 15) -> dict:
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
            return {'stdout': out, 'stderr': err, 'exit_code': code}
        return await loop.run_in_executor(None, _do)
    except Exception as e:
        return {'stdout': '', 'stderr': str(e), 'exit_code': -1}


async def _check_all_devices(topo_id: str) -> str:
    async with async_session() as s:
        topo = (await s.execute(select(TopologySave).where(TopologySave.id == topo_id))).scalar_one_or_none()
    if not topo: return "拓扑未找到"
    devices = json.loads(topo.device_data) if isinstance(topo.device_data, str) else (topo.device_data or [])
    if not devices: return "拓扑中无设备"

    results = []
    for dev in devices:
        name = dev.get('name', '?')
        ip = dev.get('ip', '')
        pwd = dev.get('password', '')
        user = dev.get('username', 'admin')
        login = dev.get('loginMethod', 'ssh')

        if not ip:
            results.append(f"⚠️ {name}: 无IP"); continue
        alive = await _socket_check(ip, 22 if login == 'ssh' else 23)
        if not alive:
            results.append(f"❌ {name} ({ip}): 不可达"); continue
        if not pwd:
            results.append(f"⚠️ {name} ({ip}): 可达但缺密码"); continue

        out = await _ssh_exec(ip, user, pwd, "show version | include uptime")
        if out.get('exit_code', -1) == 0:
            ver = (out.get('stdout', '')[:60]).replace('\n', ' ')
            results.append(f"✅ {name} ({ip}): {ver}")
        else:
            results.append(f"❌ {name} ({ip}): SSH失败 - {out.get('stderr', '?')[:40]}")

    return "\n".join(results)


VERIFY_MAP = {
    "端口": "show interface status | include connected",
    "VLAN": "show vlan brief",
    "路由": "show ip route | include ^[OSB]",
    "OSPF": "show ip ospf neighbor",
    "ACL": "show access-lists | include permit|deny",
    "链路聚合": "show etherchannel summary",
    "端口安全": "show port-security",
}

def _verify_cmd(task: str, vendor: str = "*") -> str | None:
    for kw, cmd in VERIFY_MAP.items():
        if kw in task: return cmd
    return None


# ═══ 系统提示词 ═══════════════════════════════════════════════════

async def _build_system_prompt() -> str:
    async with async_session() as s:
        topos = (await s.execute(
            select(TopologySave).order_by(TopologySave.updated_at.desc())
        )).scalars().all()

    topo_lines = []
    for t in topos:
        devices = json.loads(t.device_data) if isinstance(t.device_data, str) else (t.device_data or [])
        no_pwd = sum(1 for d in devices if not d.get("password"))
        warn = f" ⚠️{no_pwd}台缺密码" if no_pwd else ""
        topo_lines.append(f"  [{t.id[:8]}] {t.name}: {t.device_count}设备/{t.link_count}链路{warn}")

    return f"""# 身份
你是 OpsBrain AI 运维助手——企业网络运维 Agent。
直接调用工具完成任务，不需要中间层转发。

## 当前拓扑
{chr(10).join(topo_lines) if topo_lines else '  暂无拓扑'}

## 工作方式
1. 用户描述需求 → 你直接调用合适的工具 → 基于工具结果回复
2. 需要多步操作时，依次调用工具，不要跳步
3. 涉及设备操作时，先从拓扑中获取设备信息（IP/密码/厂商），再调用设备工具
4. 缺少信息时主动询问用户，不要猜测

## 回复规则
- 先调用工具查看实际状态再回答
- 直接给结论，不复述过程
- 回复控制在300字以内
- 需要用户操作时，清晰列出步骤"""


# ═══ LLM 调用（带 Function Calling 多轮循环）═══════════════════

async def _llm_chat(messages: list[dict], api_key_obj=None, max_rounds: int = 8) -> str:
    ak = await _fetch_ak(api_key_obj)
    if not ak: return "请先在设置中配置 API Key"
    url = _build_url(ak)
    if not url: return f"不支持的提供商: {ak.provider}"
    model = (ak.model or "deepseek-chat").strip()

    for _ in range(max_rounds):
        _sanitize(messages, model)
        body = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 4000, "tools": TOOLS}
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

                if not msg.get("tool_calls"):
                    return msg.get("content", "")

                asst = {"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg["tool_calls"]}
                if "reasoning_content" in msg:
                    asst["reasoning_content"] = msg["reasoning_content"]
                messages.append(asst)

                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    try: args = json.loads(fn.get("arguments", "{}"))
                    except: args = {}
                    result = await _exec_tool(fn.get("name", ""), args)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        except httpx.TimeoutException:
            return "API 超时，请稍后重试"
        except Exception as e:
            return f"API 异常: {str(e)}"

    return "已达到最大工具调用轮数"


# ═══ API 端点 ═══════════════════════════════════════════════════

@agent_router.get("/chat/history")
async def chat_history(user: User = Depends(get_current_user)):
    memory = _load_mem("agent")
    return {"messages": memory, "count": len(memory)}


@agent_router.post("/chat")
async def chat(data: dict, user: User = Depends(get_current_user)):
    user_msg = (data.get("message") or "").strip()
    if not user_msg: raise HTTPException(400)

    if user_msg == "/reset":
        _save_mem("agent", [])
        p = _mem_path("agent")
        if _os.path.exists(p):
            try: _os.remove(p)
            except: pass
        return {"reply": "对话已重置", "model": "agent", "memory_count": 0, "timestamp": _now().isoformat()}

    system = await _build_system_prompt()
    memory = _load_mem("agent")
    messages = [{"role": "system", "content": system}] + memory + [{"role": "user", "content": user_msg}]

    reply = await _llm_chat(messages)

    _save_mem("agent", [
        {"role": "user", "content": user_msg, "ts": _now().isoformat()},
        {"role": "assistant", "content": reply, "ts": _now().isoformat()},
    ])

    return {"reply": reply, "model": "agent",
            "memory_count": len(_load_mem("agent")),
            "timestamp": _now().isoformat()}


# ═══ 飞书集成 ═══════════════════════════════════════════════════

async def _feishu_handler(event: dict) -> str | None:
    try:
        message = event.get("message", {})
        raw = message.get("content", "{}")
        content = json.loads(raw) if isinstance(raw, str) else raw
        user_msg = content.get("text", "").strip()
        if not user_msg: return None

        system = await _build_system_prompt()
        memory = _load_mem("agent")
        reply = await _llm_chat(
            [{"role": "system", "content": system}] + memory
            + [{"role": "user", "content": f"[飞书] {user_msg}"}]
        )
        _save_mem("agent", [
            {"role": "user", "content": f"[飞书] {user_msg}", "ts": _now().isoformat()},
            {"role": "assistant", "content": reply, "ts": _now().isoformat()},
        ])
        return reply
    except Exception as e:
        log.error("Feishu handler error", extra={"error": str(e)})
        return None


@agent_router.post("/feishu-webhook")
async def feishu_webhook(data: dict):
    try:
        async with async_session() as session:
            result = await session.execute(select(FeishuConfig).where(FeishuConfig.enabled == True))
            cfg = result.scalar_one_or_none()

        if cfg and cfg.enabled and cfg.connection_mode == "webhook":
            from .feishu_bot import FeishuBotClient
            verifier = FeishuBotClient(
                app_id=cfg.app_id, app_secret=cfg.app_secret,
                domain=cfg.domain, verification_token=cfg.verification_token,
                encrypt_key=cfg.encrypt_key,
            )
            if "challenge" in data:
                return {"challenge": data["challenge"]}
            if cfg.encrypt_key and "encrypt" in data:
                try:
                    import lark_oapi as lark
                    decrypted = lark.JSON.crypto.decrypt(cfg.encrypt_key, data["encrypt"])
                    body = json.loads(decrypted) if isinstance(decrypted, str) else decrypted
                except Exception as e:
                    log.error("Feishu decrypt failed", extra={"error": str(e)})
                    return {"message": "decrypt failed"}
            else:
                body = data
            if cfg.verification_token and body.get("token") != cfg.verification_token:
                return {"message": "invalid token"}

            event = body.get("event", {})
            if event.get("type") == "im.message.receive_v1":
                message_id = event.get("message", {}).get("message_id", "")
                reply = await _feishu_handler(event)
                if reply and message_id and cfg.app_id and cfg.app_secret:
                    await _send_feishu_reply(cfg, message_id, reply)
        return {"message": "ok"}
    except Exception as e:
        log.error("Feishu webhook error", extra={"error": str(e)})
        return {"message": "ok"}


async def _send_feishu_reply(cfg, message_id: str, reply_text: str):
    try:
        base = "https://open.feishu.cn" if cfg.domain == "feishu" else "https://open.larksuite.com"
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                f"{base}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": cfg.app_id, "app_secret": cfg.app_secret},
            )
            td = token_resp.json()
        if td.get("code") != 0:
            log.error("Feishu token failed", extra={"error": td.get("msg", "?")})
            return
        token = td["tenant_access_token"]
        async with httpx.AsyncClient(timeout=10) as client:
            rd = (await client.post(
                f"{base}/open-apis/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"content": json.dumps({"text": reply_text}, ensure_ascii=False), "msg_type": "text"},
            )).json()
            if rd.get("code") != 0:
                log.error("Feishu reply failed", extra={"error": rd.get("msg", "?")})
    except Exception as e:
        log.error("Feishu reply error", extra={"error": str(e)})
