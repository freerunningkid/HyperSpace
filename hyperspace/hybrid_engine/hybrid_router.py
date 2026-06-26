"""HybridRouter —— 核心混合路由决策引擎 (原生实现, 无外部依赖).

三层架构 (v2.0 多 Provider):
  DeepSeek Web (原生 Python 客户端) — 规划/搜索/识图/长文本 (零 Token 成本)
  ↔ 多 API Provider (DeepSeek/Qwen/Zhipu/SiliconFlow/Agnes via Registry)
  → 占位 Provider (ChatGLM/Qwen Chat Web — fallback 到 API)

路由优先级 (自高而低):
  1. has_image → deepseek_web (原生识图)
  2. needs_search → deepseek_web (联网搜索)
  3. needs_planning → deepseek_web (长文本规划)
  4. is_long → deepseek_web (1M 上下文)
  5. needs_coding → deepseek_api (API 输出稳定)
  6. needs_translation → deepseek_api
  7. needs_structured_output → deepseek_api (JSON 模式)
  8. 默认 → deepseek_web (经济优先)
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml

from .task_analyzer import TaskProfile, analyze_task
from .health_checker import HealthChecker, HealthResult
from .result_processor import ProcessedResult, ResultProcessor
from .fallback import FallbackManager

# 复用现有 Provider 类型
from ..providers.base import (
    ProviderError,
    ProviderNotImplemented,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)
from ..providers.openai_compat import OpenAICompatProvider

# Provider 能力匹配
from ..providers.capabilities import capability_for_task, matches_capabilities

# 我们的 DeepSeek Web 客户端 + 上下文管理
from .deepseek_web_client import DeepSeekWebClient, DeepSeekAuth, DeepSeekWebResponse
from .context_window_manager import ContextWindowManager
from . import web_auth as web_auth_mod

logger = logging.getLogger("hyperspace.hybrid_router")


@dataclass
class RoutingDecision:
    """路由决策."""
    executor: str = "deepseek_web"
    provider_id: str = "deepseek_web"   # v2.0: 与 executor 对应，但允许独立设置
    model: str = "deepseek-chat"
    fallback_order: list[str] = field(default_factory=lambda: [
        "deepseek_web", "deepseek_api", "zhipu",
    ])
    reason: str = ""
    web_mode: str = "auto"
    search_enabled: bool = True
    thinking_enabled: bool = True
    mode_source: str = "auto"
    routing_strategy: str = "auto"       # v2.0: 路由策略
    expected_output: str = "answer"      # v2.0: 输出类型
    force_provider: bool = False         # v2.0: 是否强制指定 provider


# ── 模式枚举 ──

FORCE_MODES = {"force_web", "force_api", "force_zhipu"}
LEGACY_MODES = {"free_text", "free_vision", "cheap_capable", "premium"}
ALL_MODES = LEGACY_MODES | FORCE_MODES | {"auto"}
WEB_MODES = {"auto", "quick", "expert", "vision"}

# ── 默认配置 ──

DEFAULT_CONFIG = {
    "routing": {
        "default_executor": "deepseek_web",
        "fallback_order": ["deepseek_web", "deepseek_api", "zhipu"],
        "rules": [
            {"condition": "has_image", "executor": "deepseek_web"},
            {"condition": "needs_search", "executor": "deepseek_web"},
            {"condition": "needs_planning", "executor": "deepseek_web"},
            {"condition": "is_long", "executor": "deepseek_web"},
            {"condition": "needs_coding", "executor": "deepseek_api"},
            {"condition": "needs_translation", "executor": "deepseek_api"},
            {"condition": "needs_structured_output", "executor": "deepseek_api"},
        ],
    },
    "executors": {
        "deepseek_web": {
            "model": "deepseek-chat",
            "timeout": 120,
            "search_enabled": True,
            "thinking_enabled": True,
        },
        "deepseek_api": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "timeout": 60,
        },
        "zhipu": {
            "provider": "zhipu",
            "model": "glm-4.7-flash",
            "timeout": 30,
        },
    },
}


def _resolve_web_mode(profile: TaskProfile, web_mode: str) -> str:
    """解析 DeepSeek Web 产品模式."""
    if web_mode in WEB_MODES and web_mode != "auto":
        return web_mode
    return profile.suggested_web_mode or "auto"


def _thinking_enabled_for_web_mode(web_mode: str, profile: TaskProfile) -> bool:
    """根据 Web 模式映射 thinking_enabled."""
    if web_mode == "quick":
        return False
    if web_mode in {"expert", "vision"}:
        return True
    # auto: let context_window_manager decide (avoid empty response)
    return None


def _resolve_search_enabled(
    profile: TaskProfile,
    web_mode: str,
    search_enabled: bool | None,
) -> bool:
    """解析搜索开关."""
    if search_enabled is not None:
        return search_enabled
    if web_mode == "vision" and (profile.has_image or profile.has_file):
        return False
    # auto mode: use TaskAnalyzer smart detection + explicit needs_search
    return profile.needs_search or getattr(profile, "search_enabled", False)


def _build_system_context(profile: TaskProfile) -> str:
    """根据任务特征生成最小化系统指令 (控制 Web 模型行为)."""
    if profile.has_image:
        return _SYS["vision"]
    if profile.needs_translation:
        return _SYS["translation"]
    if profile.needs_coding:
        return _SYS["coding"]
    if profile.needs_planning:
        return _SYS["planning"]
    if profile.needs_search:
        return _SYS["search"]
    if profile.needs_structured_output:
        return _SYS["structured"]
    return _SYS["default"]


_SYS = {
    "coding": "你是 DeepSeek，编程助手。输出正确可运行的代码。不确定时直说不知道，不编造不存在的 API 或库。",
    "planning": "你是 DeepSeek，技术规划师。给出具体可执行的步骤，不空泛建议。不确定就直说。",
    "translation": "你是 DeepSeek，翻译引擎。只输出翻译结果，不加任何解释或备注。",
    "search": "你是 DeepSeek，联网研究助手。基于已知事实回答，不确定就标注「不确定」。",
    "vision": "你是 DeepSeek，图像分析助手。详细精确描述你看到的内容，不要编造图像中没有的东西。",
    "structured": "你是 DeepSeek，格式化输出助手。严格按要求的 JSON/表格格式输出，不附加冗余文字。",
    "default": "你是 DeepSeek，精准推理助手。简体中文回复。不确定就说不知道，不编造答案。",
}


class HybridRouter:
    """混合推理路由器 —— 任务分析 → 健康检查 → 路由 → 执行 → 后处理.

    v2.0: 可选注入 ProviderRegistry，支持多 Provider 架构。
          无 Registry 时回退为旧三 executor 模式。
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        deepseek_api_config: dict | None = None,
        zhipu_config: dict | None = None,
        provider_registry: Any | None = None,
        providers_config_path: str | Path | None = None,
    ):
        self._cfg = self._load_config(config_path)
        self._deepseek_api_cfg = deepseek_api_config or {}
        self._zhipu_cfg = zhipu_config or {}
        self._github_cfg = {"base_url": "https://models.github.ai/inference", "model": "openai/gpt-4o", "timeout": 60}
        self._agnes_cfg = {"base_url": "https://apihub.agnes-ai.com/v1", "model": "agnes-2.0-flash", "timeout": 30}

        # v2.0: ProviderRegistry
        self._registry = provider_registry
        self._providers_config_path = providers_config_path

        # 初始化 DeepSeek Web 客户端
        self._web_client: DeepSeekWebClient | None = None
        self._ctx_mgr: ContextWindowManager | None = None
        self._init_web_client()

        # 健康检查器 (用凭据提供者检查 Web 可用性)
        self._health_checker = HealthChecker(
            deepseek_web_auth_provider=self._get_saved_auth,
        )
        self._fallback = FallbackManager(
            fallback_order=self._cfg["routing"]["fallback_order"]
        )
        # 凭据刷新保护
        self._auth_lock = asyncio.Lock()
        self._auth_refresh_attempted = False

    def _init_web_client(self):
        """从已保存凭据初始化 DeepSeek Web 客户端和上下文管理器.

        当 Cookie 有效但 Bearer Token 缺失时，自动尝试提取.
        """
        auth_data = web_auth_mod.load_saved_auth()
        if auth_data:
            auth = DeepSeekAuth.from_dict(auth_data)
            if auth.is_valid():
                # Cookie 有效但无 Bearer → 自动提取
                if not auth.bearer:
                    logger.info("Cookie 有效但 Bearer Token 缺失, 尝试自动提取...")
                    try:
                        result = web_auth_mod.auto_extract_sync()
                        if result and result.get("bearer"):
                            auth = DeepSeekAuth.from_dict(result)
                            logger.info("Bearer Token 自动提取成功")
                    except Exception as e:
                        logger.warning(f"自动提取失败, 将使用 Cookie-only 模式: {e}")

                self._web_client = DeepSeekWebClient(auth)
                self._ctx_mgr = ContextWindowManager(
                    web_client=self._web_client,
                    compress_fn=self._compress_via_api,
                )
                logger.info("DeepSeek Web 客户端 + 上下文管理器已初始化 (凭据有效)")

    def _get_saved_auth(self) -> dict | None:
        """返回已保存的凭据 (供 HealthChecker 使用)."""
        return web_auth_mod.load_saved_auth()

    async def _refresh_web_auth(self) -> bool:
        """尝试刷新 DeepSeek Web 凭据, 返回成功/失败.

        含 asyncio.Lock 防止并发重复刷新;
        含 _auth_refresh_attempted 标志防止同次 execute 内无限重试.
        """
        if self._auth_refresh_attempted:
            return False
        self._auth_refresh_attempted = True

        async with self._auth_lock:
            try:
                result = await web_auth_mod.auto_extract()
                if result and result.get("bearer"):
                    self._web_client.auth = DeepSeekAuth.from_dict(result)
                    self._ctx_mgr = ContextWindowManager(
                        web_client=self._web_client,
                        compress_fn=self._compress_via_api,
                    )
                    logger.info("凭据自动刷新成功")
                    return True
            except Exception as e:
                logger.warning(f"凭据自动刷新失败: {e}")
            return False

    # ── 公开入口 ──

    async def execute(
        self,
        prompt: str,
        images: list[str] | None = None,
        context: str | None = None,
        mode: str = "auto",
        session_key: str = "",
        web_mode: str = "auto",
        search_enabled: bool | None = None,
        provider: str = "auto",
        routing_strategy: str = "auto",
        expected_output: str = "answer",
    ) -> ProcessedResult:
        """完整流程: 分析 → 路由 → 执行 → 后处理.

        session_key: 对话会话标识, 用于多轮上下文管理.
                     空字符串 = 每次新建 (无状态).
                     同一 key = 自动追踪上下文, 满时压缩.

        v2.0 新参数:
          provider: 指定 provider id (auto = 自动选择)
          routing_strategy: 路由策略 (auto/web_first/zero_cost_first/api_first/...)
          expected_output: 输出类型 (answer/plan/json/structured/summary/critique)
        """
        self._auth_refresh_attempted = False  # 每次请求可重试一次刷新
        profile = analyze_task(prompt, images=images, context=context)

        # Auto-generate system context to control web model behavior
        _context = _build_system_context(profile)
        if context:
            _context = f"{context}\n\n{_context}"

        decision = self._route(
            profile, mode,
            web_mode=web_mode,
            search_enabled=search_enabled,
            provider=provider,
            routing_strategy=routing_strategy,
            expected_output=expected_output,
        )

        # Legacy mode 直接降级到旧路由
        if decision.reason.startswith("legacy_mode:"):
            return ProcessedResult(
                answer="[hyperspace] LEGACY_MODE_FALLBACK",
                used_executor="legacy",
            )

        health = await self._health_checker.check_all()

        result = await self._call_with_fallback(
            decision=decision,
            health=health,
            prompt=prompt,
            images=images,
            context=_context,
            session_key=session_key,
        )

        return result

    # ── 路由决策 ──

    def _route(
        self,
        profile: TaskProfile,
        mode: str,
        web_mode: str = "auto",
        search_enabled: bool | None = None,
        provider: str = "auto",
        routing_strategy: str = "auto",
        expected_output: str = "answer",
    ) -> RoutingDecision:
        """基于 TaskProfile + mode + provider 做出路由决策."""
        resolved_web_mode = _resolve_web_mode(profile, web_mode)
        thinking_enabled = _thinking_enabled_for_web_mode(resolved_web_mode, profile)
        resolved_search_enabled = _resolve_search_enabled(
            profile, resolved_web_mode, search_enabled
        )

        # v2.0: 显式 provider 选择
        if provider != "auto" and provider:
            return self._route_explicit_provider(
                profile, provider, resolved_web_mode,
                resolved_search_enabled, thinking_enabled,
                routing_strategy, expected_output,
            )

        if mode == "force_web":
            return RoutingDecision(
                executor="deepseek_web", provider_id="deepseek_web",
                model=self._cfg["executors"]["deepseek_web"]["model"],
                reason="force_web mode",
                web_mode=resolved_web_mode,
                search_enabled=resolved_search_enabled,
                thinking_enabled=thinking_enabled,
                mode_source="explicit" if web_mode != "auto" else "inferred",
                routing_strategy=routing_strategy,
                expected_output=expected_output,
            )
        if mode == "force_api":
            return RoutingDecision(
                executor="deepseek_api", provider_id="deepseek_api",
                model="deepseek-chat",
                reason="force_api mode",
                web_mode=resolved_web_mode,
                search_enabled=resolved_search_enabled,
                thinking_enabled=thinking_enabled,
                mode_source="explicit" if web_mode != "auto" else "inferred",
                routing_strategy=routing_strategy,
                expected_output=expected_output,
            )
        if mode == "force_zhipu":
            return RoutingDecision(
                executor="zhipu", provider_id="zhipu_api",
                model="glm-4.7-flash",
                reason="force_zhipu mode",
                web_mode=resolved_web_mode,
                search_enabled=resolved_search_enabled,
                thinking_enabled=thinking_enabled,
                mode_source="explicit" if web_mode != "auto" else "inferred",
                routing_strategy=routing_strategy,
                expected_output=expected_output,
            )
        if mode == "force_github":
            return RoutingDecision(
                executor="github", provider_id="github",
                model="openai/gpt-4o", reason="force_github mode",
                web_mode=resolved_web_mode, search_enabled=False,
                thinking_enabled=False, mode_source="explicit",
                routing_strategy=routing_strategy, expected_output=expected_output,
            )
        if mode == "force_agnes":
            return RoutingDecision(
                executor="agnes", provider_id="agnes",
                model="agnes-2.0-flash", reason="force_agnes mode",
                web_mode=resolved_web_mode, search_enabled=False,
                thinking_enabled=False, mode_source="explicit",
                routing_strategy=routing_strategy, expected_output=expected_output,
            )
        if mode == "auto":
            return self._route_auto(
                profile, resolved_web_mode, resolved_search_enabled, thinking_enabled,
                routing_strategy=routing_strategy, expected_output=expected_output,
            )
        if mode in LEGACY_MODES:
            return RoutingDecision(
                executor="", reason=f"legacy_mode:{mode}", fallback_order=[]
            )

        return RoutingDecision(
            executor="deepseek_web", provider_id="deepseek_web",
            reason=f"default (mode={mode})",
            web_mode=resolved_web_mode,
            search_enabled=resolved_search_enabled,
            thinking_enabled=thinking_enabled,
            routing_strategy=routing_strategy,
            expected_output=expected_output,
        )

    def _route_auto(
        self,
        profile: TaskProfile,
        web_mode: str,
        search_enabled: bool,
        thinking_enabled: bool,
        routing_strategy: str = "auto",
        expected_output: str = "answer",
    ) -> RoutingDecision:
        """优先级规则匹配 (v2.0: 当 registry 可用时使用能力匹配)."""
        # v2.0: 尝试 registry 候选
        if self._registry:
            return self._route_with_registry(
                profile, web_mode, search_enabled, thinking_enabled,
                routing_strategy, expected_output,
            )

        # 旧逻辑：硬编码规则匹配
        rules = self._cfg["routing"]["rules"]
        default_executor = self._cfg["routing"]["default_executor"]

        for rule in rules:
            condition = rule["condition"]
            executor = rule["executor"]
            if getattr(profile, condition, False):
                model = self._resolve_model(executor)
                return RoutingDecision(
                    executor=executor, provider_id=executor,
                    model=model,
                    reason=f"rule:{condition}->{executor}",
                    web_mode=web_mode,
                    search_enabled=search_enabled,
                    thinking_enabled=thinking_enabled,
                    mode_source="explicit" if web_mode != profile.suggested_web_mode else "inferred",
                    routing_strategy=routing_strategy,
                    expected_output=expected_output,
                )

        return RoutingDecision(
            executor=default_executor, provider_id=default_executor,
            model=self._resolve_model(default_executor),
            reason=f"default->{default_executor}",
            web_mode=web_mode,
            search_enabled=search_enabled,
            thinking_enabled=thinking_enabled,
            mode_source="explicit" if web_mode != profile.suggested_web_mode else "inferred",
            routing_strategy=routing_strategy,
            expected_output=expected_output,
        )

    def _resolve_model(self, executor: str) -> str:
        cfg = self._cfg["executors"].get(executor, {})
        return cfg.get("model", "unknown")

    # ── v2.0 Registry 感知路由 ──────────────────────────────────

    def _route_with_registry(
        self,
        profile: TaskProfile,
        web_mode: str,
        search_enabled: bool,
        thinking_enabled: bool,
        routing_strategy: str = "auto",
        expected_output: str = "answer",
    ) -> RoutingDecision:
        """使用 ProviderRegistry 进行能力匹配路由。"""
        from ..providers.capabilities import capability_for_task

        required_caps = capability_for_task(
            profile,
            expected_output=expected_output,
            has_files=profile.has_file,
        )

        candidates = self._registry.select_candidates(
            required_caps=required_caps,
            exclude_placeholder=True,
            exclude_disabled=True,
            strategy=routing_strategy,
            preferred_type=ProviderType.WEB if routing_strategy in ("auto", "web_first") else None,
        )

        if not candidates:
            # 回退到硬编码默认
            logger.warning("Registry 无可用候选，回退到默认路由")
            return RoutingDecision(
                executor="deepseek_web", provider_id="deepseek_web",
                model="deepseek-chat",
                reason="registry_empty_fallback",
                web_mode=web_mode,
                search_enabled=search_enabled,
                thinking_enabled=thinking_enabled,
                routing_strategy=routing_strategy,
                expected_output=expected_output,
            )

        best = candidates[0]
        return RoutingDecision(
            executor=best.id, provider_id=best.id,
            model=getattr(best, '_model', 'unknown'),
            reason=f"registry:capability_match->{best.id}",
            fallback_order=[p.id for p in candidates[1:]],
            web_mode=web_mode,
            search_enabled=search_enabled,
            thinking_enabled=thinking_enabled,
            routing_strategy=routing_strategy,
            expected_output=expected_output,
        )

    def _route_explicit_provider(
        self,
        profile: TaskProfile,
        provider: str,
        web_mode: str,
        search_enabled: bool,
        thinking_enabled: bool,
        routing_strategy: str = "auto",
        expected_output: str = "answer",
    ) -> RoutingDecision:
        """显式 provider 选择。

        如果指定的 provider 是占位 provider，标记为 force_provider，
        让 fallback 逻辑处理 placeholder → API 降级。
        """
        force = routing_strategy == "force_provider"

        # 检查 registry
        if self._registry:
            p = self._registry.get(provider)
            if p:
                if p.type == ProviderType.PLACEHOLDER_WEB and not force:
                    # 占位 provider：允许 fallback
                    fallback_provider = self._registry.get_fallback_for(provider)
                    fallback_order = [fallback_provider.id] if fallback_provider else []
                    return RoutingDecision(
                        executor=provider, provider_id=provider,
                        model="unknown",
                        reason=f"explicit_placeholder:{provider}",
                        fallback_order=fallback_order,
                        web_mode=web_mode,
                        search_enabled=search_enabled,
                        thinking_enabled=thinking_enabled,
                        routing_strategy="fallback",
                        expected_output=expected_output,
                        force_provider=force,
                    )
                # 正常 provider
                return RoutingDecision(
                    executor=provider, provider_id=provider,
                    model=getattr(p, '_model', 'unknown'),
                    reason=f"explicit:{provider}",
                    web_mode=web_mode,
                    search_enabled=search_enabled,
                    thinking_enabled=thinking_enabled,
                    routing_strategy=routing_strategy,
                    expected_output=expected_output,
                    force_provider=force,
                )
            else:
                # 未知 provider id — 尝试映射到已知 executor
                return RoutingDecision(
                    executor=provider, provider_id=provider,
                    model="unknown",
                    reason=f"explicit_unknown:{provider}",
                    web_mode=web_mode,
                    search_enabled=search_enabled,
                    thinking_enabled=thinking_enabled,
                    routing_strategy=routing_strategy,
                    expected_output=expected_output,
                    force_provider=force,
                )

        # 无 registry，退回旧逻辑
        return RoutingDecision(
            executor=provider, provider_id=provider,
            model="unknown",
            reason=f"explicit_no_registry:{provider}",
            routing_strategy=routing_strategy,
            expected_output=expected_output,
            force_provider=force,
        )

    # ── 执行与降级 ──

    async def _call_with_fallback(
        self,
        decision: RoutingDecision,
        health: HealthResult,
        prompt: str,
        images: list[str] | None,
        context: str | None,
        session_key: str = "",
    ) -> ProcessedResult:
        """带降级的执行 (v2.0: 含 placeholder fallback 元数据)."""

        # v2.0: placeholder 扩展 fallback 链
        effective_fallback = list(decision.fallback_order)
        if self._registry:
            placeholder_fallback = self._registry.get_fallback_chain(decision.provider_id)
            if len(placeholder_fallback) > 1:
                for fb_id in placeholder_fallback[1:]:
                    if fb_id not in effective_fallback:
                        effective_fallback.append(fb_id)

        # 构建执行器映射
        executors = self._build_executor_map()

        # 过滤可用执行器
        available = self._filter_available(
            effective_fallback or decision.fallback_order, health
        )

        # 执行
        result = await self._fallback.execute(
            executors=executors,
            primary_executor=decision.executor,
            prompt=prompt,
            images=images,
            context=context,
            fallback_order=available,
            session_key=session_key,
            web_mode=decision.web_mode,
            search_enabled=decision.search_enabled,
            thinking_enabled=decision.thinking_enabled,
            routing_strategy=decision.routing_strategy,
            expected_output=decision.expected_output,
        )

        if result.success and result.value:
            processed = ResultProcessor.process(
                raw_text=result.value,
                executor_name=result.used_executor or decision.executor,
                model_name=result.used_model or decision.model,
            )
            # v2.0: 附加 provider 元数据
            if result.used_executor != decision.executor:
                processed.used_executor = result.used_executor
            return processed

        errors = "; ".join(
            f"{e['executor']}:{e['error_type']}:{e['msg'][:80]}"
            for e in result.errors
        )
        return ProcessedResult(
            answer=f"[hyperspace] x 所有执行器均失败: {errors}",
            used_executor="error",
        )

    def _build_executor_map(self) -> dict:
        """构建可调用的执行器函数映射 (v2.0: 含 registry providers)."""
        executors = {
            "deepseek_web": self._call_web,
            "deepseek_api": self._call_api,
            "zhipu": self._call_zhipu,
            "github": self._call_github,
            "agnes": self._call_agnes,
        }

        # v2.0: 从 registry 添加额外 provider
        if self._registry:
            for provider in self._registry.list_all():
                if provider.type == ProviderType.PLACEHOLDER_WEB:
                    # 占位 provider 映射到 fallback 调用
                    fallback_id = self._registry._fallback_map.get(provider.id)
                    if fallback_id and fallback_id not in executors:
                        executors[provider.id] = self._make_provider_caller(provider.id)
                    elif fallback_id:
                        executors[provider.id] = executors[fallback_id]
                elif provider.id not in executors:
                    executors[provider.id] = self._make_provider_caller(provider.id)

        return executors

    def _make_provider_caller(self, provider_id: str):
        """为指定 provider 创建可调用包装器。

        返回 async callable(prompt, images, context, executor_name, **kwargs)
        签名与 FallbackManager 兼容。
        """
        async def _call(prompt, images=None, context=None, executor_name="", **kwargs):
            if not self._registry:
                raise RuntimeError(f"Registry 不可用，无法调用 {provider_id}")

            provider = self._registry.get(provider_id)
            if not provider:
                raise RuntimeError(f"Provider 未注册: {provider_id}")

            from ..providers.base import ProviderRequest
            request = ProviderRequest(
                prompt=prompt,
                provider_id=provider_id,
                images=images,
                context=context,
                session_id=kwargs.get("session_key", ""),
                web_mode=kwargs.get("web_mode", "auto"),
                search_enabled=kwargs.get("search_enabled", True),
                expected_output=kwargs.get("expected_output", "answer"),
                routing_strategy=kwargs.get("routing_strategy", "auto"),
            )

            try:
                response = await provider.chat(request)
                if response.error:
                    raise RuntimeError(f"[{provider_id}] {response.error}")
                return response.answer, response.model or "unknown"
            except ProviderNotImplemented:
                raise  # 让 fallback 逻辑处理

        return _call

    async def _compress_via_api(self, text: str) -> str:
        """用可用 API 做上下文压缩摘要 (v2.0: 优先使用 registry)."""
        # v2.0: 尝试通过 registry 获取 API provider
        if self._registry:
            api_candidates = self._registry.select_candidates(
                required_caps=None,
                exclude_placeholder=True,
                exclude_disabled=True,
                strategy="fastest",
                preferred_type=ProviderType.API,
            )
            for candidate in api_candidates:
                try:
                    from ..providers.base import ProviderRequest
                    req = ProviderRequest(
                        prompt=text,
                        provider_id=candidate.id,
                    )
                    resp = await candidate.chat(req)
                    if resp.answer:
                        return resp.answer
                except Exception:
                    continue

        # 旧逻辑: 使用 hardcoded API key
        cfg = self._deepseek_api_cfg or self._zhipu_cfg
        if not cfg or not cfg.get("api_key"):
            lines = text.split("\n")
            return "\n".join(lines[-5:]) if len(lines) > 5 else text

        try:
            from ..config import ProviderCandidate
            provider_name = cfg.get("provider", "deepseek")
            key_env = "DEEPSEEK_API_KEY" if provider_name == "deepseek" else "ZHIPU_API_KEY"

            cand = ProviderCandidate(
                provider=provider_name,
                base_url=cfg.get("base_url", "https://api.deepseek.com"),
                model=cfg.get("model", "deepseek-chat"),
                key_env=key_env,
            )
            from ..providers.openai_compat import OpenAICompatProvider
            provider = OpenAICompatProvider(cand, timeout=30)
            resp = await provider.chat(text)
            return resp.text
        except Exception as e:
            logger.warning(f"压缩 API 调用失败: {e}")
            lines = text.split("\n")
            return "\n".join(lines[-5:]) if len(lines) > 5 else text

    async def _call_web(
        self,
        prompt: str,
        images: list[str] | None = None,
        context: str | None = None,
        executor_name: str = "deepseek_web",
        session_key: str = "",
        **kwargs,
    ) -> tuple[str, str]:
        """调用 DeepSeek Web 客户端 (通过 ContextWindowManager 管理上下文)."""
        if not self._web_client or not self._ctx_mgr:
            raise RuntimeError("DeepSeek Web 客户端未初始化 (请先运行 auth extract)")

        # 尝试重新初始化 (如果凭据文件更新了)
        if not self._web_client.auth.is_valid():
            auth_data = web_auth_mod.load_saved_auth()
            if auth_data:
                auth = DeepSeekAuth.from_dict(auth_data)
                if auth.is_valid():
                    self._web_client.auth = auth
                    # 重新创建 ContextWindowManager
                    self._ctx_mgr = ContextWindowManager(
                        web_client=self._web_client,
                        compress_fn=self._compress_via_api,
                    )
            # 文件重载无效, 尝试自动提取凭据
            if not self._web_client.auth.is_valid():
                await self._refresh_web_auth()

        # 合并 context 到 prompt
        if context:
            full_prompt = f"{context}\n\n{prompt}"
        else:
            full_prompt = prompt

        # Bearer pre-check (first call each session)
        if self._web_client.auth.bearer and not getattr(self, "_bearer_checked", False):
            self._bearer_checked = True
            try:
                if not await self._web_client.verify_auth():
                    logger.warning("Bearer expired pre-check, auto-clear")
                    web_auth_mod.save_auth({"cookie": "", "bearer": ""})
                    self._web_client.auth.bearer = ""
                    # 尝试立即重新提取 Bearer 以便本次请求继续
                    await self._refresh_web_auth()
            except Exception:
                pass

        try:
            # 通过上下文管理器发送 (自动处理压缩/新 session/故障恢复)
            resp = await self._ctx_mgr.chat(
                session_key=session_key,
                prompt=full_prompt,
                images=images,
                web_mode=kwargs.get("web_mode", "auto"),
                search_enabled=kwargs.get("search_enabled", True),
                thinking_enabled=kwargs.get("thinking_enabled", True),
            )
        except RuntimeError as e:
            err_msg = str(e)
            # Bearer 过期 → 清除凭据，下次 _init_web_client 自动刷新
            if "Missing Token" in err_msg or "40002" in err_msg:
                logger.warning("Bearer Token 已过期，自动清除并刷新")
                web_auth_mod.save_auth({"cookie": "", "bearer": ""})
                # 立即刷新, 下次 _call_web 入口 (或 fallback 后的下次请求) 会使用新凭据
                await self._refresh_web_auth()
            if "连续失败" in str(e):
                # 连续失败, 触发降级 (让 _call_with_fallback 处理)
                raise
            raise

        # 合并思维链和最终回答
        if resp.thinking:
            full_text = f"{resp.thinking}\n\n{resp.text}"
        else:
            full_text = resp.text

        web_mode = kwargs.get("web_mode", "auto")
        thinking = kwargs.get("thinking_enabled", True)
        if web_mode == "expert":
            model_label = "deepseek-v4-pro · deep thinking" if thinking else "deepseek-v4-pro"
        elif web_mode == "vision":
            model_label = "deepseek-v4-pro"
        elif web_mode == "quick":
            model_label = "deepseek-v4-flash"
        else:
            model_label = "deepseek-v4-flash"
        return full_text, model_label

    async def _call_api(
        self,
        prompt: str,
        images: list[str] | None = None,
        context: str | None = None,
        executor_name: str = "deepseek_api",
        **kwargs,
    ) -> tuple[str, str]:
        """调用 DeepSeek API (通过 OpenAICompatProvider)."""
        cfg = self._deepseek_api_cfg
        if not cfg or not cfg.get("api_key"):
            raise RuntimeError("DeepSeek API Key 未配置")

        from ..config import ProviderCandidate
        cand = ProviderCandidate(
            provider="deepseek",
            base_url=cfg.get("base_url", "https://api.deepseek.com"),
            model=cfg.get("model", "deepseek-chat"),
            key_env="DEEPSEEK_API_KEY",
        )
        # 临时注入 key
        old = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = cfg["api_key"]

        try:
            provider = OpenAICompatProvider(cand, timeout=cfg.get("timeout", 60))
            resp = await provider.chat(prompt, images=images, context=context)
            return resp.text, resp.model
        finally:
            if old:
                os.environ["DEEPSEEK_API_KEY"] = old
            else:
                os.environ.pop("DEEPSEEK_API_KEY", None)

    async def _call_zhipu(
        self,
        prompt: str,
        images: list[str] | None = None,
        context: str | None = None,
        executor_name: str = "zhipu",
        **kwargs,
    ) -> tuple[str, str]:
        """调用智谱 GLM API (通过 OpenAICompatProvider)."""
        cfg = self._zhipu_cfg
        if not cfg or not cfg.get("api_key"):
            raise RuntimeError("智谱 API Key 未配置")

        from ..config import ProviderCandidate
        cand = ProviderCandidate(
            provider="zhipu",
            base_url=cfg.get("base_url", "https://open.bigmodel.cn/api/paas/v4"),
            model=cfg.get("model", "glm-4.7-flash"),
            key_env="ZHIPU_API_KEY",
        )
        old = os.environ.get("ZHIPU_API_KEY")
        os.environ["ZHIPU_API_KEY"] = cfg["api_key"]

        try:
            provider = OpenAICompatProvider(cand, timeout=cfg.get("timeout", 30))
            resp = await provider.chat(prompt, images=images, context=context)
            return resp.text, resp.model
        finally:
            if old:
                os.environ["ZHIPU_API_KEY"] = old
            else:
                os.environ.pop("ZHIPU_API_KEY", None)

    async def _call_github(
        self, prompt, images=None, context=None, executor_name="github", **kwargs
    ) -> tuple[str, str]:
        """GitHub Models GPT-4o (免费 OpenAI 兼容)."""
        from openai import AsyncOpenAI
        key = os.environ.get("GITHUB_API_KEY", "")
        if not key:
            raise RuntimeError("GITHUB_API_KEY 未配置")
        client = AsyncOpenAI(base_url=self._github_cfg["base_url"], api_key=key)
        resp = await client.chat.completions.create(
            model=self._github_cfg["model"], messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return resp.choices[0].message.content or "", self._github_cfg["model"]

    async def _call_agnes(
        self, prompt, images=None, context=None, executor_name="agnes", **kwargs
    ) -> tuple[str, str]:
        """Agnes Flash (免费 OpenAI 兼容)."""
        from openai import AsyncOpenAI
        key = os.environ.get("AGNES_API_KEY", "")
        if not key:
            raise RuntimeError("AGNES_API_KEY 未配置")
        client = AsyncOpenAI(base_url=self._agnes_cfg["base_url"], api_key=key)
        resp = await client.chat.completions.create(
            model=self._agnes_cfg["model"], messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return resp.choices[0].message.content or "", self._agnes_cfg["model"]

    def _filter_available(
        self,
        order: list[str],
        health: HealthResult,
    ) -> list[str]:
        """过滤不可用的执行器."""
        health_map = {
            "deepseek_web": health.deepseek_web,
            "deepseek_api": health.deepseek_api,
            "zhipu": health.zhipu,
            "github": health.github,
            "agnes": health.agnes,
        }
        available = []
        for name in order:
            if name not in health_map:
                available.append(name)
                continue
            status = health_map[name]
            if status and status.available:
                available.append(name)
            elif name in ("zhipu", "github", "agnes"):
                available.append(name)  # 免费 Provider 始终可用
        return available

    # ── 配置加载 ──

    @staticmethod
    def _load_config(config_path: str | Path | None) -> dict:
        if config_path:
            path = Path(config_path)
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                return _deep_merge(copy.deepcopy(DEFAULT_CONFIG), loaded)
        return copy.deepcopy(DEFAULT_CONFIG)


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
