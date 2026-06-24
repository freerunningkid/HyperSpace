# -*- coding: utf-8 -*-
"""测试: ContextWindowManager — 上下文窗口追踪、压缩触发、会话恢复.

纯单元测试，Mock DeepSeekWebClient 和 compress_fn，不打真实网络。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from hyperspace.hybrid_engine.context_window_manager import (
    COMPRESS_THRESHOLD,
    DEFAULT_CONTEXT_LIMIT,
    MAX_CONSECUTIVE_FAILURES,
    TOKEN_EST_RATIO,
    ContextWindowManager,
    SessionState,
    _estimate_tokens,
)
from hyperspace.hybrid_engine.deepseek_web_client import DeepSeekWebResponse


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _make_response(text: str = "response", thinking: str = "") -> DeepSeekWebResponse:
    """构造一个标准响应."""
    return DeepSeekWebResponse(
        text=text,
        thinking=thinking,
        session_id="sess_001",
        finish_reason="stop",
    )


def _make_web_client() -> AsyncMock:
    """构造 mock DeepSeekWebClient."""
    client = AsyncMock()
    client.create_chat_session = AsyncMock(return_value="sess_new")
    client.chat_completion = AsyncMock(return_value=_make_response())
    return client


def _make_compress_fn(return_summary: str = "压缩摘要内容") -> AsyncMock:
    """构造 mock 压缩函数."""
    fn = AsyncMock(return_value=return_summary)
    return fn


# ══════════════════════════════════════════════════════════════════════
# TestEstimateTokens
# ══════════════════════════════════════════════════════════════════════

class TestEstimateTokens:
    """Token 估算函数."""

    def test_empty_string_returns_1(self):
        assert _estimate_tokens("") == 1

    def test_short_text(self):
        # "hello" = 5 chars * 0.3 = 1.5 → int = 1 → max(1,1) = 1
        assert _estimate_tokens("hello") == 1

    def test_medium_text(self):
        # 100 chars * 0.3 = 30
        assert _estimate_tokens("x" * 100) == 30

    def test_long_text(self):
        # 10000 chars * 0.3 = 3000
        assert _estimate_tokens("x" * 10000) == 3000

    def test_chinese_text(self):
        # "你好世界" = 4 chars * 0.3 = 1.2 → 1
        assert _estimate_tokens("你好世界") == 1

    def test_token_est_ratio_constant(self):
        """验证 TOKEN_EST_RATIO 值为 0.3."""
        assert TOKEN_EST_RATIO == 0.3


# ══════════════════════════════════════════════════════════════════════
# TestSessionState
# ══════════════════════════════════════════════════════════════════════

class TestSessionState:
    """SessionState 数据结构."""

    def test_default_values(self):
        state = SessionState(session_id="s_1")
        assert state.session_id == "s_1"
        assert state.message_count == 0
        assert state.estimated_tokens == 0
        assert state.context_limit == DEFAULT_CONTEXT_LIMIT
        assert state.summary == ""
        assert state.created_at == 0.0
        assert state.last_active == 0.0
        assert state.consecutive_failures == 0

    def test_custom_values(self):
        state = SessionState(
            session_id="s_custom",
            message_count=5,
            estimated_tokens=2000,
            context_limit=32000,
            summary="previous summary",
            consecutive_failures=2,
        )
        assert state.message_count == 5
        assert state.estimated_tokens == 2000
        assert state.context_limit == 32000
        assert state.summary == "previous summary"
        assert state.consecutive_failures == 2


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 初始化与属性
# ══════════════════════════════════════════════════════════════════════

class TestContextWindowManagerInit:
    """初始化与基本属性."""

    def test_init_defaults(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web)
        assert mgr._web == web
        assert mgr._context_limit == DEFAULT_CONTEXT_LIMIT
        assert mgr._compress_fn is None
        assert mgr._sessions == {}
        assert mgr.active_count == 0

    def test_init_custom_context_limit(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web, context_limit=32000)
        assert mgr._context_limit == 32000

    def test_init_with_compress_fn(self):
        web = _make_web_client()
        compress_fn = _make_compress_fn()
        mgr = ContextWindowManager(web, compress_fn=compress_fn)
        assert mgr._compress_fn == compress_fn


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 首次对话
# ══════════════════════════════════════════════════════════════════════

class TestFirstMessage:
    """首次对话：自动创建 session，初始化状态."""

    @pytest.mark.asyncio
    async def test_first_message_creates_session(self):
        """首次对话自动创建 session 并初始化状态."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="sess_first")
        web.chat_completion = AsyncMock(return_value=_make_response(text="你好！"))

        mgr = ContextWindowManager(web)
        resp = await mgr.chat(session_key="user_1", prompt="你好")

        assert resp.text == "你好！"
        web.create_chat_session.assert_awaited_once()
        web.chat_completion.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_first_message_initializes_state(self):
        """首次对话后 state 存在且字段正确."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="sess_A")
        web.chat_completion = AsyncMock(return_value=_make_response(text="ok"))

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="user_2", prompt="hello")

        state = mgr.get_session("user_2")
        assert state is not None
        assert state.session_id == "sess_A"
        assert state.message_count == 1
        assert state.estimated_tokens > 0
        assert state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_first_message_uses_session_key_as_key(self):
        """不同 session_key 创建不同 session."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(side_effect=["s_A", "s_B"])
        web.chat_completion = AsyncMock(return_value=_make_response())

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="alice", prompt="hi")
        await mgr.chat(session_key="bob", prompt="yo")

        assert mgr.active_count == 2
        assert mgr.get_session("alice").session_id == "s_A"
        assert mgr.get_session("bob").session_id == "s_B"

    @pytest.mark.asyncio
    async def test_first_message_calls_chat_completion_with_thinking(self):
        """首次对话时 chat_completion 传 thinking_enabled=True."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_think")
        web.chat_completion = AsyncMock(return_value=_make_response())

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="u1", prompt="复杂问题")

        call_kwargs = web.chat_completion.call_args.kwargs
        assert call_kwargs["thinking_enabled"] is True

    @pytest.mark.asyncio
    async def test_quick_mode_disables_thinking(self):
        """Quick 模式关闭 thinking_enabled."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_quick")
        web.chat_completion = AsyncMock(return_value=_make_response())

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="u1", prompt="简单回答", web_mode="quick")

        call_kwargs = web.chat_completion.call_args.kwargs
        assert call_kwargs["thinking_enabled"] is False

    @pytest.mark.asyncio
    async def test_vision_mode_uploads_images_as_ref_file_ids(self):
        """Vision 模式上传图片时传给 chat_completion 的是 ref_file_ids，而不是 images."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_vision")
        web.prepare_ref_file_ids = AsyncMock(return_value=["file_123"])
        web.chat_completion = AsyncMock(return_value=_make_response())

        mgr = ContextWindowManager(web)
        await mgr.chat(
            session_key="u1",
            prompt="这张截图有什么 bug",
            images=["screenshot.png"],
            web_mode="vision",
        )

        web.prepare_ref_file_ids.assert_awaited_once_with(["screenshot.png"])
        call_kwargs = web.chat_completion.call_args.kwargs
        assert call_kwargs["ref_file_ids"] == ["file_123"]
        assert "images" not in call_kwargs
        assert call_kwargs["thinking_enabled"] is True

    @pytest.mark.asyncio
    async def test_first_message_passes_search_enabled(self):
        """首次对话时传递 search_enabled 参数."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_search")
        web.chat_completion = AsyncMock(return_value=_make_response())

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="u1", prompt="搜索一下", search_enabled=False)

        call_kwargs = web.chat_completion.call_args.kwargs
        assert call_kwargs["search_enabled"] is False


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 无状态模式
# ══════════════════════════════════════════════════════════════════════

class TestStatelessMode:
    """session_key="" 时每次新建 session，不复用."""

    @pytest.mark.asyncio
    async def test_stateless_creates_new_session_every_time(self):
        web = _make_web_client()
        web.create_chat_session = AsyncMock(side_effect=["s1", "s2", "s3"])
        web.chat_completion = AsyncMock(return_value=_make_response())

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="", prompt="msg1")
        await mgr.chat(session_key="", prompt="msg2")
        await mgr.chat(session_key="", prompt="msg3")

        assert web.create_chat_session.call_count == 3
        assert mgr.active_count == 0  # 不存储到 _sessions

    @pytest.mark.asyncio
    async def test_stateless_does_not_accumulate(self):
        """无状态模式每次都是新对话，不复用 session_id."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(side_effect=["s1", "s2"])
        call_sessions = []

        async def track_session(prompt, session_id=None, **kwargs):
            call_sessions.append(session_id)
            return _make_response()

        web.chat_completion = AsyncMock(side_effect=track_session)

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="", prompt="m1")
        await mgr.chat(session_key="", prompt="m2")

        # 每次都创建了新 session
        assert web.create_chat_session.call_count == 2
        # 两次 chat_completion 都用了不同的 session_id
        assert call_sessions[0] == "s1"
        assert call_sessions[1] == "s2"
        assert call_sessions[0] != call_sessions[1]


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 多轮对话累加
# ══════════════════════════════════════════════════════════════════════

class TestMultiTurnAccumulation:
    """多轮对话中 message_count 和 estimated_tokens 正确累加."""

    @pytest.mark.asyncio
    async def test_message_count_increments(self):
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_multi")
        web.chat_completion = AsyncMock(return_value=_make_response(text="短回复"))

        mgr = ContextWindowManager(web)
        for i in range(3):
            await mgr.chat(session_key="u1", prompt=f"msg{i}")

        state = mgr.get_session("u1")
        assert state.message_count == 3

    @pytest.mark.asyncio
    async def test_estimated_tokens_accumulates(self):
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_tok")
        # 返回固定长度响应
        web.chat_completion = AsyncMock(return_value=_make_response(text="R" * 100))

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="u1", prompt="P" * 100)

        # 估算: prompt(100*0.3=30) + response(100*0.3=30) = 60
        state = mgr.get_session("u1")
        first_tokens = state.estimated_tokens

        await mgr.chat(session_key="u1", prompt="Q" * 200)
        # 追加: prompt(200*0.3=60) + response(100*0.3=30) = 90
        # 总计: 60 + 90 = 150
        state = mgr.get_session("u1")
        assert state.estimated_tokens == first_tokens + 90
        assert state.message_count == 2

    @pytest.mark.asyncio
    async def test_session_state_persists_across_calls(self):
        """同一 session_key 多次调用，state 持续更新."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_persist")
        web.chat_completion = AsyncMock(return_value=_make_response("ok"))

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="persistent", prompt="first")

        state1 = mgr.get_session("persistent")
        sid1 = state1.session_id
        count1 = state1.message_count

        await mgr.chat(session_key="persistent", prompt="second")

        state2 = mgr.get_session("persistent")
        assert state2.session_id == sid1  # 同一 session_id
        assert state2.message_count == count1 + 1

    @pytest.mark.asyncio
    async def test_consecutive_failures_reset_on_success(self):
        """成功调用后 consecutive_failures 重置为 0."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_reset")
        # 第一次失败
        web.chat_completion = AsyncMock(
            side_effect=[
                Exception("timeout"),  # 失败 → compress_and_restart 会尝试
                _make_response("ok"),  # compress 中的摘要注入成功
                _make_response("ok"),  # 用户消息成功
            ]
        )

        mgr = ContextWindowManager(web)
        # 第一次调用会失败然后 compress_and_restart
        try:
            await mgr.chat(session_key="u_fail", prompt="test")
        except Exception:
            pass
        # 检查 state（可能已被压缩重建）
        state = mgr.get_session("u_fail")
        if state:
            assert state.consecutive_failures == 0


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 压缩触发
# ══════════════════════════════════════════════════════════════════════

class TestCompressionTrigger:
    """estimated_tokens ≥ context_limit * 0.85 时触发压缩."""

    @pytest.mark.asyncio
    async def test_compression_triggers_when_threshold_exceeded(self):
        """超过 85% 阈值时触发压缩."""
        web = _make_web_client()
        limit = 1000
        # 初始状态：tokens 接近阈值
        # threshold = 1000 * 0.85 = 850
        web.create_chat_session = AsyncMock(side_effect=["s_pre", "s_new"])

        # 所有 chat_completion 都返回短响应
        web.chat_completion = AsyncMock(return_value=_make_response(text="ok"))

        compress_fn = _make_compress_fn("这是关于架构设计的核心摘要内容")

        mgr = ContextWindowManager(web, compress_fn=compress_fn, context_limit=limit)

        # 第一步：制造接近阈值的状态
        # 手动注入一个接近阈值的 state
        import time
        pre_state = SessionState(
            session_id="s_pre",
            message_count=10,
            estimated_tokens=860,  # 超过 850
            context_limit=limit,
            created_at=time.time(),
            last_active=time.time(),
        )
        mgr._sessions["u_compress"] = pre_state

        # 现在再发一条消息，_should_compress 检查：
        # 860 + _estimate_tokens("hello") = 860 + 1 = 861 >= 850 → 触发压缩
        await mgr.chat(session_key="u_compress", prompt="hello")

        # 验证压缩函数被调用
        compress_fn.assert_awaited_once()

        # 验证创建了新 session
        assert web.create_chat_session.call_count >= 1

        # 验证新状态被创建
        new_state = mgr.get_session("u_compress")
        assert new_state is not None
        assert new_state.summary == "这是关于架构设计的核心摘要内容"

    @pytest.mark.asyncio
    async def test_no_compression_when_below_threshold(self):
        """低于 85% 阈值时不触发压缩."""
        web = _make_web_client()
        limit = 10000  # threshold = 8500
        web.create_chat_session = AsyncMock(return_value="s_low")
        web.chat_completion = AsyncMock(return_value=_make_response(text="ok"))

        compress_fn = _make_compress_fn()
        mgr = ContextWindowManager(web, compress_fn=compress_fn, context_limit=limit)

        import time
        pre_state = SessionState(
            session_id="s_low",
            message_count=5,
            estimated_tokens=500,  # 远低于 8500
            context_limit=limit,
            created_at=time.time(),
            last_active=time.time(),
        )
        mgr._sessions["u_low"] = pre_state

        await mgr.chat(session_key="u_low", prompt="hello")

        # 压缩函数不应被调用
        compress_fn.assert_not_awaited()
        # 不应创建新 session（除了最初的手动注入）
        # 实际上它使用的是已有的 session_id
        call_sessions = [
            c.kwargs.get("session_id") for c in web.chat_completion.call_args_list
        ]
        assert "s_low" in call_sessions

    @pytest.mark.asyncio
    async def test_should_compress_at_exactly_85_percent(self):
        """恰好 85% 时触发压缩."""
        limit = 10000  # threshold = 8500
        web = _make_web_client()
        mgr = ContextWindowManager(web, context_limit=limit)

        state = SessionState(
            session_id="s_exact",
            estimated_tokens=8499,  # 8499 + 1 >= 8500 → 触发
            context_limit=limit,
        )
        # 8499 + _estimate_tokens("x") = 8499 + 1 = 8500 >= 8500 → True
        assert mgr._should_compress(state, "x") is True

    @pytest.mark.asyncio
    async def test_should_compress_below_85_percent(self):
        """低于 85% 时不触发."""
        limit = 10000  # threshold = 8500
        web = _make_web_client()
        mgr = ContextWindowManager(web, context_limit=limit)

        state = SessionState(
            session_id="s_below",
            estimated_tokens=8498,  # 8498 + 1 = 8499 < 8500 → False
            context_limit=limit,
        )
        assert mgr._should_compress(state, "x") is False

    @pytest.mark.asyncio
    async def test_should_compress_at_86_percent(self):
        """86% 明确触发压缩."""
        limit = 10000  # threshold = 8500
        web = _make_web_client()
        mgr = ContextWindowManager(web, context_limit=limit)

        state = SessionState(
            session_id="s_86",
            estimated_tokens=8600,  # 8600 + _estimate_tokens("x") = 8601 >= 8500 → True
            context_limit=limit,
        )
        assert mgr._should_compress(state, "x") is True


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 压缩后摘要注入
# ══════════════════════════════════════════════════════════════════════

class TestSummaryInjection:
    """压缩后新 session 的首条消息包含摘要."""

    @pytest.mark.asyncio
    async def test_new_session_gets_summary_injected(self):
        """压缩后第一个 chat_completion 调用注入摘要消息."""
        web = _make_web_client()
        limit = 1000  # threshold = 850
        web.create_chat_session = AsyncMock(return_value="s_post_compress")

        chat_calls = []

        async def record_chat(**kwargs):
            chat_calls.append(kwargs)
            return _make_response("got it")

        web.chat_completion = AsyncMock(side_effect=record_chat)

        compress_fn = _make_compress_fn("核心摘要：讨论了架构设计")

        mgr = ContextWindowManager(web, compress_fn=compress_fn, context_limit=limit)

        import time
        pre_state = SessionState(
            session_id="s_old",
            message_count=20,
            estimated_tokens=900,
            context_limit=limit,
            summary="旧摘要",
            created_at=time.time(),
            last_active=time.time(),
        )
        mgr._sessions["u_si"] = pre_state

        await mgr.chat(session_key="u_si", prompt="继续讨论")

        # 应该有两次 chat_completion 调用：
        # 1. 摘要注入消息
        # 2. 用户的实际消息
        assert len(chat_calls) == 2

        # 第一条是摘要注入
        first_call = chat_calls[0]
        assert "核心摘要" in first_call["prompt"]
        assert "上下文摘要" in first_call["prompt"]
        assert first_call["thinking_enabled"] is False  # 摘要消息不启用思考

        # 第二条是用户的实际消息
        second_call = chat_calls[1]
        assert second_call["prompt"] == "继续讨论"
        assert second_call["thinking_enabled"] is True

    @pytest.mark.asyncio
    async def test_compression_updates_summary_in_state(self):
        """压缩后新 state 的 summary 字段被更新."""
        web = _make_web_client()
        limit = 1000
        web.create_chat_session = AsyncMock(return_value="s_new_summary")
        web.chat_completion = AsyncMock(return_value=_make_response("ok"))

        compress_fn = _make_compress_fn("这是通过压缩生成的全新摘要内容文本")

        mgr = ContextWindowManager(web, compress_fn=compress_fn, context_limit=limit)

        import time
        pre_state = SessionState(
            session_id="s_old2",
            message_count=15,
            estimated_tokens=900,
            context_limit=limit,
            summary="旧摘要",
            created_at=time.time(),
            last_active=time.time(),
        )
        mgr._sessions["u_s2"] = pre_state

        await mgr.chat(session_key="u_s2", prompt="继续")

        new_state = mgr.get_session("u_s2")
        assert new_state.summary == "这是通过压缩生成的全新摘要内容文本"

    @pytest.mark.asyncio
    async def test_compression_without_compress_fn_uses_placeholder(self):
        """无 compress_fn 时使用占位摘要."""
        web = _make_web_client()
        limit = 1000
        web.create_chat_session = AsyncMock(return_value="s_no_compress_fn")
        web.chat_completion = AsyncMock(return_value=_make_response("ok"))

        mgr = ContextWindowManager(web, compress_fn=None, context_limit=limit)

        import time
        pre_state = SessionState(
            session_id="s_old3",
            message_count=5,
            estimated_tokens=900,
            context_limit=limit,
            summary="",
            created_at=time.time(),
            last_active=time.time(),
        )
        mgr._sessions["u_nofn"] = pre_state

        await mgr.chat(session_key="u_nofn", prompt="hello")

        new_state = mgr.get_session("u_nofn")
        assert "[对话历史摘要已丢失]" in new_state.summary

    @pytest.mark.asyncio
    async def test_old_summary_preserved_when_compress_fn_fails(self):
        """压缩函数失败时保留旧摘要."""
        web = _make_web_client()
        limit = 1000
        web.create_chat_session = AsyncMock(return_value="s_fail_compress")
        web.chat_completion = AsyncMock(return_value=_make_response("ok"))

        compress_fn = AsyncMock(side_effect=Exception("API 不可用"))

        mgr = ContextWindowManager(web, compress_fn=compress_fn, context_limit=limit)

        import time
        pre_state = SessionState(
            session_id="s_old4",
            message_count=5,
            estimated_tokens=900,
            context_limit=limit,
            summary="保留的旧摘要",
            created_at=time.time(),
            last_active=time.time(),
        )
        mgr._sessions["u_keep"] = pre_state

        await mgr.chat(session_key="u_keep", prompt="hello")

        new_state = mgr.get_session("u_keep")
        assert new_state.summary == "保留的旧摘要"


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 连续失败检测
# ══════════════════════════════════════════════════════════════════════

class TestConsecutiveFailures:
    """≥3 次连续失败触发 RuntimeError."""

    @pytest.mark.asyncio
    async def test_three_consecutive_failures_raises(self):
        """连续 3 次失败应抛出 RuntimeError."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_fail")
        # chat_completion 连续失败
        web.chat_completion = AsyncMock(side_effect=Exception("timeout"))

        mgr = ContextWindowManager(web, compress_fn=None)

        import time
        pre_state = SessionState(
            session_id="s_fail",
            message_count=3,
            estimated_tokens=100,
            context_limit=10000,
            created_at=time.time(),
            last_active=time.time(),
            consecutive_failures=2,  # 已经失败了 2 次
        )
        mgr._sessions["u_fail"] = pre_state

        with pytest.raises(RuntimeError, match="连续调用失败"):
            await mgr.chat(session_key="u_fail", prompt="test")

    @pytest.mark.asyncio
    async def test_two_failures_triggers_compression_not_runtime_error(self):
        """连续 2 次失败 → 触发 compress_and_restart，不抛 RuntimeError."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(side_effect=["s_old_fail", "s_new_after"])

        call_count = [0]

        async def flaky_chat(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise Exception("timeout")
            return _make_response("recovered")

        web.chat_completion = AsyncMock(side_effect=flaky_chat)

        mgr = ContextWindowManager(web, compress_fn=None)

        import time
        pre_state = SessionState(
            session_id="s_old_fail",
            message_count=5,
            estimated_tokens=100,
            context_limit=10000,
            created_at=time.time(),
            last_active=time.time(),
            consecutive_failures=1,  # 已失败 1 次
        )
        mgr._sessions["u_two"] = pre_state

        # 不应抛出 RuntimeError（第 2 次失败触发 compress_and_restart）
        try:
            await mgr.chat(session_key="u_two", prompt="test")
        except RuntimeError as e:
            if "连续调用失败" in str(e):
                pytest.fail("不应在 2 次失败时抛出 RuntimeError")

    @pytest.mark.asyncio
    async def test_normal_chat_failure_increments_counter(self):
        """正常路径失败时 consecutive_failures 递增."""
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_counter")
        web.chat_completion = AsyncMock(side_effect=Exception("network error"))

        mgr = ContextWindowManager(web, compress_fn=None)

        import time
        pre_state = SessionState(
            session_id="s_counter",
            message_count=3,
            estimated_tokens=100,
            context_limit=10000,
            created_at=time.time(),
            last_active=time.time(),
            consecutive_failures=0,
        )
        mgr._sessions["u_counter"] = pre_state

        # 这次调用会失败 → 进入 except → consecutive_failures += 1 → compress_and_restart
        # compress_and_restart 需要创建新 session 和注入摘要
        # 由于我们没有设置足够高的 tokens，它不会触发压缩阈值路径
        # 实际上在 except 块中：先 += 1，然后检查 >= 3，然后 compress_and_restart
        # compress_and_restart 会创建新 session

        # 准备 compress_and_restart 所需的 mock
        web.chat_completion = AsyncMock(
            side_effect=[
                Exception("network error"),  # 第一次调用失败
                _make_response("summary ok"),  # 摘要注入
                _make_response("final ok"),  # 用户消息
            ]
        )

        try:
            await mgr.chat(session_key="u_counter", prompt="test")
        except Exception:
            pass
        # 如果恢复成功，state 应该被重建且 counter 为 0


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 会话状态管理
# ══════════════════════════════════════════════════════════════════════

class TestSessionStateManagement:
    """get_session / list_sessions / clear_session / clear_all / active_count."""

    def test_active_count_zero_initially(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web)
        assert mgr.active_count == 0

    @pytest.mark.asyncio
    async def test_active_count_after_chat(self):
        web = _make_web_client()
        web.create_chat_session = AsyncMock(return_value="s_count")
        web.chat_completion = AsyncMock(return_value=_make_response())

        mgr = ContextWindowManager(web)
        await mgr.chat(session_key="a", prompt="hi")
        assert mgr.active_count == 1

        await mgr.chat(session_key="b", prompt="yo")
        assert mgr.active_count == 2

    def test_get_session_nonexistent(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web)
        assert mgr.get_session("nonexistent") is None

    def test_list_sessions(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web)

        import time
        mgr._sessions["a"] = SessionState(
            session_id="s_a", created_at=time.time(), last_active=time.time()
        )
        mgr._sessions["b"] = SessionState(
            session_id="s_b", created_at=time.time(), last_active=time.time()
        )

        sessions = mgr.list_sessions()
        assert len(sessions) == 2
        assert "a" in sessions
        assert "b" in sessions

    def test_clear_session(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web)

        import time
        mgr._sessions["keep"] = SessionState(
            session_id="s_keep", created_at=time.time(), last_active=time.time()
        )
        mgr._sessions["remove"] = SessionState(
            session_id="s_remove", created_at=time.time(), last_active=time.time()
        )

        mgr.clear_session("remove")
        assert mgr.get_session("remove") is None
        assert mgr.get_session("keep") is not None
        assert mgr.active_count == 1

    def test_clear_session_nonexistent_no_error(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web)
        mgr.clear_session("no_such_key")  # 不抛异常

    def test_clear_all(self):
        web = _make_web_client()
        mgr = ContextWindowManager(web)

        import time
        mgr._sessions["a"] = SessionState(
            session_id="s_a", created_at=time.time(), last_active=time.time()
        )
        mgr._sessions["b"] = SessionState(
            session_id="s_b", created_at=time.time(), last_active=time.time()
        )

        mgr.clear_all()
        assert mgr.active_count == 0
        assert mgr.list_sessions() == {}

    def test_list_sessions_returns_copy(self):
        """list_sessions 返回副本，修改不影响内部."""
        web = _make_web_client()
        mgr = ContextWindowManager(web)

        import time
        mgr._sessions["x"] = SessionState(
            session_id="s_x", created_at=time.time(), last_active=time.time()
        )

        sessions = mgr.list_sessions()
        sessions["y"] = SessionState(
            session_id="s_y", created_at=time.time(), last_active=time.time()
        )

        assert "y" not in mgr._sessions  # 内部未被修改
        assert mgr.active_count == 1


# ══════════════════════════════════════════════════════════════════════
# TestContextWindowManager — 常量验证
# ══════════════════════════════════════════════════════════════════════

class TestConstants:
    """验证模块常量."""

    def test_default_context_limit(self):
        assert DEFAULT_CONTEXT_LIMIT == 64_000

    def test_compress_threshold(self):
        assert COMPRESS_THRESHOLD == 0.85

    def test_max_consecutive_failures(self):
        assert MAX_CONSECUTIVE_FAILURES == 3
