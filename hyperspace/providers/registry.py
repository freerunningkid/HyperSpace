"""ProviderRegistry —— 统一注册、管理与查询多 Provider。

职责：
  1. 注册/查找/列出 provider
  2. 汇聚所有 provider health
  3. 根据能力、健康、策略筛选候选 provider
  4. 从 YAML 配置加载 provider
  5. 支持 fallback 链

边界：
  - Registry 不决定路由策略（由 Router 使用 registry 提供的信息决定）
  - Registry 不直接调用模型
  - Registry 不持有 DeepSeek Web 专用类引用
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatus,
    ProviderType,
)
from .health import (
    compute_health_score,
    cost_tier_to_score,
    filter_available,
    is_placeholder,
    sort_candidates_by_strategy,
)

logger = logging.getLogger("hyperspace.providers.registry")


class ProviderRegistry:
    """Provider 注册中心。"""

    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}
        self._fallback_map: dict[str, str] = {}  # provider_id → fallback_provider_id

    # ── 注册与查找 ──────────────────────────────────────────────

    def register(self, provider: BaseProvider) -> None:
        """注册一个 provider。"""
        self._providers[provider.id] = provider
        logger.debug(f"已注册 provider: {provider.id} (type={provider.type.value})")

    def register_with_fallback(self, provider: BaseProvider, fallback_id: str | None) -> None:
        """注册 provider 并记录其 fallback 目标。"""
        self.register(provider)
        if fallback_id:
            self._fallback_map[provider.id] = fallback_id

    def get(self, provider_id: str) -> BaseProvider | None:
        """按 id 获取 provider。"""
        return self._providers.get(provider_id)

    def list_all(self) -> list[BaseProvider]:
        """列出所有已注册 provider（含未启用的）。"""
        return list(self._providers.values())

    def list_enabled(self) -> list[BaseProvider]:
        """列出所有可启用的 provider（排除 disabled 状态的）。"""
        return [
            p for p in self._providers.values()
            if p.capabilities.text  # 至少支持文本
        ]

    def list_ids(self) -> list[str]:
        """列出所有已注册的 provider id。"""
        return list(self._providers.keys())

    def get_fallback_for(self, provider_id: str) -> BaseProvider | None:
        """获取指定 provider 的 fallback 目标。"""
        fallback_id = self._fallback_map.get(provider_id)
        if fallback_id:
            return self._providers.get(fallback_id)
        return None

    # ── 健康汇聚 ────────────────────────────────────────────────

    async def get_health_all(self) -> dict[str, ProviderHealth]:
        """获取所有 provider 的健康状态。

        注意：每个 provider.health_check() 本身应尽量轻量（key 存在检查 / 状态检查）。
        不做 smoke test（默认关闭）。
        """
        results: dict[str, ProviderHealth] = {}
        for pid, provider in self._providers.items():
            try:
                health = await provider.health_check()
            except Exception as e:
                health = ProviderHealth(
                    status=ProviderStatus.UNAVAILABLE,
                    score=0.0,
                    last_error=str(e)[:200],
                    message=f"健康检查异常: {e}",
                )
            results[pid] = health
        return results

    # ── 候选筛选 ────────────────────────────────────────────────

    def select_candidates(
        self,
        required_caps: ProviderCapabilities | None = None,
        *,
        exclude_placeholder: bool = True,
        exclude_disabled: bool = True,
        strategy: str = "auto",
        preferred_type: ProviderType | None = None,
    ) -> list[BaseProvider]:
        """根据能力、状态、策略筛选候选 provider 列表。

        Args:
            required_caps: 必需的能力集合（None = 只需 text）
            exclude_placeholder: 是否排除占位 provider
            exclude_disabled: 是否排除 disabled provider
            strategy: 排序策略 (auto/web_first/api_first/cheapest/...)
            preferred_type: 优先类型

        Returns:
            候选 provider 列表（按策略排序）
        """
        required = required_caps or ProviderCapabilities(text=True)

        from .capabilities import matches_capabilities

        candidates: list[tuple[BaseProvider, float, ProviderHealth]] = []

        for provider in self._providers.values():
            # 1. 排除占位
            if exclude_placeholder and provider.type == ProviderType.PLACEHOLDER_WEB:
                continue
            # 2. 排除 disabled (status, not type)
            if exclude_disabled and getattr(provider, '_disabled', False):
                continue
            # 3. 能力匹配
            if not matches_capabilities(provider.capabilities, required):
                continue

            # 构建轻量 health（不调用异步 health_check，用 cost_tier 推断基础分）
            base_score = 90.0 if provider.cost_tier != CostTier.UNKNOWN else 70.0
            health = ProviderHealth(
                status=ProviderStatus.AVAILABLE,
                score=base_score,
                message="",
            )
            cost_score = cost_tier_to_score(provider.cost_tier)
            candidates.append((provider, cost_score, health))

        # 排序
        typed_candidates = [
            (p.id, h, p.type, cs) for p, cs, h in candidates
        ]
        sorted_ids = sort_candidates_by_strategy(typed_candidates, strategy)

        # 按排序结果返回 provider
        id_to_provider = {p.id: p for p, _, _ in candidates}
        result = [id_to_provider[pid] for pid in sorted_ids if pid in id_to_provider]

        # 如果指定了 preferred_type，优先排前面
        if preferred_type:
            preferred = [p for p in result if p.type == preferred_type]
            others = [p for p in result if p.type != preferred_type]
            result = preferred + others

        return result

    def get_fallback_chain(self, provider_id: str) -> list[str]:
        """获取指定 provider 的完整 fallback 链。

        返回 [provider_id, fallback_id, fallback_of_fallback, ...]
        """
        chain = [provider_id]
        seen = {provider_id}
        current = provider_id
        while current in self._fallback_map:
            next_id = self._fallback_map[current]
            if next_id in seen:
                break  # 循环引用保护
            if next_id not in self._providers:
                break  # fallback 目标未注册
            chain.append(next_id)
            seen.add(next_id)
            current = next_id
        return chain

    # ── 配置加载 ────────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config_path: str | Path | None = None,
        *,
        env: dict[str, str] | None = None,
        web_client_factory=None,
        context_manager_factory=None,
        compress_fn=None,
    ) -> ProviderRegistry:
        """从 YAML 配置文件加载 provider 注册表。

        Args:
            config_path: providers.yaml 路径（None = 使用默认 config/providers.yaml）
            env: 环境变量字典（默认 os.environ）
            web_client_factory: DeepSeekWebProvider 的 web_client 工厂
            context_manager_factory: DeepSeekWebProvider 的 ctx_mgr 工厂
            compress_fn: DeepSeekWebProvider 的压缩函数

        Returns:
            配置好的 ProviderRegistry
        """
        registry = cls()

        if env is None:
            env = os.environ

        if config_path is None:
            # 默认路径：config/providers.yaml（相对于项目根）
            from ..config import CONFIG_DIR
            config_path = CONFIG_DIR / "providers.yaml"

        config_path = Path(config_path)
        if not config_path.exists():
            logger.warning(f"Provider 配置文件不存在: {config_path}，使用空注册表")
            return registry

        with config_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        providers_section = raw.get("providers", {})
        if not providers_section:
            logger.warning("配置文件中没有 providers 节")
            return registry

        for pid, cfg in providers_section.items():
            if not isinstance(cfg, dict):
                continue

            enabled = cfg.get("enabled", True)
            if not enabled:
                logger.debug(f"跳过已禁用的 provider: {pid}")
                continue

            # enabled_env 检查
            enabled_env = cfg.get("enabled_env")
            if enabled_env and enabled_env not in env:
                logger.debug(f"跳过缺少环境变量的 provider: {pid} (需 {enabled_env})")
                continue

            ptype_str = cfg.get("type", "api")
            try:
                ptype = ProviderType(ptype_str)
            except ValueError:
                logger.warning(f"未知 provider 类型: {ptype_str}，跳过 {pid}")
                continue

            cost_tier_str = cfg.get("cost_tier", "unknown")
            try:
                cost_tier = CostTier(cost_tier_str)
            except ValueError:
                cost_tier = CostTier.UNKNOWN

            capabilities = cls._parse_capabilities(cfg.get("capabilities", {}))

            class_path = cfg.get("class", "")

            # 根据 class 或 type 创建 provider
            provider = cls._create_provider(
                registry=registry,
                pid=pid,
                ptype=ptype,
                class_path=class_path,
                cfg=cfg,
                capabilities=capabilities,
                cost_tier=cost_tier,
                env=env,
                web_client_factory=web_client_factory,
                context_manager_factory=context_manager_factory,
                compress_fn=compress_fn,
            )

            if provider is None:
                logger.warning(f"无法创建 provider: {pid}")
                continue

            fallback_to = cfg.get("fallback_to")
            if fallback_to:
                registry._fallback_map[pid] = fallback_to

            logger.info(f"已加载 provider: {pid} (type={ptype.value}, cost={cost_tier.value})")

        return registry

    @staticmethod
    def _parse_capabilities(raw: dict) -> ProviderCapabilities:
        """从字典解析能力声明。"""
        return ProviderCapabilities(
            text=raw.get("text", True),
            vision_understanding=raw.get("vision_understanding", False),
            image_generation=raw.get("image_generation", False),
            video_understanding=raw.get("video_understanding", False),
            video_generation=raw.get("video_generation", False),
            file_upload=raw.get("file_upload", False),
            web_search=raw.get("web_search", False),
            streaming=raw.get("streaming", False),
            structured_output=raw.get("structured_output", False),
            planning=raw.get("planning", True),
            long_context=raw.get("long_context", False),
            tool_calling=raw.get("tool_calling", False),
        )

    @staticmethod
    def _create_provider(
        registry: ProviderRegistry,
        pid: str,
        ptype: ProviderType,
        class_path: str,
        cfg: dict,
        capabilities: ProviderCapabilities,
        cost_tier: CostTier,
        env: dict[str, str],
        web_client_factory=None,
        context_manager_factory=None,
        compress_fn=None,
    ) -> BaseProvider | None:
        """根据配置创建 provider 实例。

        Provider 创建策略：
          1. Web 类型 → DeepSeekWebProvider（如果 class_path 指向它）
          2. Placeholder Web → PlaceholderProvider
          3. API 类型 → OpenAICompatibleProvider 适配器
        """
        # ── Placeholder Web ──
        if ptype == ProviderType.PLACEHOLDER_WEB:
            from .chatglm_web import ChatGLMWebPlaceholderProvider
            from .qwen_chat_web import QwenChatWebPlaceholderProvider

            if "chatglm" in pid:
                provider = ChatGLMWebPlaceholderProvider()
                registry.register(provider)
                return provider
            elif "qwen" in pid:
                provider = QwenChatWebPlaceholderProvider()
                registry.register(provider)
                return provider
            else:
                # 通用占位
                provider = ChatGLMWebPlaceholderProvider()
                provider.id = pid
                registry.register(provider)
                return provider

        # ── Web 类型 (DeepSeek Web) ──
        if ptype == ProviderType.WEB:
            from .deepseek_web import DeepSeekWebProvider

            provider = DeepSeekWebProvider(
                web_client_factory=web_client_factory,
                context_manager_factory=context_manager_factory,
                compress_fn=compress_fn,
            )
            registry.register(provider)
            return provider

        # ── API 类型 ──
        if ptype == ProviderType.API:
            from .openai_compatible import OpenAICompatibleProvider

            base_url = cfg.get("base_url", "")
            model = cfg.get("model", "")
            key_env_name = cfg.get("key_env", "")

            provider = OpenAICompatibleProvider(
                provider_id=pid,
                provider_name=cfg.get("provider_name", pid),
                base_url=base_url,
                model=model,
                key_env=key_env_name,
                capabilities=capabilities,
                cost_tier=cost_tier,
                timeout=cfg.get("timeout", 60.0),
            )
            registry.register(provider)
            return provider

        return None
