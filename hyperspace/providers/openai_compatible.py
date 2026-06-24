"""OpenAI-compatible Provider —— 基于 BaseProvider 接口的适配层。

内部复用现有的 openai_compat.OpenAICompatProvider（不改其签名），
封装为符合新 Provider contract 的 BaseProvider 实现。

SiliconFlow、Agnes 系列、DeepSeek API、Zhipu API、Qwen API 等
OpenAI 兼容端点均可通过此适配器接入，通过配置区分 provider id/model/base_url。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..config import ProviderCandidate
from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)
from .openai_compat import OpenAICompatProvider as _LegacyProvider

logger = logging.getLogger("hyperspace.providers.openai_compatible")


class OpenAICompatibleProvider(BaseProvider):
    """通用 OpenAI 兼容端点 Provider。

    内部委托给现有的 openai_compat.OpenAICompatProvider，
    负责：
      1. 从构造参数读取配置（不从 os.environ 写回）
      2. 将 ProviderRequest 转为旧调用格式
      3. 将旧 ProviderResponse 映射为新 ProviderResponse
    """

    def __init__(
        self,
        provider_id: str,
        provider_name: str,
        base_url: str,
        model: str,
        key_env: str,
        capabilities: ProviderCapabilities | None = None,
        cost_tier: CostTier = CostTier.UNKNOWN,
        timeout: float = 60.0,
        provider_type: ProviderType = ProviderType.API,
    ):
        self.id = provider_id
        self.type = provider_type
        self.capabilities = capabilities or ProviderCapabilities(text=True)
        self.cost_tier = cost_tier

        self._provider_name = provider_name
        self._base_url = base_url
        self._model = model
        self._key_env = key_env
        self._timeout = timeout

        # 只读取一次环境变量，存入实例属性
        self._api_key: str | None = os.environ.get(key_env)

        # 内部 legacy client（延迟创建，因为可能 key 缺失）
        self._client: _LegacyProvider | None = None

    @property
    def has_key(self) -> bool:
        """是否有可用的 API Key。"""
        return bool(self._api_key)

    def _ensure_client(self) -> _LegacyProvider:
        """获取或创建内部 legacy client。"""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    f"[{self.id}] 缺少 API Key (env: {self._key_env})"
                )
            candidate = ProviderCandidate(
                provider=self._provider_name,
                base_url=self._base_url,
                model=self._model,
                key_env=self._key_env,
            )
            self._client = _LegacyProvider(candidate, timeout=self._timeout)
        return self._client

    async def health_check(self) -> ProviderHealth:
        """轻量健康检查：检查 key 是否存在、配置是否完整。"""
        if not self._api_key:
            return ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=10.0,
                message=f"缺少 API Key (env: {self._key_env})",
            )
        if not self._base_url:
            return ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=10.0,
                message="缺少 base_url 配置",
            )
        return ProviderHealth(
            status=ProviderStatus.AVAILABLE,
            score=90.0,
            message="Key 已配置",
        )

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        """发起 chat completion，返回标准化 ProviderResponse。

        将 ProviderRequest 字段映射到旧调用格式：
          - prompt → prompt
          - context → context (system message)
          - images → images
          - files → 当前不支持（API 路径不处理文件上传）
        """
        if not self._api_key:
            return ProviderResponse(
                answer="",
                provider_id=self.id,
                provider_type=self.type,
                model=self._model,
                error=f"缺少 API Key (env: {self._key_env})",
            )

        try:
            client = self._ensure_client()
        except RuntimeError as e:
            return ProviderResponse(
                answer="",
                provider_id=self.id,
                provider_type=self.type,
                model=self._model,
                error=str(e),
            )

        try:
            legacy_resp = await client.chat(
                prompt=request.prompt,
                images=request.images,
                context=request.context,
            )
        except Exception as e:
            logger.error(f"[{self.id}] chat 失败: {e}")
            return ProviderResponse(
                answer="",
                provider_id=self.id,
                provider_type=self.type,
                model=self._model,
                error=str(e),
            )

        # 映射旧响应 → 新响应
        return ProviderResponse(
            answer=legacy_resp.text,
            provider_id=self.id,
            provider_type=self.type,
            model=legacy_resp.model or self._model,
            usage={
                "prompt_tokens": legacy_resp.prompt_tokens,
                "completion_tokens": legacy_resp.completion_tokens,
            },
            raw_metadata={
                "provider_name": self._provider_name,
                "base_url": self._base_url,
            },
        )

    async def upload_file(self, request: ProviderRequest) -> Any:
        """API provider 不支持文件上传。"""
        return {"error": "file_upload not supported for API providers"}

    async def close_session(self, session_id: str) -> None:
        """API provider 无会话概念。"""
        return None
