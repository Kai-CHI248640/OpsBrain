"""OpsBrain Web — Feishu Integration Routes

飞书机器人集成设置向导，参考 OpenClaw 飞书插件设计：
1. 用户选择连接模式（WebSocket / Webhook）
2. 选择设置方式（扫码 / 手动输入）
3. 配置凭证
4. 测试连接
5. 飞书只绑定总控 Commander Agent
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, FeishuConfig
from ..schemas import FeishuConfigUpdate, FeishuTestRequest

from logging_setup import get_logger

log = get_logger(__name__)
feishu_router = APIRouter()

# ── 飞书开放平台基础 URL ──────────────────────────────────────────────
_FEISHU_BASE = "https://open.feishu.cn"
_LARK_BASE = "https://open.larksuite.com"
_FEISHU_ACCOUNTS = "https://accounts.feishu.cn"
_LARK_ACCOUNTS = "https://accounts.larksuite.com"
# 注册路径（参考 OpenClaw app-registration 实现）
_REGISTRATION_PATH = "/oauth/v1/app/registration"


def _base_url(domain: str) -> str:
    return _FEISHU_BASE if domain == "feishu" else _LARK_BASE


def _accounts_url(domain: str) -> str:
    return _FEISHU_ACCOUNTS if domain == "feishu" else _LARK_ACCOUNTS


# ── Pydantic 请求模型 ──────────────────────────────────────────────────

class QRBeginRequest(BaseModel):
    domain: str = Field(default="feishu", pattern=r"^(feishu|lark)$")


class QRBeginResponse(BaseModel):
    device_code: str
    qr_url: str
    user_code: str
    interval: int
    expire_in: int


class QRPollRequest(BaseModel):
    device_code: str
    domain: str = Field(default="feishu", pattern=r"^(feishu|lark)$")
    interval: int = Field(default=5, ge=1, le=30)


class QRPollResponse(BaseModel):
    status: str  # pending | success | access_denied | expired | timeout | error
    app_id: str = ""
    app_secret: str = ""
    open_id: str = ""
    error: str = ""


async def _post_registration(accounts_url: str, body: dict) -> dict:
    """向飞书注册服务发送 POST 请求（form-urlencoded）
    
    参考 OpenClaw app-registration.js 的 postRegistration 实现：
    - Content-Type: application/x-www-form-urlencoded
    - 超时: 10s
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{accounts_url}{_REGISTRATION_PATH}",
            data=body,  # httpx 会自动编码为 form-urlencoded
        )
        return resp.json()


# ═══════════════════════════════════════════════════════════════════════
# ① 扫码注册流程（参考 OpenClaw 飞书插件 app-registration）
# ═══════════════════════════════════════════════════════════════════════

@feishu_router.post("/qr/begin", response_model=QRBeginResponse)
async def feishu_qr_begin(
    req: QRBeginRequest,
    user: User = Depends(get_current_user),
):
    """Step 1: 初始化飞书应用注册，返回 QR 码 URL 和设备码"""
    domain = req.domain
    accounts_url = _accounts_url(domain)

    # 检查环境是否支持 client_secret 方式
    init_data = await _post_registration(accounts_url, {"action": "init"})
    supported = init_data.get("supported_auth_methods", [])
    if "client_secret" not in supported:
        raise HTTPException(400, "当前环境不支持扫码注册，请使用手动输入方式")

    # 发起注册
    begin_data = await _post_registration(accounts_url, {
        "action": "begin",
        "archetype": "PersonalAgent",
        "auth_method": "client_secret",
        "request_user_info": "open_id",
    })

    if "device_code" not in begin_data:
        raise HTTPException(502, f"注册服务响应异常: {begin_data}")

    # 构建 QR 码 URL（加上 from 和 tp 参数，参考 OpenClaw）
    qr_url = begin_data.get("verification_uri_complete", "")
    if qr_url:
        parsed = urllib.parse.urlparse(qr_url)
        qs = urllib.parse.parse_qs(parsed.query)
        qs["from"] = ["oc_onboard"]
        qs["tp"] = ["ob_cli_app"]
        parsed = parsed._replace(query=urllib.parse.urlencode(qs, doseq=True))
        qr_url = urllib.parse.urlunparse(parsed)

    log.info("Feishu QR begin", extra={
        "device_code": begin_data.get("device_code", "")[:8] + "...",
    })

    return QRBeginResponse(
        device_code=begin_data["device_code"],
        qr_url=qr_url or "",
        user_code=begin_data.get("user_code", ""),
        interval=begin_data.get("interval", 5),
        expire_in=begin_data.get("expire_in", 600),
    )


@feishu_router.post("/qr/poll", response_model=QRPollResponse)
async def feishu_qr_poll(
    req: QRPollRequest,
    user: User = Depends(get_current_user),
):
    """Step 2: 轮询扫码结果"""
    accounts_url = _accounts_url(req.domain)
    try:
        data = await _post_registration(accounts_url, {
            "action": "poll",
            "device_code": req.device_code,
        })
    except Exception as e:
        return QRPollResponse(status="error", error=str(e))

    # 检查是否成功
    if data.get("client_id") and data.get("client_secret"):
        log.info("Feishu QR poll success", extra={
            "app_id": data["client_id"][:8] + "...",
        })
        return QRPollResponse(
            status="success",
            app_id=data["client_id"],
            app_secret=data["client_secret"],
            open_id=data.get("user_info", {}).get("open_id", ""),
        )

    # 错误状态
    error = data.get("error", "")
    if error == "authorization_pending":
        return QRPollResponse(status="pending")
    elif error == "slow_down":
        return QRPollResponse(status="pending")
    elif error == "access_denied":
        return QRPollResponse(status="access_denied", error="用户在飞书端拒绝了授权")
    elif error == "expired_token":
        return QRPollResponse(status="expired", error="二维码已过期，请重新扫码")
    else:
        return QRPollResponse(status="error", error=data.get("error_description", "未知错误"))


# ═══════════════════════════════════════════════════════════════════════
# ② 配置管理
# ═══════════════════════════════════════════════════════════════════════

@feishu_router.get("/config")
async def get_feishu_config(user: User = Depends(get_current_user)):
    """获取飞书集成配置"""
    async with async_session() as session:
        result = await session.execute(select(FeishuConfig).order_by(FeishuConfig.created_at.desc()))
        config = result.scalar_one_or_none()
    if not config:
        return {
            "configured": False,
            "enabled": False,
            "app_id": "",
            "app_secret": "",
            "domain": "feishu",
            "connection_mode": "webhook",
            "verification_token": "",
            "encrypt_key": "",
            "webhook_path": "/opsbrain/api/v1/agent/feishu-webhook",
            "group_policy": "allowlist",
            "require_mention": True,
            "dm_policy": "pairing",
        }
    d = config.to_dict()
    d["configured"] = bool(config.app_id and config.app_secret)
    return d


@feishu_router.put("/config")
async def update_feishu_config(
    req: FeishuConfigUpdate,
    user: User = Depends(get_current_user),
):
    """更新飞书集成配置，保存后自动重启飞书机器人"""
    async with async_session() as session:
        result = await session.execute(select(FeishuConfig).order_by(FeishuConfig.created_at.desc()))
        config = result.scalar_one_or_none()

        if not config:
            from ..models import FeishuConfig as FeishuConfigModel
            config = FeishuConfigModel()
            session.add(config)

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await session.commit()
        await session.refresh(config)

    log.info("Feishu config updated", extra={
        "connection_mode": config.connection_mode,
        "domain": config.domain,
        "enabled": config.enabled,
    })

    # 配置更新后自动重启飞书机器人
    if config.enabled and config.app_id and config.app_secret:
        await _ensure_bot_running()
    else:
        from ..bot_manager import stop_bot
        await stop_bot()

    result = config.to_dict()
    result["configured"] = bool(config.app_id and config.app_secret)
    return result


@feishu_router.post("/test")
async def test_feishu_connection(
    req: FeishuTestRequest,
    user: User = Depends(get_current_user),
):
    """测试飞书连接
    
    如果 app_secret 为空或以 "****" 开头（掩码），从数据库中加载真实值。
    """
    # 如果 app_secret 是掩码或空字符串，从数据库加载真实值
    app_secret = req.app_secret
    if not app_secret or app_secret.startswith("****"):
        async with async_session() as session:
            result = await session.execute(
                select(FeishuConfig).order_by(FeishuConfig.created_at.desc())
            )
            stored = result.scalar_one_or_none()
            if stored and stored.app_secret:
                app_secret = stored.app_secret
                log.info("Loaded real app_secret from DB for test")

    if not app_secret:
        return {"ok": False, "error": "App Secret 未配置，请先保存飞书配置"}

    try:
        if req.connection_mode == "webhook":
            return await _test_webhook_mode(req, app_secret)
        elif req.connection_mode == "websocket":
            return await _test_websocket_mode(req, app_secret)
        else:
            raise HTTPException(400, f"不支持的连接模式: {req.connection_mode}")
    except HTTPException:
        raise
    except Exception as e:
        log.error("Feishu test failed", extra={"error": str(e)})
        return {"ok": False, "error": str(e)}


@feishu_router.post("/reset")
async def reset_feishu_config(user: User = Depends(get_current_user)):
    """重置飞书配置"""
    async with async_session() as session:
        result = await session.execute(select(FeishuConfig).order_by(FeishuConfig.created_at.desc()))
        config = result.scalar_one_or_none()
        if config:
            await session.delete(config)
            await session.commit()
    # 停止机器人
    from ..bot_manager import stop_bot
    await stop_bot()
    return {"message": "飞书配置已重置"}


# ═══════════════════════════════════════════════════════════════════════
# ③ 测试逻辑
# ═══════════════════════════════════════════════════════════════════════

def _safe_json_parse(text: str) -> dict:
    """安全 JSON 解析，忽略响应末尾的多余字符（Feishu API 有时返回多余数据）"""
    import json
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text.strip())
    return obj


async def _call_feishu_token_api(base_url: str, app_id: str, app_secret: str) -> dict:
    """安全调用飞书 token 接口"""
    url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "app_id": app_id,
                "app_secret": app_secret,
            })
            text = resp.text
            log.info("Feishu token API: status=%d len=%d", resp.status_code, len(text))
            return _safe_json_parse(text)
    except Exception as e:
        log.error("Feishu token API failed: %s", str(e))
        return {"code": -1, "msg": f"请求飞书API失败: {str(e)}"}


async def _test_webhook_mode(req: FeishuTestRequest, real_secret: str) -> dict:
    base_url = _base_url(req.domain or "feishu")
    data = await _call_feishu_token_api(base_url, req.app_id, real_secret)

    code = data.get("code", -1)
    if code == 0:
        return {"ok": True, "message": "✅ 凭据验证成功，可正常获取 Access Token", "expire": data.get("expire", 0)}
    else:
        return {"ok": False, "error": f"凭据验证失败: {data.get('msg', '未知错误')}", "code": code}


async def _test_websocket_mode(req: FeishuTestRequest, real_secret: str) -> dict:
    base_url = _base_url(req.domain or "feishu")
    token_data = await _call_feishu_token_api(base_url, req.app_id, real_secret)

    if token_data.get("code") != 0:
        return {"ok": False, "error": f"凭据验证失败: {token_data.get('msg', '未知错误')}"}

    token = token_data["tenant_access_token"]
    ws_url = f"{base_url}/open-apis/ws/v1/endpoint"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            ws_resp = await client.post(
                ws_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            ws_data = ws_resp.json()
    except Exception as e:
        log.error("Feishu WS endpoint check failed", extra={"error": str(e)})
        return {"ok": True, "message": "✅ 凭据验证成功（WebSocket 端点检查非必须）"}

    if ws_data.get("code") == 0:
        return {"ok": True, "message": "✅ WebSocket 连接可用", "endpoint": ws_data.get("data", {}).get("endpoint", "")}
    return {"ok": True, "message": "✅ 凭据验证成功（WebSocket 端点未启用，不影响使用）"}


# ═══════════════════════════════════════════════════════════════════════
# ④ 飞书 Bot 生命周期管理
# ═══════════════════════════════════════════════════════════════════════

async def _ensure_bot_running():
    """从数据库加载配置并确保飞书机器人正在运行"""
    print("[FEISHU DEBUG] _ensure_bot_running called", flush=True)
    from ..bot_manager import start_bot, stop_bot, get_bot_instance
    from .agent_chat import _feishu_message_handler
    print("[FEISHU DEBUG] imports OK", flush=True)

    cfg = await _load_bot_config()
    print(f"[FEISHU DEBUG] cfg={bool(cfg)}", flush=True)
    if not cfg:
        print("[FEISHU DEBUG] no config, stopping bot", flush=True)
        await stop_bot()
        return

    # 设置消息处理器
    print(f"[FEISHU DEBUG] calling start_bot mode={cfg.get('connection_mode')}", flush=True)
    ok = await start_bot(
        app_id=cfg["app_id"],
        app_secret=cfg["app_secret"],
        domain=cfg["domain"],
        verification_token=cfg.get("verification_token", ""),
        encrypt_key=cfg.get("encrypt_key", ""),
        connection_mode=cfg["connection_mode"],
    )
    print(f"[FEISHU DEBUG] start_bot returned {ok}", flush=True)
    if ok:
        bot = get_bot_instance()
        if bot:
            bot.set_handler(_feishu_message_handler)


async def _load_bot_config() -> dict | None:
    """从数据库加载飞书配置"""
    print("[FEISHU DEBUG] _load_bot_config called", flush=True)
    try:
        async with async_session() as session:
            result = await session.execute(select(FeishuConfig).order_by(FeishuConfig.created_at.desc()))
            config = result.scalar_one_or_none()
            if config and config.enabled and config.app_id and config.app_secret:
                return {
                    "app_id": config.app_id,
                    "app_secret": config.app_secret,
                    "domain": config.domain,
                    "connection_mode": config.connection_mode,
                    "verification_token": config.verification_token or "",
                    "encrypt_key": config.encrypt_key or "",
                }
    except Exception:
        pass
    return None
