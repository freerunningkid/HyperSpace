"""ChatGLM Web Placeholder Provider —— 占位，Web 自动化未实现。

显式选择时 fallback 到 agnes_text（由 Router/Registry 层处理）。
auto 路由默认不选择此 provider。
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderNotImplemented,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)


class ChatGLMWebPlaceholderProvider(BaseProvider):
    """ChatGLM Web 占位 provider。

    当前 Web 自动化未实现，显式调用时会触发 fallback。
    """

    def __init__(self):
        self.id = "chatglm_web"
        self.type = ProviderType.PLACEHOLDER_WEB
        self.capabilities = ProviderCapabilities(
            text=True,
            planning=True,
            long_context=True,
        )
        self.cost_tier = CostTier.FREE

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            status=ProviderStatus.NOT_IMPLEMENTED,
            score=30.0,
            message="ChatGLM Web 自动化尚未实现，使用 fallback API provider",
            last_error="web_automation_not_implemented",
        )

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        raise ProviderNotImplemented(
            "ChatGLM Web provider is registered but web automation is not implemented. "
            "Use fallback provider (agnes_text) or select another provider explicitly."
        )

    async def upload_file(self, request: ProviderRequest) -> Any:
        raise ProviderNotImplemented("ChatGLM Web file upload not implemented")

    async def close_session(self, session_id: str) -> None:
        return None
