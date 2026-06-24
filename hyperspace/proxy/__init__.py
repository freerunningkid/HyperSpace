"""HyperSpace 代理模式 —— 多模型 API 网关.

让 Claude Code 通过 /model 无缝切换不同厂商的大模型。
启动: python -m hyperspace.proxy_server
"""

from .converters import (
    anthropic_to_openai_request,
    openai_to_anthropic_response,
    OpenAIStreamConverter,
    passthrough_stream,
)

__all__ = [
    "anthropic_to_openai_request",
    "openai_to_anthropic_response",
    "OpenAIStreamConverter",
    "passthrough_stream",
]
