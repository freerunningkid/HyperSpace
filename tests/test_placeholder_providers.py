"""Placeholder Provider 测试 —— ChatGLM Web / Qwen Chat Web 占位 provider 行为。

纯单元测试，不涉及网络。
"""

import asyncio

import pytest

from hyperspace.providers.base import ProviderNotImplemented, ProviderRequest, ProviderStatus, ProviderType
from hyperspace.providers.chatglm_web import ChatGLMWebPlaceholderProvider
from hyperspace.providers.qwen_chat_web import QwenChatWebPlaceholderProvider


class TestChatGLMWebPlaceholder:
    """ChatGLM Web 占位 provider。"""

    def test_health_is_not_implemented(self):
        p = ChatGLMWebPlaceholderProvider()
        health = asyncio.run(p.health_check())
        assert health.status == ProviderStatus.NOT_IMPLEMENTED
        assert health.score < 50
        assert "not_implemented" in health.last_error.lower() or "not implemented" in health.message.lower()

    def test_chat_raises_not_implemented(self):
        p = ChatGLMWebPlaceholderProvider()
        with pytest.raises(ProviderNotImplemented):
            asyncio.run(p.chat(ProviderRequest(prompt="hello", provider_id="chatglm_web")))

    def test_type_is_placeholder_web(self):
        p = ChatGLMWebPlaceholderProvider()
        assert p.type == ProviderType.PLACEHOLDER_WEB

    def test_id_is_correct(self):
        p = ChatGLMWebPlaceholderProvider()
        assert p.id == "chatglm_web"

    def test_upload_file_raises_not_implemented(self):
        p = ChatGLMWebPlaceholderProvider()
        with pytest.raises(ProviderNotImplemented):
            asyncio.run(p.upload_file(ProviderRequest(prompt="test", provider_id="chatglm_web")))


class TestQwenChatWebPlaceholder:
    """Qwen Chat Web 占位 provider。"""

    def test_health_is_not_implemented(self):
        p = QwenChatWebPlaceholderProvider()
        health = asyncio.run(p.health_check())
        assert health.status == ProviderStatus.NOT_IMPLEMENTED
        assert health.score < 50

    def test_chat_raises_not_implemented(self):
        p = QwenChatWebPlaceholderProvider()
        with pytest.raises(ProviderNotImplemented):
            asyncio.run(p.chat(ProviderRequest(prompt="hello", provider_id="qwen_chat_web")))

    def test_type_is_placeholder_web(self):
        p = QwenChatWebPlaceholderProvider()
        assert p.type == ProviderType.PLACEHOLDER_WEB

    def test_id_is_correct(self):
        p = QwenChatWebPlaceholderProvider()
        assert p.id == "qwen_chat_web"
