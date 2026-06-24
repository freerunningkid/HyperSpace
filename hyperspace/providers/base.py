"""Provider 协议、标准响应与错误类型.

本文件同时兼容旧路由：
- 旧 `ProviderResponse(text, provider, model, prompt_tokens, completion_tokens)` 继续可用。
- 新 Provider contract 增加 `answer/provider_id/provider_type/raw_metadata/fallback_*`。
- 旧错误别名 `TransientError/ProviderTimeout/RateLimitError/AuthError` 继续导出，避免破坏现有执行器。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderType(str, Enum):
    WEB = "web"
    API = "api"
    PLACEHOLDER_WEB = "placeholder_web"


class ProviderStatus(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_IMPLEMENTED = "not_implemented"
    DISABLED = "disabled"


class CostTier(str, Enum):
    FREE = "free"
    LOW_COST = "low_cost"
    PAID = "paid"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class ProviderCapabilities:
    """声明 provider 可承担的任务能力。"""

    text: bool = True
    vision_understanding: bool = False
    image_generation: bool = False
    video_understanding: bool = False
    video_generation: bool = False
    file_upload: bool = False
    web_search: bool = False
    streaming: bool = False
    structured_output: bool = False
    planning: bool = True
    long_context: bool = False
    tool_calling: bool = False


@dataclass(slots=True)
class ProviderHealth:
    """Provider 健康状态，供 Registry/Router 做健康感知排序。"""

    status: ProviderStatus
    score: float
    last_checked_at: str | None = None
    last_error: str | None = None
    latency_ms: float | None = None
    success_rate: float | None = None
    message: str = ""


@dataclass(slots=True)
class ProviderRequest:
    """Provider 统一请求结构。"""

    prompt: str
    provider_id: str
    mode: str | None = None
    web_mode: str | None = None
    search_enabled: bool = False
    session_id: str | None = None
    files: list[str] | None = None
    images: list[str] | None = None
    expected_output: str = "answer"
    routing_strategy: str = "auto"
    context: str | None = None


@dataclass
class ProviderResponse:
    """Provider 标准化响应。

    新字段用于多 Provider Router：
    - answer: 标准化回答文本
    - provider_id/provider_type: 实际命中的 provider
    - raw_metadata/fallback_*: 调度诊断信息

    旧字段用于 legacy executor/cost 链路：
    - text: 同 answer
    - provider/model: 实际 provider/model
    - prompt_tokens/completion_tokens: usage 统计
    """

    answer: str = ""
    provider_id: str = ""
    provider_type: ProviderType | None = None
    model: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    error: str | None = None

    text: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __init__(
        self,
        answer: str = "",
        provider_id: str = "",
        provider_type: ProviderType | None = None,
        model: str | None = None,
        raw_metadata: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        fallback_used: bool = False,
        fallback_reason: str | None = None,
        error: str | None = None,
        text: str | None = None,
        provider: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ):
        self.answer = answer or text or ""
        self.provider_id = provider_id or provider or ""
        self.provider_type = provider_type
        self.model = model
        self.raw_metadata = raw_metadata or {}
        self.usage = usage
        self.fallback_used = fallback_used
        self.fallback_reason = fallback_reason
        self.error = error

        # Legacy 兼容字段：旧 executor/cost 仍按这些字段读取。
        self.text = text if text is not None else self.answer
        self.provider = provider or self.provider_id
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class BaseProvider:
    """所有 provider 必须实现的统一接口。"""

    id: str
    type: ProviderType
    capabilities: ProviderCapabilities
    cost_tier: CostTier

    async def health_check(self) -> ProviderHealth:
        raise NotImplementedError

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError

    async def upload_file(self, request: ProviderRequest) -> Any:
        raise NotImplementedError

    async def close_session(self, session_id: str) -> None:
        return None


class ProviderError(Exception):
    """Provider 调用失败基类。"""

    retryable: bool = False
    fallback: bool = True


class TransientError(ProviderError):
    """瞬时错误，适合重试或 fallback。"""

    retryable = True
    fallback = True


class ProviderTimeout(TransientError):
    """请求超时。"""


class RateLimitError(ProviderError):
    """限流错误，适合 fallback。"""

    retryable = True
    fallback = True


class AuthError(ProviderError):
    """鉴权失败。"""

    retryable = False
    fallback = True


class ProviderUnavailable(ProviderError):
    retryable = False
    fallback = True


class ProviderNotImplemented(ProviderError):
    retryable = False
    fallback = True


class FileUploadError(ProviderError):
    retryable = False
    fallback = True


class StructuredOutputError(ProviderError):
    retryable = False
    fallback = True


class UpstreamError(ProviderError):
    retryable = True
    fallback = True


class ValidationError(ProviderError):
    retryable = False
    fallback = False
