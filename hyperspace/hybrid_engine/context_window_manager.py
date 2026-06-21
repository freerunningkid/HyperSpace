"""ContextWindowManager —— DeepSeek Web 对话上下文窗口管理.

核心职责:
  1. 追踪每个对话 session 的状态 (消息数 / 估算 token / 上下文上限)
  2. 判断上下文窗口是否接近满 (≥85%)
  3. 满时自动压缩历史 → 创建新 session → 注入摘要
  4. 报错时自动故障恢复 → 压缩 + 新 session
  5. 保证多轮对话记忆不因窗口满而断开
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from .deepseek_web_client import DeepSeekWebClient, DeepSeekWebResponse

logger = logging.getLogger("hyperspace.context_window")

# ── 常量 ──

DEFAULT_CONTEXT_LIMIT = 64_000        # DeepSeek V3 上下文上限 (token)
COMPRESS_THRESHOLD = 0.85             # 触发压缩的阈值 (85%)
MAX_CONSECUTIVE_FAILURES = 3          # 连续失败上限
TOKEN_EST_RATIO = 0.3                 # 粗略估算: 字符数 * 0.3 ≈ token 数

# 压缩提示语 (发给 DeepSeek API / Zhipu 做摘要)
_COMPRESS_PROMPT = """你是对话摘要助手。请阅读以下对话记录，提取所有关键信息，包括：
- 用户的需求和问题
- 你给出的回答要点
- 已做的决策和结论
- 待办事项
- 重要上下文（代码片段、配置、路径等）

用简洁的中文压缩到 300 字以内。只输出摘要，不要额外说明。

对话记录：
{history}
"""


# ── 数据结构 ──

@dataclass
class SessionState:
    """一个对话 session 的状态."""
    session_id: str                     # DeepSeek 的 chat_session_id
    message_count: int = 0              # 已发送的消息数
    estimated_tokens: int = 0           # 估算已消耗的 token 数
    context_limit: int = DEFAULT_CONTEXT_LIMIT
    summary: str = ""                   # 上次压缩的摘要
    created_at: float = 0.0
    last_active: float = 0.0
    consecutive_failures: int = 0       # 连续失败计数
    last_message_id: str = ""           # 上一条消息 ID (用作 parent_message_id)


@dataclass
class CompressionResult:
    """压缩结果."""
    summary: str
    new_session_id: str
    success: bool = True
    error: str = ""


# ── Token 估算 ──

def _estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数 (中英文混合)."""
    # 中文约占 1.5-2 tokens/字, 英文约占 0.25 tokens/字符
    # 用字符数 * 0.3 做粗略估算
    return max(1, int(len(text) * TOKEN_EST_RATIO))


# ── 上下文窗口管理器 ──

class ContextWindowManager:
    """DeepSeek Web 对话上下文管理器.

    包装 DeepSeekWebClient, 在每次调用前检查上下文状态,
    自动触发压缩 + 新 session 创建.

    compress_fn: 用于生成摘要的异步函数 (prompt -> summary).
                 通常由 HybridRouter 传入, 使用 DeepSeek API / Zhipu 做摘要.
    """

    def __init__(
        self,
        web_client: DeepSeekWebClient,
        compress_fn: Callable[[str], Awaitable[str]] | None = None,
        context_limit: int = DEFAULT_CONTEXT_LIMIT,
    ):
        self._web = web_client
        self._compress_fn = compress_fn
        self._context_limit = context_limit

        # key = session_key (str, 由调用方提供, 如 agent 传的 session_id)
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    # ── 公开入口 ──

    async def chat(
        self,
        session_key: str,
        prompt: str,
        images: list[str] | None = None,
        search_enabled: bool = True,
    ) -> DeepSeekWebResponse:
        """发送消息, 自动管理上下文窗口.

        session_key: 会话标识 (同一 key 复用同一对话上下文, 不同 key 独立)
                      传空字符串 "" 表示每次新建 (无状态模式).
        """
        async with self._lock:
            # 无状态模式: 每次都新建 session
            if not session_key:
                return await self._new_session_chat("", prompt, images, search_enabled)

            state = self._sessions.get(session_key)
            if state is None:
                return await self._first_message(session_key, prompt, images, search_enabled)

            # 检查是否需要压缩
            if self._should_compress(state, prompt):
                logger.info(f"[ctx-window] 上下文窗口接近满 ({state.estimated_tokens}/{state.context_limit}), 触发压缩")
                return await self._compress_and_restart(
                    session_key, prompt, images, search_enabled
                )

            # 正常对话
            try:
                resp = await self._web.chat_completion(
                    prompt=prompt,
                    session_id=state.session_id,
                    parent_message_id=state.last_message_id or None,
                    search_enabled=search_enabled,
                    thinking_enabled=True,
                )
                self._update_state(state, prompt, resp.text, resp.message_id)
                state.consecutive_failures = 0
                return resp

            except Exception as e:
                state.consecutive_failures += 1
                logger.warning(
                    f"[ctx-window] session {state.session_id[:12]} 调用失败 "
                    f"(连续 {state.consecutive_failures} 次): {e}"
                )

                if state.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error("[ctx-window] 连续失败过多, 标记 Web 不可用")
                    raise RuntimeError("DeepSeek Web 连续调用失败, 触发降级")

                # 尝试压缩 + 新 session
                return await self._compress_and_restart(
                    session_key, prompt, images, search_enabled
                )

    # ── 内部方法 ──

    async def _first_message(
        self,
        session_key: str,
        prompt: str,
        images: list[str] | None,
        search_enabled: bool,
    ) -> DeepSeekWebResponse:
        """首次消息: 创建新 session 并发送."""
        # 如果有 summary 需要注入
        full_prompt = prompt
        state = self._sessions.get(session_key)
        if state and state.summary:
            full_prompt = f"[上下文摘要] 之前对话的关键信息：{state.summary}\n\n当前问题：{prompt}"

        return await self._new_session_chat(
            session_key, full_prompt, images, search_enabled
        )

    async def _new_session_chat(
        self,
        session_key: str,
        prompt: str,
        images: list[str] | None,
        search_enabled: bool,
    ) -> DeepSeekWebResponse:
        """创建新 session 并发送消息."""
        session_id = await self._web.create_chat_session()
        resp = await self._web.chat_completion(
            prompt=prompt,
            session_id=session_id,
            search_enabled=search_enabled,
            thinking_enabled=True,
        )

        # 更新状态
        state = SessionState(
            session_id=session_id,
            message_count=1,
            estimated_tokens=_estimate_tokens(prompt) + _estimate_tokens(resp.text),
            context_limit=self._context_limit,
            created_at=time.time(),
            last_active=time.time(),
            last_message_id=resp.message_id,
        )
        # 保留旧的 summary (如有)
        old = self._sessions.get(session_key)
        if old and old.summary:
            state.summary = old.summary

        if session_key:
            self._sessions[session_key] = state

        return resp

    def _should_compress(self, state: SessionState, new_prompt: str) -> bool:
        """检查是否应该触发压缩."""
        new_estimate = state.estimated_tokens + _estimate_tokens(new_prompt)
        threshold = int(state.context_limit * COMPRESS_THRESHOLD)
        return new_estimate >= threshold

    async def _compress_and_restart(
        self,
        session_key: str,
        prompt: str,
        images: list[str] | None,
        search_enabled: bool,
    ) -> DeepSeekWebResponse:
        """压缩历史 → 创建新 session → 注入摘要 → 发送."""
        state = self._sessions.get(session_key)
        summary = state.summary if state else ""

        if self._compress_fn and state:
            # 尝试用 API 做智能压缩
            try:
                history_text = await self._build_history_text(state)
                new_summary = await self._compress_fn(
                    _COMPRESS_PROMPT.format(history=history_text)
                )
                if new_summary and len(new_summary) > 10:
                    summary = new_summary.strip()
            except Exception as e:
                logger.warning(f"[ctx-window] 压缩失败, 使用旧摘要: {e}")
                # 保留已有摘要 (如果有的话)
                if not summary:
                    summary = "[对话历史摘要已丢失]"

        elif not summary:
            summary = "[对话历史摘要已丢失]"

        # 创建新 session, 注入摘要
        new_session_id = await self._web.create_chat_session()

        # 先用摘要消息填充上下文
        await self._web.chat_completion(
            prompt=f"[上下文摘要] 之前对话的关键信息：{summary}",
            session_id=new_session_id,
            thinking_enabled=False,
        )

        # 再发用户的真实消息
        resp = await self._web.chat_completion(
            prompt=prompt,
            session_id=new_session_id,
            images=images,
            search_enabled=search_enabled,
            thinking_enabled=True,
        )

        # 更新状态
        new_state = SessionState(
            session_id=new_session_id,
            message_count=2,
            estimated_tokens=_estimate_tokens(summary)
                + _estimate_tokens(prompt)
                + _estimate_tokens(resp.text),
            context_limit=self._context_limit,
            summary=summary,
            created_at=time.time(),
            last_active=time.time(),
        )
        if session_key:
            self._sessions[session_key] = new_state

        logger.info(
            f"[ctx-window] 会话已压缩重启: {state.session_id[:12] if state else 'none'} -> {new_session_id[:12]}"
        )
        return resp

    async def _build_history_text(self, state: SessionState) -> str:
        """构建供压缩用的历史文本.

        目前只提供摘要和基本信息.
        未来可扩展为从 DeepSeek 拉取历史消息.
        """
        parts = [
            f"消息数: {state.message_count}",
            f"估算 Token: {state.estimated_tokens}",
        ]
        if state.summary:
            parts.append(f"已有摘要: {state.summary}")
        return "\n".join(parts)

    def _update_state(self, state: SessionState, prompt: str, response: str,
                       message_id: str = ""):
        """更新 session 状态."""
        state.message_count += 1
        state.estimated_tokens += _estimate_tokens(prompt) + _estimate_tokens(response)
        state.last_active = time.time()
        if message_id:
            state.last_message_id = message_id

    # ── 状态管理 ──

    def get_session(self, session_key: str) -> SessionState | None:
        """获取指定 session 的状态."""
        return self._sessions.get(session_key)

    def list_sessions(self) -> dict[str, SessionState]:
        """列出所有活跃 session."""
        return dict(self._sessions)

    def clear_session(self, session_key: str):
        """清除指定 session."""
        self._sessions.pop(session_key, None)

    def clear_all(self):
        """清除所有 session."""
        self._sessions.clear()

    @property
    def active_count(self) -> int:
        return len(self._sessions)
