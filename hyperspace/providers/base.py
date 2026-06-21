"""Provider 协议与错误类型.

所有 provider 实现统一异步接口 chat(), 返回 ProviderResponse.
异常分两类, 供执行器决策回退:
  TransientError / RateLimitError  → 可跳下一候选 / 升档
  ProviderError (其它)              → 同样跳过, 但日志标记为非瞬时
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderResponse:
    """provider 调用的标准化结果."""

    text: str               # 模型回答
    provider: str           # 实际命中的 provider (zhipu/deepseek/...)
    model: str              # 实际命中的模型
    prompt_tokens: int = 0  # usage (用于成本追踪, 缺省 0)
    completion_tokens: int = 0


class ProviderError(Exception):
    """provider 调用失败的基类. 被执行器捕获以触发回退."""


class TransientError(ProviderError):
    """瞬时错误 (网络/超时) —— 适合回退."""


class ProviderTimeout(TransientError):
    """请求超时."""


class RateLimitError(ProviderError):
    """限流 (429 等) —— 适合回退到下一候选/升档."""


class AuthError(ProviderError):
    """鉴权失败 (401 等) —— 通常 key 配置错误."""
