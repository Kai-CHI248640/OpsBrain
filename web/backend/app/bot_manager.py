"""OpsBrain — Feishu Bot Client (Singleton)

全局飞书机器人实例，供 routes 和 lifespan 共享。
"""
from __future__ import annotations

from .feishu_bot import FeishuBotClient
from logging_setup import get_logger

log = get_logger(__name__)

# 全局单例
_bot_instance: FeishuBotClient | None = None


def get_bot_instance() -> FeishuBotClient | None:
    return _bot_instance


async def start_bot(app_id: str, app_secret: str, domain: str,
                    verification_token: str = "", encrypt_key: str = "",
                    connection_mode: str = "websocket") -> bool:
    """启动/重启飞书机器人"""
    global _bot_instance

    print(f"[FEISHU DEBUG] start_bot called mode={connection_mode}", flush=True)

    # 先停止旧实例
    if _bot_instance:
        try:
            await _bot_instance.stop()
        except Exception:
            pass
        _bot_instance = None

    bot = FeishuBotClient(
        app_id=app_id,
        app_secret=app_secret,
        domain=domain,
        verification_token=verification_token,
        encrypt_key=encrypt_key,
    )

    if connection_mode == "websocket":
        try:
            await bot.start_websocket()
            print("[FEISHU DEBUG] bot_manager: WS started OK", flush=True)
            log.info("Feishu WebSocket bot started")
        except Exception as e:
            log.error("Feishu WS start failed: %s", e)
            return False
    else:
        log.info("Feishu webhook mode (no persistent connection needed)")

    _bot_instance = bot
    return True


async def stop_bot():
    """停止飞书机器人"""
    global _bot_instance
    if _bot_instance:
        try:
            await _bot_instance.stop()
        except Exception:
            pass
        _bot_instance = None
