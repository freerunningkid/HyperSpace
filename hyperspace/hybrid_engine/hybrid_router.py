"""HybridRouter —— 核心混合路由决策引擎 (原生实现, 无外部依赖).

三层架构:
  DeepSeek Web (原生 Python 客户端) — 规划/搜索/识图/长文本 (零 Token 成本)
  ↔ DeepSeek API (OpenAI Compat) — 代码/翻译/结构化输出 (低成本)
  → 智谱 GLM (OpenAI Compat) — 最后兜底 (免费)

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
from ..providers.base import ProviderError, ProviderResponse
from ..providers.openai_compat import OpenAICompatProvider

# 我们的 DeepSeek Web 客户端 + 上下文管理
from .deepseek_web_client import DeepSeekWebClient, DeepSeekAuth, DeepSeekWebResponse
from .context_window_manager import ContextWindowManager
from . import web_auth as web_auth_mod

logger = logging.getLogger("hyperspace.hybrid_router")


@dataclass
class RoutingDecision:
    """路由决策."""
    executor: str = "deepseek_web"
    model: str = "deepseek-chat"
    fallback_order: list[str] = field(default_factory=lambda: [
        "deepseek_web", "deepseek_api", "zhipu",
    ])
    reason: str = ""


# ── 模式枚举 ──

FORCE_MODES = {"force_web", "force_api", "force_zhipu"}
LEGACY_MODES = {"free_text", "free_vision", "cheap_capable", "premium"}
ALL_MODES = LEGACY_MODES | FORCE_MODES | {"auto"}

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


class HybridRouter:
    """混合推理路由器 —— 任务分析 → 健康检查 → 路由 → 执行 → 后处理."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        deepseek_api_config: dict | None = None,
        zhipu_config: dict | None = None,
    ):
        self._cfg = self._load_config(config_path)
        self._deepseek_api_cfg = deepseek_api_config or {}
        self._zhipu_cfg = zhipu_config or {}

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

    def _init_web_client(self):
        """从已保存凭据初始化 DeepSeek Web 客户端和上下文管理器."""
        auth_data = web_auth_mod.load_saved_auth()
        if auth_data:
            auth = DeepSeekAuth.from_dict(auth_data)
            if auth.is_valid():
                self._web_client = DeepSeekWebClient(auth)
                self._ctx_mgr = ContextWindowManager(
                    web_client=self._web_client,
                    compress_fn=self._compress_via_api,
                )
                logger.info("DeepSeek Web 客户端 + 上下文管理器已初始化 (凭据有效)")

    def _get_saved_auth(self) -> dict | None:
        """返回已保存的凭据 (供 HealthChecker 使用)."""
        return web_auth_mod.load_saved_auth()

    # ── 公开入口 ──

    async def execute(
        self,
        prompt: str,
        images: list[str] | None = None,
        context: str | None = None,
        mode: str = "auto",
        session_key: str = "",
    ) -> ProcessedResult:
        """完整流程: 分析 → 路由 → 执行 → 后处理.

        session_key: 对话会话标识, 用于多轮上下文管理.
                     空字符串 = 每次新建 (无状态).
                     同一 key = 自动追踪上下文, 满时压缩.
        """
        profile = analyze_task(prompt, images=images, context=context)

        decision = self._route(profile, mode)

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
            context=context,
            session_key=session_key,
        )

        return result

    # ── 路由决策 ──

    def _route(self, profile: TaskProfile, mode: str) -> RoutingDecision:
        """基于 TaskProfile + mode 做出路由决策."""
        if mode == "force_web":
            return RoutingDecision(
                executor="deepseek_web",
                model=self._cfg["executors"]["deepseek_web"]["model"],
                reason="force_web mode",
            )
        if mode == "force_api":
            return RoutingDecision(
                executor="deepseek_api",
                model="deepseek-chat",
                reason="force_api mode",
            )
        if mode == "force_zhipu":
            return RoutingDecision(
                executor="zhipu",
                model="glm-4.7-flash",
                reason="force_zhipu mode",
            )
        if mode == "auto":
            return self._route_auto(profile)
        if mode in LEGACY_MODES:
            return RoutingDecision(
                executor="", reason=f"legacy_mode:{mode}", fallback_order=[]
            )

        return RoutingDecision(executor="deepseek_web", reason=f"default (mode={mode})")

    def _route_auto(self, profile: TaskProfile) -> RoutingDecision:
        """优先级规则匹配."""
        rules = self._cfg["routing"]["rules"]
        default_executor = self._cfg["routing"]["default_executor"]

        for rule in rules:
            condition = rule["condition"]
            executor = rule["executor"]
            if getattr(profile, condition, False):
                model = self._resolve_model(executor)
                return RoutingDecision(
                    executor=executor, model=model,
                    reason=f"rule:{condition}->{executor}",
                )

        return RoutingDecision(
            executor=default_executor,
            model=self._resolve_model(default_executor),
            reason=f"default->{default_executor}",
        )

    def _resolve_model(self, executor: str) -> str:
        cfg = self._cfg["executors"].get(executor, {})
        return cfg.get("model", "unknown")

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
        """带降级的执行."""

        # 构建执行器映射
        executors = self._build_executor_map()

        # 过滤可用执行器
        available = self._filter_available(decision.fallback_order, health)

        # 执行
        result = await self._fallback.execute(
            executors=executors,
            primary_executor=decision.executor,
            prompt=prompt,
            images=images,
            context=context,
            fallback_order=available,
            session_key=session_key,
        )

        if result.success and result.value:
            processed = ResultProcessor.process(
                raw_text=result.value,
                executor_name=result.used_executor or decision.executor,
                model_name=result.used_model or decision.model,
            )
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
        """构建可调用的执行器函数映射."""
        return {
            "deepseek_web": self._call_web,
            "deepseek_api": self._call_api,
            "zhipu": self._call_zhipu,
        }

    async def _compress_via_api(self, text: str) -> str:
        """用可用 API (DeepSeek API 或 Zhipu) 做上下文压缩摘要."""
        cfg = self._deepseek_api_cfg or self._zhipu_cfg
        if not cfg or not cfg.get("api_key"):
            # 无 API Key, 返回原文截断
            lines = text.split("\n")
            return "\n".join(lines[-5:]) if len(lines) > 5 else text

        try:
            from ..config import ProviderCandidate
            provider_name = cfg.get("provider", "deepseek")
            key_env = "DEEPSEEK_API_KEY" if provider_name == "deepseek" else "ZHIPU_API_KEY"
            old = os.environ.get(key_env)
            os.environ[key_env] = cfg["api_key"]

            try:
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
            finally:
                if old:
                    os.environ[key_env] = old
                else:
                    os.environ.pop(key_env, None)
        except Exception as e:
            logger.warning(f"压缩 API 调用失败: {e}")
            # 回退: 截取最后几行
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

        # 合并 context 到 prompt
        if context:
            full_prompt = f"{context}\n\n{prompt}"
        else:
            full_prompt = prompt

        try:
            # 通过上下文管理器发送 (自动处理压缩/新 session/故障恢复)
            resp = await self._ctx_mgr.chat(
                session_key=session_key,
                prompt=full_prompt,
                images=images,
                search_enabled=True,
            )
        except RuntimeError as e:
            if "连续失败" in str(e):
                # 连续失败, 触发降级 (让 _call_with_fallback 处理)
                raise
            raise

        # 合并思维链和最终回答
        if resp.thinking:
            full_text = f"{resp.thinking}\n\n{resp.text}"
        else:
            full_text = resp.text

        return full_text, "deepseek-chat"

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
        }
        available = []
        for name in order:
            if name not in health_map:
                available.append(name)
                continue
            status = health_map[name]
            if status and status.available:
                available.append(name)
            elif name == "zhipu":
                available.append(name)  # Zhipu 始终可用
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
