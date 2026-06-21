"""FallbackManager —— 降级与重试管理.

异常分类 + 降级链遍历 + 指数退避重试.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass
class FallbackResult:
    """降级管理的结果."""
    success: bool
    value: T | None = None
    used_executor: str | None = None
    used_model: str | None = None
    errors: list[dict] = field(default_factory=list)  # [{executor, error_type, msg}]


class FallbackManager:
    """执行降级链: 按顺序尝试每个 executor, 失败则切下一个.

    指数退避: 100ms → 200ms → 400ms (最多 3 次重试/executor)
    """

    # 可重试的错误类型 (瞬时)
    RETRYABLE_ERRORS = ("timeout", "429", "503", "connection", "ratelimit")

    def __init__(self, fallback_order: list[str] | None = None):
        self.fallback_order = fallback_order or ["deepseek_web", "deepseek_api", "zhipu"]
        self._retry_delays = [0.1, 0.2, 0.4]  # seconds

    async def execute(
        self,
        executors: dict[str, Callable[..., Awaitable[tuple[T, str, str]]]],
        primary_executor: str,
        *args,
        fallback_order: list[str] | None = None,
        **kwargs,
    ) -> FallbackResult:
        """沿降级链依次执行, 直到成功或耗尽.

        每个 executor 遇到瞬时错误时重试 (指数退避).
        """
        order = fallback_order or self.fallback_order
        chain = self._build_chain(primary_executor, order)
        result = FallbackResult(success=False)

        for executor_name in chain:
            executor_fn = executors.get(executor_name)
            if not executor_fn:
                result.errors.append({
                    "executor": executor_name,
                    "error_type": "not_found",
                    "msg": "Executor not registered",
                })
                continue

            # 尝试当前 executor (带重试)
            for attempt, delay in enumerate([0] + self._retry_delays):
                if attempt > 0:
                    await asyncio.sleep(delay)

                try:
                    value, model = await executor_fn(*args, executor_name=executor_name, **kwargs)
                    result.success = True
                    result.value = value
                    result.used_executor = executor_name
                    result.used_model = model
                    return result
                except Exception as e:
                    error_type = self._classify_error(e)
                    result.errors.append({
                        "executor": executor_name,
                        "error_type": error_type,
                        "msg": str(e),
                        "attempt": attempt + 1,
                    })

                    # 非可重试错误 → 立即切下一 executor
                    if error_type not in self.RETRYABLE_ERRORS:
                        break

        result.success = False
        return result

    def _build_chain(self, primary: str, order: list[str]) -> list[str]:
        """构建执行链: primary → fallback_order (去重)."""
        chain = [primary]
        for e in order:
            if e != primary and e not in chain:
                chain.append(e)
        return chain

    @staticmethod
    def _classify_error(error: Exception) -> str:
        """将异常分类为可重试类型字符串."""
        retryable = ("timeout", "429", "503", "connection", "ratelimit")
        msg = str(error).lower()

        if "timeout" in msg:
            return "timeout"
        if "429" in msg or "ratelimit" in msg or "rate limit" in msg:
            return "ratelimit"
        if "503" in msg or "502" in msg:
            return "503"
        if "connection" in msg or "network" in msg or "econnrefused" in msg:
            return "connection"
        if "auth" in msg or "401" in msg or "403" in msg:
            return "auth"
        if "empty" in msg or "no response" in msg:
            return "empty_response"

        # Fallback: 检查异常类名
        cls = type(error).__name__.lower()
        for keyword in retryable:
            if keyword in cls:
                return keyword

        return "unknown"
