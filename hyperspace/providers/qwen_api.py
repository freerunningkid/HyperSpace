"""Qwen API Provider —— thin wrapper around OpenAICompatibleProvider."""

from __future__ import annotations

from .base import CostTier, ProviderCapabilities
from .openai_compatible import OpenAICompatibleProvider


class QwenAPIProvider(OpenAICompatibleProvider):
    """Qwen（通义千问）API（OpenAI 兼容）Provider。

    环境变量：QWEN_API_KEY
    """

    def __init__(self):
        super().__init__(
            provider_id="qwen_api",
            provider_name="qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-plus",
            key_env="QWEN_API_KEY",
            capabilities=ProviderCapabilities(
                text=True,
                vision_understanding=True,
                streaming=True,
                structured_output=True,
                planning=True,
            ),
            cost_tier=CostTier.LOW_COST,
            timeout=60.0,
        )
