"""OpenAI 兼容 Provider —— 单一实现服务 zhipu/deepseek/kimi/openrouter.

核查依据: 智谱官方文档明确「完全兼容 OpenAI 所有 Endpoint, 仅换 base_url/api_key」;
DeepSeek / Kimi(moonshot) / OpenRouter 同为标准 OpenAI 协议. 故此处不分四份代码,
用一个 OpenAICompatProvider + 不同 ProviderCandidate 配置即可.

异常分类是稳健性的关键 —— 把 OpenAI SDK 的各类错误映射到我们的回退决策类型:
  限流(429) → RateLimitError
  网络/超时 → TransientError / ProviderTimeout
  鉴权(401/403) → AuthError
  其它 APIStatusError → ProviderError
执行器据此决定跳过/升档.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from ..config import ProviderCandidate
from .base import (
    AuthError,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    RateLimitError,
    TransientError,
)

# 单次调用默认超时 (秒). 免费档有时较慢, 留足余量
DEFAULT_TIMEOUT = 60.0


class OpenAICompatProvider:
    """对任意 OpenAI 兼容端点的异步调用封装.

    无状态: 每个 ProviderCandidate 配一个实例即可; key 从 candidate.api_key 取.
    """

    def __init__(self, candidate: ProviderCandidate, timeout: float = DEFAULT_TIMEOUT):
        if not candidate.api_key:
            raise ProviderError(f"[{candidate.provider}] 缺少 key ({candidate.key_env})")
        self.candidate = candidate
        self._client = AsyncOpenAI(
            api_key=candidate.api_key,
            base_url=candidate.base_url,
            timeout=timeout,
        )

    async def chat(
        self,
        prompt: str,
        images: list[str] | None = None,
        context: str | None = None,
    ) -> ProviderResponse:
        """发一次 chat completion, 返回标准化结果.

        images: 元素可为本地路径或 data:image/...;... base64 或 http(s) URL.
                本地路径会读文件并转 base64 (智谱 GLM-4V 支持 data url).
        context: 作为 system message 前置 (可选).
        """
        messages: list[dict] = []
        if context:
            messages.append({"role": "system", "content": context})

        if images:
            # 多模态: content 为 [text, image_url, ...]
            content: list[dict] = [{"type": "text", "text": prompt}]
            for img in images:
                content.append({"type": "image_url", "image_url": {"url": self._normalize_image(img)}})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        try:
            resp = await self._client.chat.completions.create(
                model=self.candidate.model,
                messages=messages,
            )
        except APITimeoutError as e:
            raise ProviderTimeout(f"[{self.candidate.provider}] 请求超时: {e}") from e
        except APIConnectionError as e:
            raise TransientError(f"[{self.candidate.provider}] 网络错误: {e}") from e
        except APIStatusError as e:
            # 按 HTTP 状态码分类
            status = e.status_code if hasattr(e, "status_code") else None
            if status == 429:
                raise RateLimitError(f"[{self.candidate.provider}] 限流 (429)") from e
            if status in (401, 403):
                raise AuthError(f"[{self.candidate.provider}] 鉴权失败 ({status})") from e
            if status and 500 <= status < 600:
                raise TransientError(f"[{self.candidate.provider}] 服务端错误 ({status})") from e
            raise ProviderError(f"[{self.candidate.provider}] API 错误 ({status}): {e}") from e
        except Exception as e:
            # asyncio 超时等
            if isinstance(e, asyncio.TimeoutError):
                raise ProviderTimeout(f"[{self.candidate.provider}] asyncio 超时") from e
            raise ProviderError(f"[{self.candidate.provider}] 未知错误: {e}") from e

        text = ""
        if resp.choices:
            text = (resp.choices[0].message.content or "").strip()
        usage = resp.usage
        return ProviderResponse(
            text=text,
            provider=self.candidate.provider,
            model=self.candidate.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    @staticmethod
    def _normalize_image(img: str) -> str:
        """把本地路径转 data URL; 已是 url/data url 则原样返回."""
        if img.startswith(("http://", "https://", "data:")):
            return img
        # 视为本地路径
        path = Path(img)
        if not path.exists():
            # 不是 url 也不是文件 —— 当作 base64 原文, 包成 data url 兜底
            return f"data:image/jpeg;base64,{img}"
        # 推断 mime
        suffix = path.suffix.lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(suffix, "jpeg")
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/{mime};base64,{b64}"
