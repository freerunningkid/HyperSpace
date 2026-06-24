"""Provider Registry 测试 —— 注册/筛选/fallback/配置加载

纯单元测试，不使用真实 API Key。
"""

import os
import tempfile
from pathlib import Path

import pytest

from hyperspace.providers.base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)
from hyperspace.providers.registry import ProviderRegistry


class DummyAPIProvider(BaseProvider):
    def __init__(self, pid="dummy_api", **caps_overrides):
        self.id = pid
        self.type = ProviderType.API
        caps = ProviderCapabilities(text=True)
        for k, v in caps_overrides.items():
            setattr(caps, k, v)
        self.capabilities = caps
        self.cost_tier = CostTier.FREE

    async def health_check(self):
        return ProviderHealth(status=ProviderStatus.AVAILABLE, score=90.0, message="ok")

    async def chat(self, request):
        return ProviderResponse(answer=f"reply from {self.id}", provider_id=self.id, provider_type=self.type)

    async def upload_file(self, request):
        return {"id": "f1"}


class DummyPlaceholderProvider(BaseProvider):
    def __init__(self, pid="dummy_placeholder"):
        self.id = pid
        self.type = ProviderType.PLACEHOLDER_WEB
        self.capabilities = ProviderCapabilities(text=True, planning=True)
        self.cost_tier = CostTier.FREE

    async def health_check(self):
        return ProviderHealth(status=ProviderStatus.NOT_IMPLEMENTED, score=30.0, message="not implemented")

    async def chat(self, request):
        from hyperspace.providers.base import ProviderNotImplemented
        raise ProviderNotImplemented("web automation not implemented")

    async def upload_file(self, request):
        from hyperspace.providers.base import ProviderNotImplemented
        raise ProviderNotImplemented("not implemented")


class TestProviderRegistry:
    """核心 Registry 功能测试。"""

    def test_register_and_get(self):
        reg = ProviderRegistry()
        p = DummyAPIProvider("test_provider")
        reg.register(p)
        assert reg.get("test_provider") is p
        assert reg.get("nonexistent") is None

    def test_list_all(self):
        reg = ProviderRegistry()
        p1 = DummyAPIProvider("p1")
        p2 = DummyAPIProvider("p2")
        reg.register(p1)
        reg.register(p2)
        assert len(reg.list_all()) == 2
        assert len(reg.list_ids()) == 2

    def test_fallback_map(self):
        reg = ProviderRegistry()
        p1 = DummyAPIProvider("primary")
        p2 = DummyAPIProvider("fallback")
        reg.register_with_fallback(p1, "fallback")
        reg.register(p2)
        assert reg.get_fallback_for("primary") is p2
        assert reg.get_fallback_for("fallback") is None
        assert reg.get_fallback_for("nonexistent") is None

    def test_fallback_chain(self):
        reg = ProviderRegistry()
        a = DummyAPIProvider("a")
        b = DummyAPIProvider("b")
        c = DummyAPIProvider("c")
        reg.register_with_fallback(a, "b")
        reg.register_with_fallback(b, "c")
        reg.register(c)
        chain = reg.get_fallback_chain("a")
        assert chain == ["a", "b", "c"]

    def test_fallback_chain_cycle_protection(self):
        reg = ProviderRegistry()
        a = DummyAPIProvider("a")
        b = DummyAPIProvider("b")
        reg.register_with_fallback(a, "b")
        reg.register_with_fallback(b, "a")
        chain = reg.get_fallback_chain("a")
        assert chain == ["a", "b"]  # 循环终止

    def test_select_candidates_excludes_placeholder(self):
        reg = ProviderRegistry()
        api = DummyAPIProvider("api")
        placeholder = DummyPlaceholderProvider("ph")
        reg.register(api)
        reg.register(placeholder)

        candidates = reg.select_candidates(exclude_placeholder=True)
        ids = [p.id for p in candidates]
        assert "api" in ids
        assert "ph" not in ids

    def test_select_candidates_includes_placeholder_when_allowed(self):
        reg = ProviderRegistry()
        api = DummyAPIProvider("api")
        placeholder = DummyPlaceholderProvider("ph")
        reg.register(api)
        reg.register(placeholder)

        candidates = reg.select_candidates(exclude_placeholder=False)
        ids = [p.id for p in candidates]
        assert "ph" in ids

    def test_select_candidates_by_capability(self):
        reg = ProviderRegistry()
        vision_provider = DummyAPIProvider("vision", vision_understanding=True)
        text_provider = DummyAPIProvider("text_only")
        reg.register(vision_provider)
        reg.register(text_provider)

        required = ProviderCapabilities(text=True, vision_understanding=True)
        candidates = reg.select_candidates(required_caps=required)
        ids = [p.id for p in candidates]
        assert "vision" in ids
        assert "text_only" not in ids

    def test_select_candidates_by_structured_output(self):
        reg = ProviderRegistry()
        structured = DummyAPIProvider("structured", structured_output=True)
        text = DummyAPIProvider("text_only")
        reg.register(structured)
        reg.register(text)

        required = ProviderCapabilities(text=True, structured_output=True)
        candidates = reg.select_candidates(required_caps=required)
        ids = [p.id for p in candidates]
        assert "structured" in ids
        assert "text_only" not in ids

    def test_select_candidates_strategy_web_first(self):
        reg = ProviderRegistry()
        web = DummyAPIProvider("web_p")
        web.type = ProviderType.WEB  # 模拟 web provider
        api = DummyAPIProvider("api_p")
        reg.register(web)
        reg.register(api)

        candidates = reg.select_candidates(strategy="web_first")
        assert candidates[0].id == "web_p"

    def test_select_candidates_strategy_api_first(self):
        reg = ProviderRegistry()
        web = DummyAPIProvider("web_p")
        web.type = ProviderType.WEB
        api = DummyAPIProvider("api_p")
        reg.register(web)
        reg.register(api)

        candidates = reg.select_candidates(strategy="api_first")
        assert candidates[0].id == "api_p"

    @pytest.mark.asyncio
    async def test_get_health_all(self):
        reg = ProviderRegistry()
        p1 = DummyAPIProvider("p1")
        p2 = DummyAPIProvider("p2")
        reg.register(p1)
        reg.register(p2)

        health = await reg.get_health_all()
        assert "p1" in health
        assert "p2" in health
        assert health["p1"].status == ProviderStatus.AVAILABLE

    def test_select_candidates_cheapest_orders_by_cost(self):
        reg = ProviderRegistry()
        free = DummyAPIProvider("free")
        free.cost_tier = CostTier.FREE
        paid = DummyAPIProvider("paid")
        paid.cost_tier = CostTier.PAID
        low = DummyAPIProvider("low")
        low.cost_tier = CostTier.LOW_COST
        reg.register(paid)
        reg.register(low)
        reg.register(free)

        candidates = reg.select_candidates(strategy="cheapest")
        assert candidates[0].id == "free"


class TestProviderRegistryFromConfig:
    """配置加载测试。"""

    def test_empty_config(self):
        """None config path should return empty registry (don't load defaults)."""
        # Use explicit non-existent path to avoid loading default config
        reg = ProviderRegistry.from_config(config_path="/nonexistent/path/providers.yaml")
        assert len(reg.list_all()) == 0

    def test_invalid_config_no_providers_section(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("other: value\n")
            f.flush()
            reg = ProviderRegistry.from_config(config_path=f.name)
        assert len(reg.list_all()) == 0
        os.unlink(f.name)

    def test_disabled_provider_skipped(self):
        yaml_content = """
providers:
  test_api:
    type: api
    enabled: false
    provider_name: test
    base_url: https://test.com
    model: test-model
    key_env: TEST_KEY
    capabilities:
      text: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            reg = ProviderRegistry.from_config(config_path=f.name)
        assert len(reg.list_all()) == 0
        os.unlink(f.name)

    def test_provider_with_missing_key_still_registered(self):
        """key_env 缺失时 provider 仍注册，但 health 检查会报告 UNAVAILABLE。"""
        yaml_content = """
providers:
  test_api:
    type: api
    enabled: true
    provider_name: test
    base_url: https://test.com
    model: test-model
    key_env: MISSING_KEY_XYZ
    capabilities:
      text: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            reg = ProviderRegistry.from_config(config_path=f.name, env={})
        # provider 仍被注册（无 enabled_env 限制）
        assert len(reg.list_all()) == 1
        p = reg.get("test_api")
        assert p is not None
        import asyncio
        health = asyncio.run(p.health_check())
        assert health.score < 30  # 缺 key 低分
        os.unlink(f.name)

    def test_api_provider_loaded_with_env_key(self):
        yaml_content = """
providers:
  test_api:
    type: api
    enabled: true
    provider_name: test
    base_url: https://test.com
    model: test-model
    key_env: TEST_KEY_FOR_REGISTRY
    cost_tier: free
    capabilities:
      text: true
      streaming: true
      structured_output: true
      planning: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            reg = ProviderRegistry.from_config(
                config_path=f.name,
                env={"TEST_KEY_FOR_REGISTRY": "sk-test-123"},
            )
        assert len(reg.list_all()) == 1
        p = reg.get("test_api")
        assert p is not None
        assert p.cost_tier == CostTier.FREE
        assert p.capabilities.text is True
        assert p.capabilities.streaming is True
        assert p.capabilities.structured_output is True
        os.unlink(f.name)

    def test_placeholder_provider_loaded(self):
        yaml_content = """
providers:
  chatglm_web:
    type: placeholder_web
    enabled: true
    fallback_to: agnes_text
    cost_tier: free
    capabilities:
      text: true
      planning: true
      long_context: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            reg = ProviderRegistry.from_config(config_path=f.name, env={})
        assert len(reg.list_all()) == 1
        p = reg.get("chatglm_web")
        assert p.type == ProviderType.PLACEHOLDER_WEB
        assert reg.get_fallback_for("chatglm_web") is None  # agnes_text not registered
        os.unlink(f.name)
