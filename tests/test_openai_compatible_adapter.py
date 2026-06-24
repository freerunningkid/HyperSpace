"""OpenAI-compatible Adapter 测试 —— 字段映射验证。

验证新 openai_compatible.py 适配层正确包装旧 OpenAICompatProvider。
纯单元测试，mock 所有外部调用。
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hyperspace.providers.base import (
    CostTier,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    ProviderType,
)
from hyperspace.providers.openai_compatible import OpenAICompatibleProvider


class TestOpenAICompatibleProvider:
    """新适配层测试 (不依赖真实 API Key)。"""

    @pytest.fixture
    def mock_env_key(self):
        """临时注入测试用环境变量。"""
        old = os.environ.get("TEST_ADAPTER_KEY")
        os.environ["TEST_ADAPTER_KEY"] = "sk-test-12345"
        yield
        if old:
            os.environ["TEST_ADAPTER_KEY"] = old
        else:
            os.environ.pop("TEST_ADAPTER_KEY", None)

    def test_constructor_reads_key_from_env_only(self, mock_env_key):
        """验证 key 只从环境变量读取，不硬编码。"""
        provider = OpenAICompatibleProvider(
            provider_id="test_api",
            provider_name="test",
            base_url="https://test.com/v1",
            model="test-model",
            key_env="TEST_ADAPTER_KEY",
            cost_tier=CostTier.FREE,
        )
        assert provider.has_key is True
        assert provider._key_env == "TEST_ADAPTER_KEY"
        # 不写入 os.environ
        assert "TEST_ADAPTER_KEY" in os.environ

    def test_constructor_with_missing_key(self):
        """key 缺失时 provider 标记为不可用。"""
        provider = OpenAICompatibleProvider(
            provider_id="test_api",
            provider_name="test",
            base_url="https://test.com/v1",
            model="test-model",
            key_env="NONEXISTENT_KEY_XYZ",
            cost_tier=CostTier.FREE,
        )
        assert provider.has_key is False
        assert provider._api_key is None

    @pytest.mark.asyncio
    async def test_chat_returns_error_without_key(self):
        """无 key 时 chat 返回错误而非抛异常。"""
        provider = OpenAICompatibleProvider(
            provider_id="test_api",
            provider_name="test",
            base_url="https://test.com/v1",
            model="test-model",
            key_env="NONEXISTENT_KEY_XYZ",
            cost_tier=CostTier.FREE,
        )
        req = ProviderRequest(prompt="hello", provider_id="test_api")
        resp = await provider.chat(req)
        assert resp.error is not None
        assert "缺少 API Key" in resp.error

    @pytest.mark.asyncio
    async def test_chat_maps_fields_correctly(self, mock_env_key):
        """验证旧 ProviderResponse → 新 ProviderResponse 字段映射。"""
        provider = OpenAICompatibleProvider(
            provider_id="test_api",
            provider_name="test",
            base_url="https://test.com/v1",
            model="test-model",
            key_env="TEST_ADAPTER_KEY",
            cost_tier=CostTier.LOW_COST,
        )

        # Mock 内部 legacy client 的 chat 方法
        mock_legacy_resp = MagicMock()
        mock_legacy_resp.text = "Hello from legacy"
        mock_legacy_resp.model = "test-model-v2"
        mock_legacy_resp.provider = "test"
        mock_legacy_resp.prompt_tokens = 10
        mock_legacy_resp.completion_tokens = 20

        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=mock_legacy_resp)
        provider._ensure_client = MagicMock(return_value=mock_client)

        req = ProviderRequest(
            prompt="hello",
            provider_id="test_api",
            images=["test.jpg"],
            context="system context",
        )
        resp = await provider.chat(req)

        assert resp.answer == "Hello from legacy"
        assert resp.provider_id == "test_api"
        assert resp.provider_type == ProviderType.API
        assert resp.model == "test-model-v2"
        assert resp.usage["prompt_tokens"] == 10
        assert resp.usage["completion_tokens"] == 20
        assert resp.error is None

    @pytest.mark.asyncio
    async def test_health_check_with_key(self, mock_env_key):
        """有 key 时 health 返回 AVAILABLE。"""
        provider = OpenAICompatibleProvider(
            provider_id="test_api",
            provider_name="test",
            base_url="https://test.com/v1",
            model="test-model",
            key_env="TEST_ADAPTER_KEY",
        )
        health = await provider.health_check()
        assert health.score >= 80

    @pytest.mark.asyncio
    async def test_health_check_without_key(self):
        """无 key 时 health 返回 UNAVAILABLE。"""
        provider = OpenAICompatibleProvider(
            provider_id="test_api",
            provider_name="test",
            base_url="https://test.com/v1",
            model="test-model",
            key_env="NONEXISTENT_KEY_XYZ",
        )
        health = await provider.health_check()
        assert health.score < 30
