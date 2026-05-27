"""
OpsBrain OOBM — Model API 配置

支持自定义任何兼容 OpenAI API 格式的模型提供商。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelProvider(str, Enum):
    """支持的模型提供商"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    CUSTOM = "custom"  # 任意兼容 OpenAI 的 API


MODEL_PROVIDER_BASES: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",       # DeepSeek 官方
    "siliconflow": "https://api.siliconflow.cn/v1",  # SiliconFlow
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434/v1",
    "custom": "",  # 用户自定义
}

MODEL_PROVIDER_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "deepseek": "deepseek-chat",
    "siliconflow": "Pro/deepseek-ai/DeepSeek-V3",
    "anthropic": "claude-3-5-sonnet-20241022",
    "ollama": "llama3.2",
    "custom": "",
}


class ModelConfig(BaseSettings):
    """模型 API 配置 — 所有字段以 OPSBRAIN_MODEL_ 前缀设置"""

    model_config = SettingsConfigDict(
        env_prefix="OPSBRAIN_MODEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 提供商 ─────────────────────────────────────────────────────
    provider: ModelProvider = Field(
        default=ModelProvider.DEEPSEEK,
        alias="OPSBRAIN_MODEL_PROVIDER",
        description="模型提供商",
    )

    # ── API 地址 ───────────────────────────────────────────────────
    api_base: str = Field(
        default="",
        alias="OPSBRAIN_MODEL_API_BASE",
        description="API 基础地址（为空则使用提供商默认值）",
    )

    # ── API Key ────────────────────────────────────────────────────
    api_key: str = Field(
        default="",
        alias="OPSBRAIN_MODEL_API_KEY",
        description="API Key",
    )

    # ── 模型名 ─────────────────────────────────────────────────────
    model: str = Field(
        default="",
        alias="OPSBRAIN_MODEL_MODEL",
        description="模型名称（为空则使用提供商默认值）",
    )

    # ── 请求参数 ───────────────────────────────────────────────────
    max_tokens: int = Field(
        default=4096, ge=256, le=65536,
        alias="OPSBRAIN_MODEL_MAX_TOKENS",
        description="最大输出 Token 数",
    )
    temperature: float = Field(
        default=0.3, ge=0.0, le=2.0,
        alias="OPSBRAIN_MODEL_TEMPERATURE",
        description="生成温度（0=确定性, 越高越随机）",
    )
    timeout: int = Field(
        default=60, ge=10, le=600,
        alias="OPSBRAIN_MODEL_TIMEOUT",
        description="请求超时（秒）",
    )
    max_retries: int = Field(
        default=3, ge=0, le=10,
        alias="OPSBRAIN_MODEL_MAX_RETRIES",
        description="请求重试次数",
    )

    # ── 能力开关 ───────────────────────────────────────────────────
    enabled: bool = Field(
        default=True,
        alias="OPSBRAIN_MODEL_ENABLED",
        description="是否启用模型 API",
    )

    # ── 用途配置 ───────────────────────────────────────────────────
    parse_neighbors: bool = Field(
        default=True,
        alias="OPSBRAIN_MODEL_PARSE_NEIGHBORS",
        description="使用模型辅助解析 LLDP/CDP 输出",
    )
    describe_topology: bool = Field(
        default=True,
        alias="OPSBRAIN_MODEL_DESCRIBE_TOPOLOGY",
        description="使用模型生成拓扑文字描述",
    )
    identify_device: bool = Field(
        default=True,
        alias="OPSBRAIN_MODEL_IDENTIFY_DEVICE",
        description="使用模型从 show version 识别设备型号",
    )

    @field_validator("api_base", mode="before")
    @classmethod
    def resolve_api_base(cls, v: str, info) -> str:
        """如果未设置 api_base，使用提供商默认值"""
        if v:
            return v
        # 尝试从验证上下文中获取 provider
        return v  # 留空，由运行时解析

    @field_validator("model", mode="before")
    @classmethod
    def resolve_model(cls, v: str, info) -> str:
        """如果未设置 model，使用提供商默认值"""
        if v:
            return v
        return v  # 留空，由运行时解析

    def get_api_base(self) -> str:
        """获取有效的 API 基础地址"""
        if self.api_base:
            return self.api_base
        return MODEL_PROVIDER_BASES.get(self.provider.value, "")

    def get_model(self) -> str:
        """获取有效的模型名称"""
        if self.model:
            return self.model
        return MODEL_PROVIDER_MODELS.get(self.provider.value, "gpt-4o")


# ── 全局单例 ────────────────────────────────────────────────────────────────
model_config: ModelConfig = ModelConfig()
