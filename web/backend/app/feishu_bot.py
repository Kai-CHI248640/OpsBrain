"""OpsBrain — Feishu Bot Client (lark-oapi SDK in thread)

在独立线程中运行 lark_oapi SDK Client 处理 WebSocket 连接和 Protobuf 消息解析。
"""

from __future__ import annotations

import asyncio
import json
import threading
import httpx
from typing import Callable, Awaitable

from logging_setup import get_logger

log = get_logger(__name__)

MessageHandler = None  # 动态类型


class FeishuBotClient:
    def __init__(self, app_id: str, app_secret: str, domain: str = "feishu",
                 verification_token: str = "", encrypt_key: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.encrypt_key = encrypt_key
        self.domain = domain
        self._running = False
        self._handler: MessageHandler | None = None
        self._ws_thread: threading.Thread | None = None

    # ── WebSocket (SDK Client in thread) ─────────────────────────

    async def _ws_event_loop(self):
        """启动 SDK Client 线程，轮询消息队列"""
        import queue as qmod
        
        event_queue: qmod.Queue = qmod.Queue()
        self._running = True
        main_loop = asyncio.get_running_loop()

        def _run_sdk():
            try:
                from lark_oapi.ws import Client
                from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
                import json as _json
                print("[FEISHU SDK] thread starting...", flush=True)
                
                ws_domain = "https://open.feishu.cn" if self.domain != "lark" else "https://open.larksuite.com"
                
                def on_message(event):
                    print(f"[FEISHU SDK] MSG received!", flush=True)
                    msg = event.event.message
                    raw = msg.content
                    try:
                        content = _json.loads(raw) if isinstance(raw, str) else raw
                        user_text = content.get("text", "") if isinstance(content, dict) else ""
                    except:
                        user_text = str(raw) if raw else ""
                    if user_text and self._handler:
                        event_queue.put(("message", {
                            "message": {
                                "chat_id": msg.chat_id,
                                "message_id": msg.message_id,
                                "content": raw,
                            },
                            "text": user_text,
                        }))
                
                handler = EventDispatcherHandler.builder("", "") \
                    .register_p2_im_message_receive_v1(on_message) \
                    .build()
                
                secret_val = self.app_secret
                client = Client(
                    app_id=self.app_id,
                    **{"app_secret": secret_val},
                    event_handler=handler,
                    domain=ws_domain,
                )
                
                client.start()
            except Exception as e:
                print(f"[FEISHU SDK] error: {e}", flush=True)
                import traceback
                traceback.print_exc()
            event_queue.put(("stopped",))

        self._ws_thread = threading.Thread(target=_run_sdk, daemon=True)
        self._ws_thread.start()
        print("[FEISHU SDK] thread started", flush=True)

        while self._running and self._ws_thread.is_alive():
            try:
                kind, data = event_queue.get_nowait()
                if kind == "message":
                    print(f"[FEISHU SDK] dequeuing message", flush=True)
                    asyncio.run_coroutine_threadsafe(
                        self._handle_and_reply(data), main_loop
                    )
                elif kind == "stopped":
                    break
            except qmod.Empty:
                pass
            await asyncio.sleep(0.3)

    async def _handle_and_reply(self, event: dict):
        print(f"[FEISHU] handle_and_reply: handler={self._handler is not None}", flush=True)
        try:
            reply = await self._handler(event) if self._handler else None
            print(f"[FEISHU] reply ready: {bool(reply)}", flush=True)
            if reply:
                await self._send_reply(event, reply)
        except Exception as e:
            print(f"[FEISHU] handler error: {e}", flush=True)

    async def _send_reply(self, event: dict, reply_text: str):
        message = event.get("message", {})
        if not isinstance(message, dict):
            return
        message_id = message.get("message_id", "")
        if not message_id:
            return

        base = "https://open.feishu.cn" if self.domain != "lark" else "https://open.larksuite.com"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{base}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            data = r.json()
        token = data.get("tenant_access_token", "")
        if not token:
            return
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                f"{base}/open-apis/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"content": json.dumps({"text": reply_text}, ensure_ascii=False), "msg_type": "text"},
            )

    # ── Webhook ──────────────────────────────────────────────────

    def verify_webhook_event(self, body: dict) -> bool:
        if "challenge" in body:
            return True
        return True

    def handle_webhook_event(self, body: dict) -> dict:
        if "challenge" in body:
            return {"challenge": body["challenge"]}
        return body

    # ── 生命周期 ──────────────────────────────────────────────────

    def set_handler(self, handler: MessageHandler):
        self._handler = handler

    async def start_websocket(self):
        asyncio.create_task(self._ws_event_loop())

    async def stop(self):
        self._running = False
