"""Add Agent chat API and PUT update endpoint to backend."""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("129.211.28.47", 22, "root", "248640", allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

# ── 1. Update topology routes: add PUT ────────────────────────────
with sftp.open("/root/opsbrain/web/backend/app/routes/topology.py", "r") as f:
    topo = f.read().decode()

put_code = """
@topology_router.put("/{topo_id}")
async def update_topology(topo_id: str, data: dict, user: User = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TopologySave).where(TopologySave.id == topo_id)
        )
        topo = result.scalar_one_or_none()
        if not topo:
            raise HTTPException(status_code=404, detail="Topology not found")
        if "name" in data:
            topo.name = data["name"]
        if "device_data" in data:
            topo.device_data = _json.dumps(data["device_data"])
            topo.device_count = len(data["device_data"])
        if "link_data" in data:
            topo.link_data = _json.dumps(data["link_data"])
            topo.link_count = len(data["link_data"])
        await session.commit()
        await session.refresh(topo)
    log.info("Topology updated", extra={"id": topo_id})
    return topo.to_dict()
"""

if "update_topology" not in topo:
    topo = topo.rstrip() + "\n" + put_code + "\n"
    with sftp.open("/root/opsbrain/web/backend/app/routes/topology.py", "w") as f:
        f.write(topo.encode())
    print("[OK] PUT update_topology added")
else:
    print("[OK] PUT already exists")

# ── 2. Create Agent chat route ────────────────────────────────────
agent_code = r'''"""
OpsBrain Web — Agent Chat Routes (Model API)
"""
from __future__ import annotations

import json as _json
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, TopologySave, ApiKey

import logging
log = logging.getLogger(__name__)
agent_router = APIRouter()


def _build_context(topo: dict) -> str:
    """Build system prompt with full topology context."""
    devices = topo.get("device_data", [])
    links = topo.get("link_data", [])
    analysis = topo.get("analysis", "")

    ctx = "You are OpsBrain Agent, an AI network operations assistant.\n\n"
    ctx += f"## Current Topology: {topo.get('name', 'Unknown')}\n\n"

    ctx += "### Devices\n"
    for d in devices:
        t = d.get("type", "unknown")
        tc = {"router":"Router","switch":"Switch","firewall":"Firewall","server":"Server"}.get(t,t)
        ctx += f"  [{tc}] {d.get('name','?')} | Vendor: {d.get('vendor','?')} | "
        ctx += f"IP: {d.get('ip','N/A')} | Login: {d.get('loginMethod','ssh')}\n"
        ctx += f"    Credentials: {d.get('username','?')}/{d.get('password','***')}\n"

    ctx += "\n### Links\n"
    for l in links:
        arrow = "<->" if l.get("confirmed") else "->"
        ctx += f"  {l.get('source','?')}:{l.get('sourcePort','?')} {arrow} {l.get('target','?')}:{l.get('targetPort','?')} ({l.get('speed','?')})\n"

    if analysis:
        ctx += f"\n### Analysis\n{analysis}\n"

    ctx += "\n### Instructions\n"
    ctx += "1. Always specify exact interface/port when configuring\n"
    ctx += "2. Use device vendor to determine correct CLI commands\n"
    ctx += "3. For servers, identify OS before suggesting commands\n"
    ctx += "4. Consider link topology to determine which port to configure\n"
    ctx += "5. Reply in Chinese (user's language)\n"
    return ctx


def _api_defaults(provider: str):
    bases = {"openai":"https://api.openai.com/v1","deepseek":"https://api.deepseek.com/v1","siliconflow":"https://api.siliconflow.cn/v1","ollama":"http://localhost:11434/v1"}
    models = {"openai":"gpt-4o","deepseek":"deepseek-chat","siliconflow":"Pro/deepseek-ai/DeepSeek-V3","ollama":"llama3.2"}
    return bases.get(provider, "https://api.openai.com/v1"), models.get(provider, "gpt-4o")


@agent_router.post("/{topo_id}/chat")
async def agent_chat(topo_id: str, data: dict, user: User = Depends(get_current_user)):
    message = data.get("message", "")
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message required")

    # Load topology
    async with async_session() as session:
        result = await session.execute(select(TopologySave).where(TopologySave.id == topo_id))
        topo = result.scalar_one_or_none()
    if not topo:
        raise HTTPException(status_code=404, detail="Topology not found")

    topo_dict = topo.to_dict()

    # Load active API key
    async with async_session() as session:
        result = await session.execute(select(ApiKey).where(ApiKey.is_active == True))
        api_rows = result.scalars().all()
        key = next((k for k in api_rows if k.is_default), api_rows[0] if api_rows else None)

    if not key:
        return {"reply": "No API Key configured. Go to Settings > API Management to add one.", "model": "none"}

    api_base, default_model = _api_defaults(key.provider)
    base_url = key.api_base or api_base
    model = key.model or default_model

    messages = [
        {"role": "system", "content": _build_context(topo_dict)},
        {"role": "user", "content": message},
    ]

    try:
        async with httpx.AsyncClient(timeout=60) as http:
            resp = await http.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json={"model": model, "messages": messages, "max_tokens": 2048, "temperature": 0.3},
                headers={"Authorization": f"Bearer {key.api_key}", "Content-Type": "application/json"},
            )
        if resp.status_code == 200:
            body = resp.json()
            reply = body["choices"][0]["message"]["content"]
            return {"reply": reply, "model": model}
        else:
            return {"reply": f"Model API error: HTTP {resp.status_code} - {resp.text[:200]}", "model": model}
    except Exception as e:
        return {"reply": f"Model API request failed: {str(e)}", "model": model}
'''

with sftp.open("/root/opsbrain/web/backend/app/routes/agent_chat.py", "w") as f:
    f.write(agent_code.encode())
print("[OK] agent_chat.py created")

# ── 3. Register router ────────────────────────────────────────────
with sftp.open("/root/opsbrain/web/backend/app/routes/__init__.py", "r") as f:
    init = f.read().decode()

if "agent_router" not in init:
    init = init.replace(
        "from .topology import topology_router",
        "from .topology import topology_router\nfrom .agent_chat import agent_router"
    )
    init = init.replace(
        'prefix="/topology", tags=["Topology"])',
        'prefix="/topology", tags=["Topology"])\nrouter.include_router(agent_router, prefix="/agent", tags=["Agent"])'
    )
    with sftp.open("/root/opsbrain/web/backend/app/routes/__init__.py", "w") as f:
        f.write(init.encode())
    print("[OK] Agent router registered")

# ── 4. Add httpx to requirements ──────────────────────────────────
with sftp.open("/root/opsbrain/web/backend/requirements.txt", "r") as f:
    reqs = f.read().decode()
if "httpx" not in reqs:
    reqs += "httpx>=0.27\n"
    with sftp.open("/root/opsbrain/web/backend/requirements.txt", "w") as f:
        f.write(reqs.encode())
    print("[OK] httpx added")

sftp.close()
client.close()
print("Backend ready. Build & deploy next.")
