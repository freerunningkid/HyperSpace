"""智谱 GLM API Provider —— thin wrapper around OpenAICompatibleProvider."""

from __future__ import annotations

from .base import CostTier, ProviderCapabilities
from .openai_compatible import OpenAICompatibleProvider


class ZhipuAPIProvider(OpenAICompatibleProvider):
    """智谱 GLM API（OpenAI 兼容）Provider。

    环境变量：ZHIPU_API_KEY
    """

    def __init__(self):
        super().__init__(
            provider_id="zhipu_api",
            provider_name="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model="glm-4.7-flash",
            key_env="ZHIPU_API_KEY",
            capabilities=ProviderCapabilities(
                text=True,
                streaming=True,
                structured_output=True,
                planning=True,
            ),
            cost_tier=CostTier.FREE,
            timeout=30.0,
        )
