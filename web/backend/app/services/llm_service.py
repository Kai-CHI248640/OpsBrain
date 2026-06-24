"""
OpsBrain — LLM Service

Extracted from agent_chat.py. Handles LLM provider configuration,
reasoning model compatibility, and LLM API calls (with/without tools).
"""

from __future__ import annotations

import json
from typing import Optional

import httpx
from sqlalchemy import select

from ..database import async_session
from ..models import ApiKey

from logging_setup import get_logger

log = get_logger(__name__)

# ═══ Provider Configuration ════════════════════════════════════════

_PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "siliconflow": "https://api.siliconflow.cn/v1/chat/completions",
}

_REASONING_PLACEHOLDER = "(reasoning omitted)"


def _requires_reasoning(model: str) -> bool:
    lower = model.lower()
    return ("deepseek-v4" in lower or lower.startswith("deepseek-chat")
            or lower.startswith("deepseek-reasoner") or "reasoner" in lower
            or "-reasoning" in lower or "-thinking" in lower)


def _sanitize(msgs: list[dict], model: str) -> int:
    if not _requires_reasoning(model):
        return 0
    fixed = 0
    for m in msgs:
        if m.get("role") == "assistant" and "reasoning_content" not in m:
            m["reasoning_content"] = _REASONING_PLACEHOLDER
            fixed += 1
    return fixed


async def fetch_api_key(api_key_obj=None):
    """Fetch an active LLM API key from DB (or use the provided one)."""
    if api_key_obj:
        return api_key_obj
    async with async_session() as s:
        r = await s.execute(
            select(ApiKey).where(
                ApiKey.is_active == True, ApiKey.api_type == "llm"
            ).order_by(ApiKey.is_default.desc())
        )
        return r.scalar_one_or_none()


def build_url(ak) -> str:
    """Build the chat completions URL for the given API key."""
    base = (ak.api_base or "").strip()
    return base.rstrip("/") + "/chat/completions" if base else _PROVIDER_URLS.get(ak.provider.strip(), "")


# ═══ LLM Calls ═══════════════════════════════════════════════════

async def llm_with_tools(
    messages: list[dict],
    tools: list[dict] | None = None,
    api_key_obj=None,
    context: dict | None = None,
    max_rounds: int = 5,
    tool_executor=None,
) -> str:
    """
    LLM call with Function Calling loop.

    Flow: send [system, user, tools] -> LLM returns tool_calls?
      YES -> execute tool -> append result -> send again (up to max_rounds)
      NO  -> return text

    Args:
        tool_executor: async callable(name, args, context) -> str.
                       If None, tool calls are skipped.
    """
    ak = await fetch_api_key(api_key_obj)
    if not ak:
        return "请先在设置中配置 API Key"
    url = build_url(ak)
    if not url:
        return f"不支持的提供商: {ak.provider}"
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
                    try:
                        err = resp.json().get("error", {}).get("message", resp.text[:300])
                    except Exception:
                        err = resp.text[:300]
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
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    if tool_executor:
                        result = await tool_executor(name, args, ctx)
                    else:
                        result = json.dumps({"error": "Tool execution not available"})
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        except httpx.TimeoutException:
            return "API 超时"
        except Exception as e:
            return f"API 异常: {str(e)}"

    return "已达到最大工具调用轮数。"


async def llm_raw(messages: list[dict], api_key_obj=None) -> str:
    """Raw LLM call without tool wrapping."""
    ak = await fetch_api_key(api_key_obj)
    if not ak:
        return "请先在设置中配置 API Key"
    url = build_url(ak)
    if not url:
        return f"不支持的提供商: {ak.provider}"
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
                try:
                    err = resp.json().get("error", {}).get("message", resp.text[:300])
                except Exception:
                    err = resp.text[:300]
                if "reasoning_content" in err:
                    for m in reversed(messages):
                        if m.get("role") == "assistant":
                            m["reasoning_content"] = _REASONING_PLACEHOLDER
                            break
                    resp2 = await c.post(url, headers=resp.request.headers, json=body)
                    if resp2.status_code < 400:
                        return resp2.json()["choices"][0]["message"].get("content", "")
                return f"[LLM error {resp.status_code}]: {err}"
            return resp.json()["choices"][0]["message"].get("content", "")
    except Exception as e:
        return f"[LLM exception]: {str(e)}"
