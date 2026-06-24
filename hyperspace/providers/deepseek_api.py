"""DeepSeek API Provider —— thin wrapper around OpenAICompatibleProvider."""

from __future__ import annotations

from .base import CostTier, ProviderCapabilities
from .openai_compatible import OpenAICompatibleProvider


class DeepSeekAPIProvider(OpenAICompatibleProvider):
    """DeepSeek 官方 API（OpenAI 兼容）Provider。

    环境变量：DEEPSEEK_API_KEY
    """

    def __init__(self):
        super().__init__(
            provider_id="deepseek_api",
            provider_name="deepseek",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            key_env="DEEPSEEK_API_KEY",
            capabilities=ProviderCapabilities(
                text=True,
                streaming=True,
                structured_output=True,
                planning=True,
                long_context=True,
            ),
            cost_tier=CostTier.LOW_COST,
            timeout=60.0,
        )
