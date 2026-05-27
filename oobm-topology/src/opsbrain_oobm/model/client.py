"""
OpsBrain OOBM — Model API 客户端

统一的模型 API 客户端抽象层。
默认使用 OpenAI 兼容接口（支持 DeepSeek / SiliconFlow / Ollama 等）。
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..logging_setup import get_logger
from .config import ModelConfig, model_config as cfg

log = get_logger(__name__)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    log.warning("httpx not installed; model API disabled")


# ═══════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════

class ChatMessage:
    """单条聊天消息"""
    def __init__(self, role: str, content: str):
        self.role = role  # system | user | assistant
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class ChatResponse:
    """模型返回"""
    def __init__(
        self,
        content: str,
        model: str = "",
        usage: Optional[dict] = None,
        success: bool = True,
        error: Optional[str] = None,
        latency_ms: float = 0.0,
    ):
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.success = success
        self.error = error
        self.latency_ms = latency_ms

    def __bool__(self) -> bool:
        return self.success


# ═══════════════════════════════════════════════════════════════════════════
# 抽象基类
# ═══════════════════════════════════════════════════════════════════════════

class ModelClient(ABC):
    """模型 API 客户端抽象基类"""

    @abstractmethod
    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """发送聊天请求"""
        ...

    @abstractmethod
    def check_connection(self) -> dict:
        """检查 API 连通性"""
        ...


# ═══════════════════════════════════════════════════════════════════════════
# OpenAI 兼容客户端（覆盖 DeepSeek / SiliconFlow / Ollama 等）
# ═══════════════════════════════════════════════════════════════════════════

class OpenAIClient(ModelClient):
    """
    OpenAI 兼容 API 客户端
    适用于: OpenAI / DeepSeek / SiliconFlow / Ollama / 任意自定义端点
    """

    def __init__(self, config: Optional[ModelConfig] = None):
        self._config = config or cfg
        self._base_url = self._config.get_api_base().rstrip("/")
        self._api_key = self._config.api_key
        self._model = self._config.get_model()
        self._timeout = self._config.timeout
        self._max_retries = self._config.max_retries

        if not HAS_HTTPX:
            log.error("httpx required for model API")
            return

        # 复用连接池
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )

        log.info(
            "OpenAI client initialized",
            extra={
                "provider": self._config.provider.value,
                "base_url": self._base_url,
                "model": self._model,
            },
        )

    # ── 核心方法 ────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponse:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            **kwargs: 覆盖配置的参数（temperature, max_tokens 等）

        Returns:
            ChatResponse
        """
        if not HAS_HTTPX:
            return ChatResponse(
                content="", success=False,
                error="httpx package not installed",
            )

        if not self._api_key:
            return ChatResponse(
                content="", success=False,
                error="OPSBRAIN_MODEL_API_KEY not configured",
            )

        payload = {
            "model": kwargs.pop("model", self._model),
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.pop("temperature", cfg.temperature),
            "max_tokens": kwargs.pop("max_tokens", cfg.max_tokens),
            **kwargs,
        }

        last_error: Optional[str] = None
        start = time.monotonic()

        for attempt in range(self._max_retries + 1):
            try:
                resp = self._http.post(
                    "/chat/completions",
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    latency = (time.monotonic() - start) * 1000

                    choice = data["choices"][0]
                    content = choice["message"]["content"]
                    usage = data.get("usage", {})

                    log.debug(
                        "Model chat success",
                        extra={
                            "model": self._model,
                            "latency_ms": round(latency),
                            "input_tokens": usage.get("prompt_tokens", 0),
                            "output_tokens": usage.get("completion_tokens", 0),
                        },
                    )

                    return ChatResponse(
                        content=content,
                        model=self._model,
                        usage=usage,
                        latency_ms=latency,
                    )

                elif resp.status_code == 429:
                    # 限流，退避重试
                    wait = min(2 ** attempt * 2, 30)
                    log.warning(
                        "Rate limited, retrying",
                        extra={
                            "attempt": attempt + 1,
                            "wait_seconds": wait,
                        },
                    )
                    time.sleep(wait)
                    last_error = f"Rate limited (429), retried {attempt + 1} times"
                    continue

                else:
                    error_body = resp.text[:500]
                    last_error = f"HTTP {resp.status_code}: {error_body}"
                    log.warning(
                        "Model API error",
                        extra={
                            "status": resp.status_code,
                            "attempt": attempt + 1,
                        },
                    )

                    if resp.status_code >= 500:
                        time.sleep(2 ** attempt)
                        continue

                    break

            except httpx.TimeoutException:
                last_error = "Request timed out"
                log.warning("Model API timeout", extra={"attempt": attempt + 1})
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)

            except httpx.ConnectError as e:
                last_error = f"Connection failed: {e}"
                log.warning("Model API connection error",
                            extra={"error": str(e)})
                break  # 连接不通，不重试

            except Exception as e:
                last_error = str(e)
                log.warning("Model API unexpected error",
                            extra={"error": str(e)})
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)

        return ChatResponse(
            content="",
            success=False,
            error=last_error or "Unknown error",
        )

    # ── 系统 Prompt 辅助 ─────────────────────────────────────────────

    def chat_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> ChatResponse:
        """带系统消息的对话"""
        messages = [
            ChatMessage("system", system_prompt),
            ChatMessage("user", user_prompt),
        ]
        return self.chat(messages, **kwargs)

    # ── 连通性检查 ──────────────────────────────────────────────────

    def check_connection(self) -> dict:
        """检查 API 连通性"""
        if not HAS_HTTPX:
            return {"status": "error", "message": "httpx not installed"}

        result = self.chat_with_system(
            "You are a helpful assistant.",
            "Reply with exactly: OK",
            max_tokens=10,
            temperature=0,
        )

        if result:
            return {
                "status": "ok",
                "model": self._model,
                "base_url": self._base_url,
                "latency_ms": round(result.latency_ms),
                "response": result.content[:200],
            }
        else:
            return {
                "status": "error",
                "model": self._model,
                "base_url": self._base_url,
                "error": result.error,
            }

    def close(self) -> None:
        """关闭 HTTP 连接池"""
        if HAS_HTTPX and hasattr(self, "_http"):
            self._http.close()


# ═══════════════════════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════════════════════

def create_client(
    config: Optional[ModelConfig] = None,
) -> Optional[ModelClient]:
    """
    根据配置创建模型客户端

    Returns:
        ModelClient 实例，若禁用或配置不完整则返回 None
    """
    conf = config or cfg

    if not conf.enabled:
        log.info("Model API disabled by configuration")
        return None

    if not conf.api_key:
        log.warning(
            "Model API key not configured; "
            "set OPSBRAIN_MODEL_API_KEY or OPSBRAIN_MODEL_ENABLED=false"
        )
        return None

    provider = conf.provider.value

    # 所有兼容 OpenAI 接口的提供商
    openai_compatible = {
        "openai", "deepseek", "siliconflow", "ollama", "custom",
    }

    if provider in openai_compatible:
        return OpenAIClient(conf)

    log.warning(f"Unsupported provider: {provider}")
    return None


# ── 便捷用法 ───────────────────────────────────────────────────────────────

_default_client: Optional[ModelClient] = None


def get_client() -> Optional[ModelClient]:
    """获取默认客户端（单例）"""
    global _default_client
    if _default_client is None and cfg.enabled:
        _default_client = create_client()
    return _default_client


def chat(messages: list[ChatMessage], **kwargs) -> ChatResponse:
    """便捷调用：使用默认客户端发送消息"""
    client = get_client()
    if not client:
        return ChatResponse(
            content="", success=False,
            error="Model API not available",
        )
    return client.chat(messages, **kwargs)


def chat_with_system(system: str, user: str, **kwargs) -> ChatResponse:
    """便捷调用：带系统消息的对话"""
    client = get_client()
    if not client:
        return ChatResponse(
            content="", success=False,
            error="Model API not available",
        )
    return client.chat_with_system(system, user, **kwargs)
