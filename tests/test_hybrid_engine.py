# -*- coding: utf-8 -*-
"""测试: Hybrid Engine 模块 —— TaskAnalyzer, HybridRouter, FallbackManager, ResultProcessor.

纯单元测试, 不打真实网络. Mock httpx 调用.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hyperspace.hybrid_engine.task_analyzer import TaskProfile, analyze_task
from hyperspace.hybrid_engine.hybrid_router import HybridRouter, RoutingDecision
from hyperspace.hybrid_engine.fallback import FallbackManager, FallbackResult
from hyperspace.hybrid_engine.result_processor import ProcessedResult, ResultProcessor


# ── TaskAnalyzer 测试 ──────────────────────────────────────────────

class TestTaskAnalyzer:
    """验证 analyze_task() 正确分类各类任务."""

    def test_coding_detection(self):
        p = analyze_task("write a quick sort algorithm in Python", images=None)
        assert p.needs_coding
        assert not p.has_image

    def test_planning_detection(self):
        p = analyze_task("help me plan a project architecture", images=None)
        assert p.needs_planning

    def test_translation_detection(self):
        p = analyze_task("translate this document to Chinese", images=None)
        assert p.needs_translation

    def test_search_detection(self):
        p = analyze_task("search for the latest AI research papers", images=None)
        assert p.needs_search

    def test_structured_detection(self):
        p = analyze_task("output as a JSON array please", images=None)
        assert p.needs_structured_output

    def test_image_detection(self):
        p = analyze_task("what is this?", images=["photo.jpg"])
        assert p.has_image

    def test_image_suggests_vision_mode(self):
        p = analyze_task("这张截图里的代码有什么 bug", images=["screenshot.png"])
        assert p.suggested_web_mode == "vision"

    def test_simple_question_suggests_quick_mode(self):
        p = analyze_task("你好，介绍一下你自己", images=None)
        assert p.suggested_web_mode == "quick"

    def test_explicit_expert_mode_suggests_expert(self):
        p = analyze_task("用专家模式帮我解这道数学题", images=None)
        assert p.suggested_web_mode == "expert"

    def test_search_news_suggests_quick_with_search(self):
        p = analyze_task("搜索一下今天的 AI 新闻", images=None)
        assert p.needs_search
        assert p.suggested_web_mode == "quick"

    def test_complex_search_uses_quick(self):
        p = analyze_task("分析最近 AI 技术趋势并给出报告", images=None)
        assert p.needs_search
        assert p.suggested_web_mode == "quick"  # Expert no search
        assert p.search_enabled is True

    def test_long_text_detection(self):
        p = analyze_task("x" * 6000, images=None)
        assert p.is_long

    def test_simple_question_no_flags(self):
        p = analyze_task("hello, how are you?", images=None)
        assert not bool(p)  # no flags set

    def test_chinese_coding(self):
        p = analyze_task("用 Python 写一个函数计算斐波那契数列", images=None)
        assert p.needs_coding

    def test_coding_fence(self):
        p = analyze_task("修复这段代码: ```python\nx = 1\n```", images=None)
        assert p.needs_coding

    def test_mixed_features(self):
        p = analyze_task("翻译以下 JSON 数据并输出为表格", images=None)
        assert p.needs_translation
        assert p.needs_structured_output

    def test_context_affects_analysis(self):
        # Context 较长, 应触发 is_long
        long_ctx = "background " * 3000
        p = analyze_task("short question", images=None, context=long_ctx)
        assert p.is_long

    def test_complexity_score(self):
        p = analyze_task("write a JSON parser that searches for patterns", images=None)
        assert p.complexity_score >= 1  # at least coding or search


# ── HybridRouter 测试 ──────────────────────────────────────────────

class TestHybridRouter:
    """验证 HybridRouter 的路由决策逻辑."""

    def setup_method(self):
        self.router = HybridRouter()

    def test_coding_routes_to_deepseek_api(self):
        p = analyze_task("implement a function in Python", images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_api"
        assert "rule:needs_coding" in d.reason

    def test_planning_routes_to_deepseek_web(self):
        p = analyze_task("create a project plan", images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_web"
        assert "rule:needs_planning" in d.reason

    def test_search_routes_to_deepseek_web(self):
        p = analyze_task("search for recent news", images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_web"

    def test_image_routes_to_deepseek_web(self):
        p = analyze_task("what is this?", images=["img.png"])
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_web"
        assert "rule:has_image" in d.reason

    def test_long_routes_to_deepseek_web(self):
        p = analyze_task("x" * 6000, images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_web"

    def test_translation_routes_to_deepseek_api(self):
        p = analyze_task("translate to English", images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_api"

    def test_structured_routes_to_deepseek_api(self):
        p = analyze_task("format as JSON table", images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_api"

    def test_simple_defaults_to_deepseek_web(self):
        p = analyze_task("hello", images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_web"
        assert "default" in d.reason

    def test_force_web(self):
        d = self.router._route(TaskProfile(), "force_web")
        assert d.executor == "deepseek_web"

    def test_force_web_quick_disables_thinking(self):
        d = self.router._route(TaskProfile(), "force_web", web_mode="quick")
        assert d.executor == "deepseek_web"
        assert d.web_mode == "quick"
        assert d.thinking_enabled is False

    def test_expert_mode_enables_thinking(self):
        p = analyze_task("用专家模式帮我解这道题", images=None)
        d = self.router._route(p, "auto")
        assert d.web_mode == "expert"
        assert d.thinking_enabled is True

    def test_search_news_uses_quick_with_search(self):
        p = analyze_task("搜索一下今天的 AI 新闻", images=None)
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_web"
        assert d.web_mode == "quick"
        assert d.search_enabled is True

    @pytest.mark.asyncio
    async def test_call_with_fallback_passes_web_mode_parameters(self):
        call_log = []

        async def fake_web(**kwargs):
            call_log.append(kwargs)
            return ("ok", "deepseek-chat")

        self.router._build_executor_map = MagicMock(return_value={"deepseek_web": fake_web})
        decision = RoutingDecision(
            executor="deepseek_web",
            web_mode="quick",
            search_enabled=False,
            thinking_enabled=False,
        )
        health = MagicMock()

        result = await self.router._call_with_fallback(
            decision=decision,
            health=health,
            prompt="简单回答",
            images=None,
            context=None,
            session_key="s1",
        )

        assert result.answer == "ok"
        assert call_log[0]["web_mode"] == "quick"
        assert call_log[0]["search_enabled"] is False
        assert call_log[0]["thinking_enabled"] is False

    def test_force_api(self):
        d = self.router._route(TaskProfile(), "force_api")
        assert d.executor == "deepseek_api"

    def test_force_zhipu(self):
        d = self.router._route(TaskProfile(), "force_zhipu")
        assert d.executor == "zhipu"

    def test_legacy_mode_free_text(self):
        p = analyze_task("hello", images=None)
        d = self.router._route(p, "free_text")
        assert d.executor == ""  # legacy
        assert "legacy_mode" in d.reason

    def test_legacy_mode_cheap_capable(self):
        p = analyze_task("hello", images=None)
        d = self.router._route(p, "cheap_capable")
        assert d.executor == ""

    def test_priority_order(self):
        """图片+编码 → 图片优先 (has_image 在 needs_coding 前面)."""
        p = analyze_task("write an algorithm", images=["img.jpg"])
        d = self.router._route(p, "auto")
        assert d.executor == "deepseek_web"  # has_image 优先级 > needs_coding
        assert "rule:has_image" in d.reason


# ── FallbackManager 测试 ───────────────────────────────────────────

class TestFallbackManager:
    """验证降级链与重试逻辑."""

    def setup_method(self):
        self.fb = FallbackManager()

    def test_success_on_first(self):
        """首选执行器立即成功."""
        async def good_fn(*args, **kwargs):
            return ("response_text", "model-1")

        result = self.fb.execute(
            executors={"primary": good_fn},
            primary_executor="primary",
            fallback_order=["primary", "secondary"],
        )
        import asyncio
        r = asyncio.run(result)
        assert r.success
        assert r.value == "response_text"

    def test_fallback_to_second(self):
        """首选失败 → 切到第二执行器."""
        call_log = []

        async def primary_fn(*args, **kwargs):
            raise Exception("timeout")
            call_log.append("primary")
            return ("", "")

        async def secondary_fn(*args, **kwargs):
            call_log.append("secondary")
            return ("ok", "model-2")

        executors = {"primary": primary_fn, "secondary": secondary_fn}
        import asyncio
        result = self.fb.execute(executors, "primary", fallback_order=["primary", "secondary"])
        r = asyncio.run(result)

    def test_retry_then_fallback(self):
        """瞬时错误重试 3 次后切下一执行器."""
        call_log = []

        async def primary_fn(*args, **kwargs):
            call_log.append("primary")
            raise Exception("timeout from server")

        async def secondary_fn(*args, **kwargs):
            call_log.append("secondary")
            return ("ok", "model-2")

        executors = {"primary": primary_fn, "secondary": secondary_fn}
        import asyncio
        result = self.fb.execute(executors, "primary", fallback_order=["primary", "secondary"])
        r = asyncio.run(result)
        assert r.success
        assert r.value == "ok"
        # primary was tried once (no retry for persistent failures after first attempt in same call)
        # Actually the retry logic tries: attempt 0 (no delay), then if fails, retries with delay
        assert "primary" in call_log
        assert "secondary" in call_log

    def test_all_fail(self):
        """全部执行器都失败."""
        async def fail_fn(*args, **kwargs):
            raise Exception("always fail")

        executors = {"a": fail_fn, "b": fail_fn}
        import asyncio
        result = self.fb.execute(executors, "a", fallback_order=["a", "b"])
        r = asyncio.run(result)
        assert not r.success
        assert len(r.errors) >= 2

    def test_error_classification(self):
        """异常分类."""
        assert FallbackManager._classify_error(Exception("timeout")) == "timeout"
        assert FallbackManager._classify_error(Exception("HTTP 429")) == "ratelimit"
        assert FallbackManager._classify_error(Exception("rate limit")) == "ratelimit"
        assert FallbackManager._classify_error(Exception("connection refused")) == "connection"
        assert FallbackManager._classify_error(Exception("network error")) == "connection"
        assert "auth" in FallbackManager._classify_error(Exception("401 unauthorized"))
        assert FallbackManager._classify_error(Exception("unknown error")) == "unknown"


# ── ResultProcessor 测试 ───────────────────────────────────────────

class TestResultProcessor:
    """验证结果后处理逻辑."""

    def test_thinking_tag_extraction(self):
        rp = ResultProcessor.process(
            "<thinking>parsing input</thinking>final answer here",
            executor_name="openclaw",
        )
        assert rp.plan == "parsing input"
        assert "final answer here" in rp.answer

    def test_details_tag_extraction(self):
        rp = ResultProcessor.process(
            "<details>step 1: read\nstep 2: process</details>output",
            executor_name="openclaw",
        )
        assert "step 1" in rp.plan
        assert "output" in rp.answer

    def test_chinese_thinking_tag(self):
        rp = ResultProcessor.process(
            "[思考]先分析问题[/思考]答案在此",
            executor_name="openclaw",
        )
        assert "先分析" in rp.plan
        assert "答案在此" in rp.answer

    def test_plain_text(self):
        rp = ResultProcessor.process(
            "just a regular response without thinking",
            executor_name="freellmapi",
        )
        assert rp.plan == ""
        assert rp.answer == "just a regular response without thinking"

    def test_empty_response(self):
        rp = ResultProcessor.process("", executor_name="zhipu")
        assert rp.answer == ""
        assert rp.plan == ""

    def test_only_thinking(self):
        rp = ResultProcessor.process(
            "<thinking>only think</thinking>",
            executor_name="openclaw",
        )
        assert rp.plan == "only think"
        assert rp.answer == "only think"  # fallback to plan when answer empty

    def test_multiple_thinking_blocks(self):
        rp = ResultProcessor.process(
            "<thinking>first thought</thinking>middle text<thinking>second thought</thinking>final",
            executor_name="openclaw",
        )
        assert "first thought" in rp.plan
        assert "second thought" in rp.plan
        assert "final" in rp.answer
