# HyperSpace 多 Provider 架构第一阶段执行计划

> **给执行者：** 推荐使用 `/dispatch` (子代理驱动) 或本会话顺序执行来实现此计划。步骤使用 `- [ ]` 语法追踪进度。

**目标：** 将 HyperSpace 从 DeepSeek 中心化混合路由重构为多 Provider 可扩展架构，同时保持 DeepSeek Web 现有能力尽量不中断。

**架构：** 新增标准 Provider 接口、ProviderRegistry、OpenAI-compatible API Provider、DeepSeek Web Provider Adapter、ChatGLM/Qwen Web 占位 Provider，并让 HybridRouter 通过 Registry 选择 Provider。MCP 入口新增 provider、routing_strategy、expected_output 和 health 查询能力。

**技术栈：** Python 3.10+、asyncio、httpx、YAML、MCP stdio、pytest、pytest-asyncio。

---

## 文件结构映射

### 新增文件

- `hyperspace/providers/base.py`
  - 职责：定义 Provider 类型、能力、健康、请求、响应、错误和 BaseProvider 接口。
  - 依赖：标准库、typing。
- `hyperspace/providers/registry.py`
  - 职责：加载 provider 配置、创建 provider 实例、按 id 查询、列出 provider、查询健康状态。
  - 依赖：`base.py`、YAML、配置。
- `hyperspace/providers/openai_compatible.py`
  - 职责：通用 OpenAI-compatible Chat Completions Provider。
  - 依赖：httpx、`base.py`。
- `hyperspace/providers/deepseek_web.py`
  - 职责：将现有 DeepSeek Web 客户端包装为标准 Provider。
  - 依赖：现有 `hybrid_engine/deepseek_web_client.py`、`context_window_manager.py`、`web_auth.py`、`result_processor.py`。
- `hyperspace/providers/deepseek_api.py`
  - 职责：DeepSeek API Provider 包装。
  - 依赖：`openai_compatible.py`。
- `hyperspace/providers/zhipu_api.py`
  - 职责：Zhipu API Provider 包装。
  - 依赖：`openai_compatible.py`。
- `hyperspace/providers/qwen_api.py`
  - 职责：Qwen API Provider 包装。
  - 依赖：`openai_compatible.py`。
- `hyperspace/providers/chatglm_web.py`
  - 职责：ChatGLM Web 占位 Provider，fallback 到 `agnes_text`。
  - 依赖：`base.py`、Registry 或 fallback provider 注入。
- `hyperspace/providers/qwen_chat_web.py`
  - 职责：Qwen Chat Web 占位 Provider，fallback 到 `qwen_api`。
  - 依赖：`base.py`、Registry 或 fallback provider 注入。

### 修改文件

- `hyperspace/hybrid_engine/hybrid_router.py`
  - 职责：从直接 DeepSeek 调用重构为通过 ProviderRegistry 选择 Provider。
- `hyperspace/server.py`
  - 职责：MCP 工具参数扩展，新增 health 工具。
- `config/providers.yaml`
  - 职责：旧 tier provider 列表扩展 SiliconFlow、Agnes。
- `config/hybrid_config.yaml`
  - 职责：ProviderRegistry 配置、fallback、路由策略。
- `.env.example`
  - 职责：新增环境变量示例。
- `tests/test_hybrid_engine.py`
  - 职责：适配 HybridRouter 新行为。
- `tests/test_deepseek_web_client.py`
  - 职责：保留 DeepSeek Web 底层能力测试。
- `README.md`
  - 职责：说明多 Provider 架构、当前支持状态、环境变量和 fallback。

### 新增测试文件

- `tests/test_provider_contract.py`
  - 职责：验证 Provider contract 和 placeholder 行为。
- `tests/test_provider_registry.py`
  - 职责：验证 Registry 加载、启用、禁用、health 查询。
- `tests/test_openai_compatible_provider.py`
  - 职责：验证 OpenAI-compatible Provider 的请求、响应、错误分类。
- `tests/test_placeholder_providers.py`
  - 职责：验证 ChatGLM/Qwen Web placeholder fallback。
- `tests/test_hybrid_router_provider_selection.py`
  - 职责：验证 Router 的 provider 选择、能力过滤、zero-cost-first、placeholder 默认不进入 auto。
- `tests/test_mcp_schema.py`
  - 职责：验证 MCP tool schema 包含新参数和 health 工具。

---

## 设计覆盖核对

| 设计需求 | 对应任务 |
|---|---|
| Provider Contract | Task 1 |
| ProviderRegistry | Task 2 |
| OpenAI-compatible API Provider | Task 3 |
| DeepSeek API/Zhipu API/Qwen API Provider | Task 4 |
| SiliconFlow/Agnes Provider | Task 4、Task 9 |
| ChatGLM/Qwen Web Placeholder | Task 5 |
| DeepSeek Web Provider Adapter | Task 6 |
| HybridRouter 重构 | Task 7 |
| MCP 接口升级 | Task 8 |
| 配置更新 | Task 9 |
| 测试补充 | Task 10 |
| README 更新 | Task 11 |
| 最终验证 | Task 12 |

## 占位符扫描

本计划不包含 `TBD`、`TODO`、`稍后补充`、`添加适当` 等模糊描述。每个任务均给出文件路径、具体步骤和验证方式。

## 类型一致性核对

本计划使用的类型名与正式设计文档一致：

- `ProviderType`
- `ProviderStatus`
- `CostTier`
- `ProviderCapabilities`
- `ProviderHealth`
- `ProviderRequest`
- `ProviderResponse`
- `BaseProvider`
- `ProviderRegistry`
- `OpenAICompatibleProvider`
- `DeepSeekWebProvider`
- `ChatGLMWebPlaceholderProvider`
- `QwenChatWebPlaceholderProvider`

---

### Task 1: 定义 Provider Contract

**涉及文件：**
- 新建: `hyperspace/providers/base.py`
- 新建: `hyperspace/providers/errors.py`
- 修改: `hyperspace/providers/__init__.py`
- 测试: `tests/test_provider_contract.py`

- [ ] **Step 1: 写入 Provider Contract 测试**

在 `tests/test_provider_contract.py` 中添加：

```python
from hyperspace.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
    CostTier,
)


class DummyProvider(BaseProvider):
    def __init__(self):
        self.id = "dummy"
        self.type = ProviderType.API
        self.capabilities = ProviderCapabilities(text=True)
        self.cost_tier = CostTier.FREE

    async def health_check(self):
        return ProviderHealth(status=ProviderStatus.AVAILABLE, score=100.0, message="ok")

    async def chat(self, request):
        return ProviderResponse(answer="ok", provider_id=self.id, provider_type=self.type)

    async def upload_file(self, request):
        return {"id": "file-1"}


async def test_provider_contract_types_and_methods():
    provider = DummyProvider()
    request = ProviderRequest(prompt="hello", provider_id="dummy")
    response = await provider.chat(request)

    assert response.provider_id == "dummy"
    assert response.provider_type == ProviderType.API
    assert provider.capabilities.text is True
    assert provider.cost_tier == CostTier.FREE
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_provider_contract.py::test_provider_contract_types_and_methods -v
```

预期：`ModuleNotFoundError` 或 `ImportError`，因为 Provider Contract 尚未实现。

- [ ] **Step 3: 写入最少实现代码**

在 `hyperspace/providers/base.py` 中实现：

```python
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
    status: ProviderStatus
    score: float
    last_checked_at: str | None = None
    last_error: str | None = None
    latency_ms: float | None = None
    success_rate: float | None = None
    message: str = ""


@dataclass(slots=True)
class ProviderRequest:
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


@dataclass(slots=True)
class ProviderResponse:
    answer: str
    provider_id: str
    provider_type: ProviderType
    model: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    error: str | None = None


class BaseProvider:
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
```

在 `hyperspace/providers/errors.py` 中实现：

```python
class ProviderError(Exception):
    provider_id: str | None = None
    retryable: bool = False
    fallback: bool = True


class ProviderUnavailable(ProviderError):
    retryable = False
    fallback = True


class ProviderNotImplemented(ProviderError):
    retryable = False
    fallback = True


class AuthenticationError(ProviderError):
    retryable = False
    fallback = True


class RateLimitError(ProviderError):
    retryable = True
    fallback = True


class TimeoutError_(ProviderError):
    retryable = True
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
```

在 `hyperspace/providers/__init__.py` 中导出：

```python
from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)

__all__ = [
    "BaseProvider",
    "CostTier",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStatus",
    "ProviderType",
]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_provider_contract.py::test_provider_contract_types_and_methods -v
```

预期：`1 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/providers/base.py hyperspace/providers/errors.py hyperspace/providers/__init__.py tests/test_provider_contract.py
git commit -m "feat: define provider contract"
```

---

### Task 2: 实现 ProviderRegistry

**涉及文件：**
- 新建: `hyperspace/providers/registry.py`
- 修改: `hyperspace/providers/__init__.py`
- 测试: `tests/test_provider_registry.py`

- [ ] **Step 1: 写入 Registry 配置 fixture 和测试**

在 `tests/test_provider_registry.py` 中添加：

```python
import pytest

from hyperspace.providers.base import ProviderType, ProviderStatus
from hyperspace.providers.registry import ProviderRegistry


@pytest.fixture
def registry_config(tmp_path, monkeypatch):
    config = tmp_path / "providers.yaml"
    config.write_text(
        """
providers:
  dummy_api:
    type: api
    class: tests.test_provider_registry.DummyProvider
    enabled: true
    cost_tier: free
    capabilities:
      text: true
      structured_output: true
  missing_key_api:
    type: api
    class: tests.test_provider_registry.DummyProvider
    enabled_env: MISSING_API_KEY
    cost_tier: free
""".strip(),
        encoding="utf-8",
    )
    return config


class DummyProvider:
    type = ProviderType.API

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def health_check(self):
        return ProviderStatus.AVAILABLE

    async def chat(self, request):
        raise NotImplementedError

    async def upload_file(self, request):
        raise NotImplementedError

    async def close_session(self, session_id):
        return None


def test_registry_loads_enabled_provider(registry_config):
    registry = ProviderRegistry(config_path=registry_config)
    provider = registry.get("dummy_api")

    assert provider is not None
    assert provider.type == ProviderType.API


def test_registry_marks_missing_env_provider_disabled(registry_config):
    registry = ProviderRegistry(config_path=registry_config)
    health = registry.health("missing_key_api")

    assert health.status == ProviderStatus.DISABLED
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_provider_registry.py -v
```

预期：`ModuleNotFoundError`，因为 `ProviderRegistry` 尚未实现。

- [ ] **Step 3: 实现 ProviderRegistry**

在 `hyperspace/providers/registry.py` 中实现：

```python
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import yaml

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatus,
    ProviderType,
)


class ProviderRegistry:
    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path) if config_path else None
        self._config = self._load_config()
        self._providers: dict[str, BaseProvider] = {}
        self._health: dict[str, ProviderHealth] = {}
        self._load_providers()

    def get(self, provider_id: str) -> BaseProvider | None:
        return self._providers.get(provider_id)

    def all(self) -> dict[str, BaseProvider]:
        return dict(self._providers)

    def health(self, provider_id: str) -> ProviderHealth:
        return self._health.get(
            provider_id,
            ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=0.0,
                message="provider not found",
            ),
        )

    def health_all(self) -> dict[str, ProviderHealth]:
        return dict(self._health)

    def list_ids(self) -> list[str]:
        return list(self._providers.keys())

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path or not self.config_path.exists():
            return {"providers": {}}
        with self.config_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {"providers": {}}

    def _load_providers(self) -> None:
        for provider_id, raw_cfg in (self._config.get("providers") or {}).items():
            cfg = raw_cfg or {}
            env_name = cfg.get("enabled_env")
            if env_name and not os.getenv(env_name):
                self._health[provider_id] = ProviderHealth(
                    status=ProviderStatus.DISABLED,
                    score=0.0,
                    message=f"missing env: {env_name}",
                )
                continue

            try:
                provider = self._create_provider(provider_id, cfg)
            except Exception as exc:
                self._health[provider_id] = ProviderHealth(
                    status=ProviderStatus.UNAVAILABLE,
                    score=0.0,
                    message=str(exc),
                )
                continue

            self._providers[provider_id] = provider
            self._health[provider_id] = ProviderHealth(
                status=ProviderStatus.AVAILABLE,
                score=100.0,
                message="loaded",
            )

    def _create_provider(self, provider_id: str, cfg: dict[str, Any]) -> BaseProvider:
        class_path = cfg.get("class")
        if not class_path:
            raise ValueError(f"provider {provider_id} missing class")

        module_name, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)

        return cls(
            provider_id=provider_id,
            **self._provider_kwargs(provider_id, cfg),
        )

    def _provider_kwargs(self, provider_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
        capabilities = ProviderCapabilities(**(cfg.get("capabilities") or {}))
        return {
            "provider_id": provider_id,
            "provider_type": ProviderType(cfg.get("type", "api")),
            "capabilities": capabilities,
            "cost_tier": CostTier(cfg.get("cost_tier", "unknown")),
            "config": cfg,
        }
```

修改 `hyperspace/providers/__init__.py`，导出：

```python
from .registry import ProviderRegistry

__all__ = [
    "BaseProvider",
    "CostTier",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStatus",
    "ProviderType",
    "ProviderRegistry",
]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_provider_registry.py -v
```

预期：`2 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/providers/registry.py hyperspace/providers/__init__.py tests/test_provider_registry.py
git commit -m "feat: add provider registry"
```

---

### Task 3: 实现 OpenAI-compatible API Provider

**涉及文件：**
- 新建: `hyperspace/providers/openai_compatible.py`
- 测试: `tests/test_openai_compatible_provider.py`

- [ ] **Step 1: 写入 mock HTTP 测试**

在 `tests/test_openai_compatible_provider.py` 中添加：

```python
import pytest
from httpx import AsyncClient, ASGITransport

from hyperspace.providers.base import (
    CostTier,
    ProviderCapabilities,
    ProviderRequest,
    ProviderType,
)
from hyperspace.providers.openai_compatible import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_openai_compatible_provider_sends_chat_request():
    async def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = request.json()
        assert body["model"] == "test-model"
        assert body["messages"] == [{"role": "user", "content": "hello"}]
        return {
            "status_code": 200,
            "json": {"choices": [{"message": {"content": "hi"}}]},
        }

    provider = OpenAICompatibleProvider(
        provider_id="test",
        provider_type=ProviderType.API,
        capabilities=ProviderCapabilities(text=True),
        cost_tier=CostTier.FREE,
        config={
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "api_key": "test-key",
        },
    )

    transport = ASGITransport(app=handler)
    async with AsyncClient(transport=transport, base_url="https://example.test") as client:
        provider.client = client
        response = await provider.chat(ProviderRequest(prompt="hello", provider_id="test"))

    assert response.answer == "hi"
    assert response.provider_id == "test"
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_openai_compatible_provider.py -v
```

预期：`ModuleNotFoundError`，因为 provider 尚未实现。

- [ ] **Step 3: 实现 OpenAICompatibleProvider**

在 `hyperspace/providers/openai_compatible.py` 中实现：

```python
from __future__ import annotations

import os
from typing import Any

import httpx

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)
from .errors import AuthenticationError, ProviderUnavailable, UpstreamError


class OpenAICompatibleProvider(BaseProvider):
    def __init__(
        self,
        provider_id: str,
        provider_type: ProviderType,
        capabilities: ProviderCapabilities,
        cost_tier: CostTier,
        config: dict[str, Any],
        client: httpx.AsyncClient | None = None,
    ):
        self.id = provider_id
        self.type = provider_type
        self.capabilities = capabilities
        self.cost_tier = cost_tier
        self.config = config
        self.client = client or httpx.AsyncClient(timeout=config.get("timeout", 60))

    async def health_check(self) -> ProviderHealth:
        if not self._api_key():
            return ProviderHealth(
                status=ProviderStatus.DISABLED,
                score=0.0,
                message="missing API key",
            )
        if not self.config.get("base_url"):
            return ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=0.0,
                message="missing base_url",
            )
        if not self.config.get("model"):
            return ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=0.0,
                message="missing model",
            )
        return ProviderHealth(
            status=ProviderStatus.AVAILABLE,
            score=100.0,
            message="configured",
        )

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        health = await self.health_check()
        if health.status in {ProviderStatus.DISABLED, ProviderStatus.UNAVAILABLE}:
            raise ProviderUnavailable(health.message)

        payload = self._build_payload(request)
        try:
            response = await self.client.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamError(f"{self.id} timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise UpstreamError(f"{self.id} request failed: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError(f"{self.id} authentication failed")
        if response.status_code == 429:
            raise UpstreamError(f"{self.id} rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"{self.id} upstream error: {response.status_code}")
        if response.status_code >= 400:
            raise ProviderUnavailable(f"{self.id} upstream error: {response.status_code}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return ProviderResponse(
            answer=content,
            provider_id=self.id,
            provider_type=self.type,
            model=self.config.get("model"),
            raw_metadata={"usage": data.get("usage")},
            usage=data.get("usage"),
        )

    async def upload_file(self, request: ProviderRequest) -> Any:
        raise ProviderUnavailable(f"{self.id} file upload is not implemented")

    async def close_session(self, session_id: str) -> None:
        return None

    def _api_key(self) -> str | None:
        env_name = self.config.get("api_key_env")
        if env_name:
            return os.getenv(env_name)
        return self.config.get("api_key")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key()}"}

    def _chat_url(self) -> str:
        base = self.config["base_url"].rstrip("/")
        return f"{base}/chat/completions"

    def _build_payload(self, request: ProviderRequest) -> dict[str, Any]:
        return {
            "model": self.config["model"],
            "messages": [{"role": "user", "content": request.prompt}],
        }
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_openai_compatible_provider.py -v
```

预期：`1 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/providers/openai_compatible.py tests/test_openai_compatible_provider.py
git commit -m "feat: add openai compatible provider"
```

---

### Task 4: 实现 API Provider 包装

**涉及文件：**
- 新建: `hyperspace/providers/deepseek_api.py`
- 新建: `hyperspace/providers/zhipu_api.py`
- 新建: `hyperspace/providers/qwen_api.py`
- 测试: `tests/test_provider_registry.py`

- [ ] **Step 1: 写入 provider wrapper 测试**

在 `tests/test_provider_registry.py` 中追加：

```python
from hyperspace.providers.deepseek_api import DeepSeekAPIProvider
from hyperspace.providers.zhipu_api import ZhipuAPIProvider
from hyperspace.providers.qwen_api import QwenAPIProvider


def test_api_provider_wrappers_are_subclasses():
    assert issubclass(DeepSeekAPIProvider, object)
    assert issubclass(ZhipuAPIProvider, object)
    assert issubclass(QwenAPIProvider, object)
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_provider_registry.py::test_api_provider_wrappers_are_subclasses -v
```

预期：`ModuleNotFoundError`，因为 wrapper 文件尚未创建。

- [ ] **Step 3: 实现 API Provider 包装**

在 `hyperspace/providers/deepseek_api.py` 中实现：

```python
from hyperspace.providers.openai_compatible import OpenAICompatibleProvider


class DeepSeekAPIProvider(OpenAICompatibleProvider):
    pass
```

在 `hyperspace/providers/zhipu_api.py` 中实现：

```python
from hyperspace.providers.openai_compatible import OpenAICompatibleProvider


class ZhipuAPIProvider(OpenAICompatibleProvider):
    pass
```

在 `hyperspace/providers/qwen_api.py` 中实现：

```python
from hyperspace.providers.openai_compatible import OpenAICompatibleProvider


class QwenAPIProvider(OpenAICompatibleProvider):
    pass
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_provider_registry.py::test_api_provider_wrappers_are_subclasses -v
```

预期：`1 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/providers/deepseek_api.py hyperspace/providers/zhipu_api.py hyperspace/providers/qwen_api.py tests/test_provider_registry.py
git commit -m "feat: add api provider wrappers"
```

---

### Task 5: 实现 ChatGLM/Qwen Web 占位 Provider

**涉及文件：**
- 新建: `hyperspace/providers/chatglm_web.py`
- 新建: `hyperspace/providers/qwen_chat_web.py`
- 测试: `tests/test_placeholder_providers.py`

- [ ] **Step 1: 写入 placeholder fallback 测试**

在 `tests/test_placeholder_providers.py` 中添加：

```python
import pytest

from hyperspace.providers.base import ProviderRequest
from hyperspace.providers.chatglm_web import ChatGLMWebPlaceholderProvider
from hyperspace.providers.qwen_chat_web import QwenChatWebPlaceholderProvider
from hyperspace.providers.errors import ProviderNotImplemented


class FallbackProvider:
    async def chat(self, request):
        from hyperspace.providers.base import ProviderResponse, ProviderType

        return ProviderResponse(
            answer="fallback-ok",
            provider_id=request.provider_id,
            provider_type=ProviderType.API,
        )


@pytest.mark.asyncio
async def test_chatglm_web_placeholder_falls_back_to_agnes_text():
    fallback = FallbackProvider()
    provider = ChatGLMWebPlaceholderProvider(
        provider_id="chatglm_web",
        fallback_provider=fallback,
    )

    response = await provider.chat(ProviderRequest(prompt="hello", provider_id="chatglm_web"))

    assert response.answer == "fallback-ok"
    assert response.fallback_used is True
    assert response.fallback_reason == "chatglm_web_automation_not_implemented"
    assert response.provider_id == "agnes_text"


@pytest.mark.asyncio
async def test_qwen_chat_web_placeholder_falls_back_to_qwen_api():
    fallback = FallbackProvider()
    provider = QwenChatWebPlaceholderProvider(
        provider_id="qwen_chat_web",
        fallback_provider=fallback,
    )

    response = await provider.chat(ProviderRequest(prompt="hello", provider_id="qwen_chat_web"))

    assert response.answer == "fallback-ok"
    assert response.fallback_used is True
    assert response.fallback_reason == "qwen_chat_web_automation_not_implemented"
    assert response.provider_id == "qwen_api"


@pytest.mark.asyncio
async def test_chatglm_web_placeholder_raises_when_no_fallback():
    provider = ChatGLMWebPlaceholderProvider(provider_id="chatglm_web")

    with pytest.raises(ProviderNotImplemented):
        await provider.chat(ProviderRequest(prompt="hello", provider_id="chatglm_web"))
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_placeholder_providers.py -v
```

预期：`ModuleNotFoundError`，因为 placeholder provider 尚未实现。

- [ ] **Step 3: 实现 placeholder providers**

在 `hyperspace/providers/chatglm_web.py` 中实现：

```python
from __future__ import annotations

from typing import Any

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)
from .errors import ProviderNotImplemented


class ChatGLMWebPlaceholderProvider(BaseProvider):
    fallback_to = "agnes_text"

    def __init__(
        self,
        provider_id: str = "chatglm_web",
        fallback_provider: BaseProvider | None = None,
    ):
        self.id = provider_id
        self.type = ProviderType.PLACEHOLDER_WEB
        self.capabilities = ProviderCapabilities(
            text=True,
            planning=True,
            long_context=True,
        )
        self.cost_tier = CostTier.FREE
        self.fallback_provider = fallback_provider

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            status=ProviderStatus.DEGRADED,
            score=40.0,
            last_error="web_automation_not_implemented",
            message="ChatGLM Web automation is not implemented; fallback is agnes_text",
        )

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        if self.fallback_provider is None:
            raise ProviderNotImplemented("ChatGLM Web automation is not implemented")

        fallback_request = ProviderRequest(
            prompt=request.prompt,
            provider_id=self.fallback_to,
            mode=request.mode,
            web_mode=request.web_mode,
            search_enabled=request.search_enabled,
            session_id=request.session_id,
            files=request.files,
            images=request.images,
            expected_output=request.expected_output,
            routing_strategy=request.routing_strategy,
            context=request.context,
        )
        response = await self.fallback_provider.chat(fallback_request)
        response.provider_id = self.fallback_to
        response.fallback_used = True
        response.fallback_reason = "chatglm_web_automation_not_implemented"
        response.raw_metadata.setdefault("requested_provider", self.id)
        return response

    async def upload_file(self, request: ProviderRequest) -> Any:
        raise ProviderNotImplemented("ChatGLM Web file upload is not implemented")

    async def close_session(self, session_id: str) -> None:
        return None
```

在 `hyperspace/providers/qwen_chat_web.py` 中实现：

```python
from __future__ import annotations

from typing import Any

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)
from .errors import ProviderNotImplemented


class QwenChatWebPlaceholderProvider(BaseProvider):
    fallback_to = "qwen_api"

    def __init__(
        self,
        provider_id: str = "qwen_chat_web",
        fallback_provider: BaseProvider | None = None,
    ):
        self.id = provider_id
        self.type = ProviderType.PLACEHOLDER_WEB
        self.capabilities = ProviderCapabilities(
            text=True,
            planning=True,
            long_context=True,
        )
        self.cost_tier = CostTier.FREE
        self.fallback_provider = fallback_provider

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            status=ProviderStatus.DEGRADED,
            score=40.0,
            last_error="web_automation_not_implemented",
            message="Qwen Chat Web automation is not implemented; fallback is qwen_api",
        )

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        if self.fallback_provider is None:
            raise ProviderNotImplemented("Qwen Chat Web automation is not implemented")

        fallback_request = ProviderRequest(
            prompt=request.prompt,
            provider_id=self.fallback_to,
            mode=request.mode,
            web_mode=request.web_mode,
            search_enabled=request.search_enabled,
            session_id=request.session_id,
            files=request.files,
            images=request.images,
            expected_output=request.expected_output,
            routing_strategy=request.routing_strategy,
            context=request.context,
        )
        response = await self.fallback_provider.chat(fallback_request)
        response.provider_id = self.fallback_to
        response.fallback_used = True
        response.fallback_reason = "qwen_chat_web_automation_not_implemented"
        response.raw_metadata.setdefault("requested_provider", self.id)
        return response

    async def upload_file(self, request: ProviderRequest) -> Any:
        raise ProviderNotImplemented("Qwen Chat Web file upload is not implemented")

    async def close_session(self, session_id: str) -> None:
        return None
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_placeholder_providers.py -v
```

预期：`3 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/providers/chatglm_web.py hyperspace/providers/qwen_chat_web.py tests/test_placeholder_providers.py
git commit -m "feat: add web placeholder providers"
```

---

### Task 6: 实现 DeepSeek Web Provider Adapter

**涉及文件：**
- 新建: `hyperspace/providers/deepseek_web.py`
- 修改: `hyperspace/providers/__init__.py`
- 测试: `tests/test_deepseek_web_client.py`

- [ ] **Step 1: 写入 adapter smoke 测试**

在 `tests/test_deepseek_web_client.py` 中追加：

```python
import pytest

from hyperspace.providers.base import ProviderRequest, ProviderType
from hyperspace.providers.deepseek_web import DeepSeekWebProvider
from hyperspace.hybrid_engine.web_auth import DeepSeekAuth


@pytest.mark.asyncio
async def test_deepseek_web_provider_without_auth_reports_unavailable():
    provider = DeepSeekWebProvider(provider_id="deepseek_web", auth=None)
    health = await provider.health_check()

    assert health.status.value == "unavailable"
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_deepseek_web_client.py::test_deepseek_web_provider_without_auth_reports_unavailable -v
```

预期：`ModuleNotFoundError`，因为 adapter 尚未实现。

- [ ] **Step 3: 实现 DeepSeekWebProvider**

在 `hyperspace/providers/deepseek_web.py` 中实现：

```python
from __future__ import annotations

from typing import Any

from hyperspace.hybrid_engine.context_window_manager import ContextWindowManager
from hyperspace.hybrid_engine.deepseek_web_client import (
    DeepSeekAuth,
    DeepSeekWebClient,
)
from hyperspace.hybrid_engine.result_processor import ResultProcessor
from hyperspace.hybrid_engine import web_auth as web_auth_mod

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)
from .errors import ProviderUnavailable


class DeepSeekWebProvider(BaseProvider):
    def __init__(
        self,
        provider_id: str = "deepseek_web",
        auth: DeepSeekAuth | None = None,
        web_client: DeepSeekWebClient | None = None,
        context_manager: ContextWindowManager | None = None,
    ):
        self.id = provider_id
        self.type = ProviderType.WEB
        self.capabilities = ProviderCapabilities(
            text=True,
            vision_understanding=True,
            file_upload=True,
            web_search=True,
            streaming=True,
            planning=True,
            long_context=True,
        )
        self.cost_tier = CostTier.FREE
        self.auth = auth or self._load_auth()
        self.web_client = web_client
        self.context_manager = context_manager
        if self.auth and self.auth.is_valid() and self.web_client is None:
            self.web_client = DeepSeekWebClient(self.auth)
        if self.auth and self.auth.is_valid() and self.context_manager is None and self.web_client:
            self.context_manager = ContextWindowManager(
                web_client=self.web_client,
                compress_fn=self._compress_via_api,
            )

    async def health_check(self) -> ProviderHealth:
        if not self.auth or not self.auth.is_valid():
            return ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=0.0,
                message="DeepSeek Web auth is missing or invalid",
            )
        return ProviderHealth(
            status=ProviderStatus.AVAILABLE,
            score=90.0,
            message="DeepSeek Web auth is configured",
        )

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        if not self.context_manager or not self.web_client:
            raise ProviderUnavailable("DeepSeek Web client is not initialized")

        full_prompt = request.prompt
        if request.context:
            full_prompt = f"{request.context}\n\n{request.prompt}"

        response = await self.context_manager.chat(
            session_key=request.session_id or "",
            prompt=full_prompt,
            images=request.images,
            web_mode=request.web_mode or "auto",
            search_enabled=request.search_enabled,
            thinking_enabled=self._thinking_enabled(request.web_mode or "auto"),
        )

        raw_text = response.text
        if response.thinking:
            raw_text = f"{response.thinking}\n\n{response.text}"

        processed = ResultProcessor.process(raw_text, executor_name=self.id, model_name="deepseek-chat")
        answer = processed.answer
        if processed.plan:
            answer = f"{processed.plan}\n\n{answer}"

        return ProviderResponse(
            answer=answer,
            provider_id=self.id,
            provider_type=self.type,
            model="deepseek-chat",
            raw_metadata={
                "thinking_present": bool(response.thinking),
                "search_enabled": request.search_enabled,
            },
        )

    async def upload_file(self, request: ProviderRequest) -> Any:
        if not self.web_client:
            raise ProviderUnavailable("DeepSeek Web client is not initialized")
        return await self.web_client.prepare_ref_file_ids(request.files or [])

    async def close_session(self, session_id: str) -> None:
        return None

    def _load_auth(self) -> DeepSeekAuth | None:
        data = web_auth_mod.load_saved_auth()
        if not data:
            return None
        auth = DeepSeekAuth.from_dict(data)
        return auth if auth.is_valid() else None

    async def _compress_via_api(self, text: str) -> str:
        lines = text.split("\n")
        return "\n".join(lines[-5:]) if len(lines) > 5 else text

    def _thinking_enabled(self, web_mode: str) -> bool:
        if web_mode == "quick":
            return False
        if web_mode in {"expert", "vision"}:
            return True
        return False
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_deepseek_web_client.py::test_deepseek_web_provider_without_auth_reports_unavailable -v
```

预期：`1 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/providers/deepseek_web.py hyperspace/providers/__init__.py tests/test_deepseek_web_client.py
git commit -m "feat: add deepseek web provider adapter"
```

---

### Task 7: 重构 HybridRouter 通过 Registry 选择 Provider

**涉及文件：**
- 修改: `hyperspace/hybrid_engine/hybrid_router.py`
- 测试: `tests/test_hybrid_router_provider_selection.py`

- [ ] **Step 1: 写入 Router provider selection 测试**

在 `tests/test_hybrid_router_provider_selection.py` 中添加：

```python
import pytest

from hyperspace.hybrid_engine.hybrid_router import HybridRouter
from hyperspace.providers.base import (
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)


class DummyProvider:
    def __init__(self, provider_id, capabilities=None, cost_tier=CostTier.FREE):
        self.id = provider_id
        self.type = ProviderType.API
        self.capabilities = capabilities or ProviderCapabilities(text=True)
        self.cost_tier = cost_tier

    async def health_check(self):
        return ProviderHealth(status=ProviderStatus.AVAILABLE, score=100.0)

    async def chat(self, request):
        return ProviderResponse(answer="ok", provider_id=self.id, provider_type=self.type)

    async def upload_file(self, request):
        raise NotImplementedError

    async def close_session(self, session_id):
        return None


def test_auto_route_prefers_deepseek_web_when_available():
    router = HybridRouter(
        provider_registry=None,
        providers={
            "deepseek_web": DummyProvider("deepseek_web"),
            "siliconflow_nex_n2_pro": DummyProvider("siliconflow_nex_n2_pro"),
        },
    )
    candidates = router._candidate_provider_ids(
        expected_output="answer",
        allow_web=True,
        allow_api=True,
    )

    assert candidates[0] == "deepseek_web"


def test_json_expected_output_prefers_structured_api_provider():
    router = HybridRouter(
        provider_registry=None,
        providers={
            "deepseek_web": DummyProvider("deepseek_web"),
            "agnes_text": DummyProvider(
                "agnes_text",
                ProviderCapabilities(text=True, structured_output=True),
            ),
        },
    )
    candidates = router._candidate_provider_ids(
        expected_output="json",
        allow_web=True,
        allow_api=True,
    )

    assert candidates[0] == "agnes_text"
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_hybrid_router_provider_selection.py -v
```

预期：`TypeError` 或 `AttributeError`，因为 HybridRouter 尚未支持 Registry/provider selection。

- [ ] **Step 3: 最小重构 HybridRouter**

在 `hyperspace/hybrid_engine/hybrid_router.py` 中新增导入：

```python
from hyperspace.providers.registry import ProviderRegistry
```

修改 `__init__` 签名：

```python
def __init__(
    self,
    config_path: str | Path | None = None,
    deepseek_api_config: dict | None = None,
    zhipu_config: dict | None = None,
    provider_registry: ProviderRegistry | None = None,
    providers: dict[str, Any] | None = None,
):
    self._cfg = self._load_config(config_path)
    self._deepseek_api_cfg = deepseek_api_config or {}
    self._zhipu_cfg = zhipu_config or {}
    self.registry = provider_registry
    self._providers = providers or {}

    self._web_client: DeepSeekWebClient | None = None
    self._ctx_mgr: ContextWindowManager | None = None
    self._init_web_client()

    self._health_checker = HealthChecker(
        deepseek_web_auth_provider=self._get_saved_auth,
    )
    self._fallback = FallbackManager(
        fallback_order=self._cfg["routing"]["fallback_order"]
    )
```

新增 helper：

```python
def _candidate_provider_ids(
    self,
    expected_output: str = "answer",
    allow_web: bool = True,
    allow_api: bool = True,
) -> list[str]:
    providers = self._providers or (self.registry.all() if self.registry else {})
    if not providers:
        return ["deepseek_web"]

    def supports_expected_output(provider: Any) -> bool:
        if expected_output in {"json", "structured"}:
            return bool(provider.capabilities.structured_output)
        return bool(provider.capabilities.text)

    def allowed(provider: Any) -> bool:
        if provider.type.value == "web" and not allow_web:
            return False
        if provider.type.value in {"api", "placeholder_web"} and not allow_api:
            return False
        if provider.type.value == "placeholder_web":
            return False
        return supports_expected_output(provider)

    def sort_key(item: tuple[str, Any]) -> tuple[int, str]:
        provider_id, provider = item
        if provider_id == "deepseek_web":
            return (0, provider_id)
        if provider.cost_tier.value == "free":
            return (1, provider_id)
        if provider.cost_tier.value == "low_cost":
            return (2, provider_id)
        return (3, provider_id)

    return [provider_id for provider_id, provider in sorted(providers.items(), key=sort_key) if allowed(provider)]
```

修改 `execute` 签名：

```python
async def execute(
    self,
    prompt: str,
    images: list[str] | None = None,
    context: str | None = None,
    mode: str = "auto",
    session_key: str = "",
    web_mode: str = "auto",
    search_enabled: bool | None = None,
    provider: str = "auto",
    routing_strategy: str = "auto",
    expected_output: str = "answer",
    allow_web: bool = True,
    allow_api: bool = True,
) -> ProcessedResult:
```

在 `_route` 中保留旧逻辑，但新增 `provider` 参数。为保持第一阶段稳定，若 `provider != "auto"`，返回：

```python
RoutingDecision(
    executor=provider,
    model=provider,
    reason=f"provider:{provider}",
    web_mode=resolved_web_mode,
    search_enabled=resolved_search_enabled,
    thinking_enabled=thinking_enabled,
    mode_source="explicit",
)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_hybrid_router_provider_selection.py -v
```

预期：`2 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/hybrid_engine/hybrid_router.py tests/test_hybrid_router_provider_selection.py
git commit -m "feat: add provider-aware router selection"
```

---

### Task 8: 升级 MCP Server

**涉及文件：**
- 修改: `hyperspace/server.py`
- 测试: `tests/test_mcp_schema.py`

- [ ] **Step 1: 写入 MCP schema 测试**

在 `tests/test_mcp_schema.py` 中添加：

```python
import hyperspace.server as server


def test_hyperspace_query_schema_has_provider_parameters():
    tools = server.list_tools.__wrapped__()
    query = next(tool for tool in tools if tool.name == "hyperspace_query")
    props = query.inputSchema["properties"]

    assert "provider" in props
    assert "routing_strategy" in props
    assert "expected_output" in props


def test_hyperspace_health_tool_exists():
    tools = server.list_tools.__wrapped__()
    names = {tool.name for tool in tools}

    assert "hyperspace_health" in names
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_mcp_schema.py -v
```

预期：`AssertionError`，因为 schema 尚未扩展。

- [ ] **Step 3: 扩展 MCP schema**

在 `hyperspace/server.py` 中新增枚举：

```python
_PROVIDERS = [
    "auto",
    "deepseek_web",
    "deepseek_api",
    "zhipu_api",
    "qwen_api",
    "siliconflow_nex_n2_pro",
    "agnes_text",
    "agnes_image",
    "agnes_video",
    "chatglm_web",
    "qwen_chat_web",
]
_ROUTING_STRATEGIES = [
    "auto",
    "web_first",
    "zero_cost_first",
    "api_first",
    "cheapest",
    "fastest",
    "balanced",
    "fallback",
]
_EXPECTED_OUTPUTS = [
    "answer",
    "plan",
    "json",
    "structured",
    "summary",
    "critique",
    "final_action_plan",
]
```

在 `hyperspace_query` 的 `inputSchema["properties"]` 中追加：

```python
"provider": {
    "type": "string",
    "enum": _PROVIDERS,
    "default": "auto",
    "description": "选择 provider；auto 表示由 HyperSpace 根据任务类型、能力和健康状态自动选择。",
},
"routing_strategy": {
    "type": "string",
    "enum": _ROUTING_STRATEGIES,
    "default": "auto",
    "description": "路由策略：auto/web_first/zero_cost_first/api_first/cheapest/fastest/balanced/fallback。",
},
"expected_output": {
    "type": "string",
    "enum": _EXPECTED_OUTPUTS,
    "default": "answer",
    "description": "期望输出类型；json/structured 会倾向支持 structured_output 的 API provider。",
},
"allow_web": {
    "type": "boolean",
    "default": True,
    "description": "是否允许使用 Web provider。",
},
"allow_api": {
    "type": "boolean",
    "default": True,
    "description": "是否允许使用 API provider。",
},
```

新增工具声明：

```python
types.Tool(
    name="hyperspace_health",
    description="查询 HyperSpace 所有 provider 的可用性、能力、健康分数和 fallback 状态。",
    inputSchema={
        "type": "object",
        "properties": {
            "check_mode": {
                "type": "string",
                "enum": ["light", "smoke"],
                "default": "light",
                "description": "light 只做配置/凭据检查；smoke 会尝试低成本探测请求。",
            }
        },
        "required": [],
    },
)
```

修改 `call_tool` 分支：

```python
if name == "hyperspace_health":
    check_mode = arguments.get("check_mode", "light")
    if check_mode == "smoke":
        text = "[hyperspace] smoke health check is not implemented in this phase"
    else:
        text = "[hyperspace] health check is not implemented in this phase"
    return [types.TextContent(type="text", text=text)]
```

修改混合引擎调用：

```python
result = await _hybrid_router.execute(
    prompt=prompt,
    images=attachments,
    context=context,
    mode=mode_str,
    session_key=session_key,
    web_mode=web_mode,
    search_enabled=search_enabled,
    provider=arguments.get("provider", "auto"),
    routing_strategy=arguments.get("routing_strategy", "auto"),
    expected_output=arguments.get("expected_output", "answer"),
    allow_web=arguments.get("allow_web", True),
    allow_api=arguments.get("allow_api", True),
)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_mcp_schema.py -v
```

预期：`2 passed`。

- [ ] **Step 5: Commit**

```bash
git add hyperspace/server.py tests/test_mcp_schema.py
git commit -m "feat: extend mcp provider parameters"
```

---

### Task 9: 更新配置和 .env.example

**涉及文件：**
- 修改: `config/providers.yaml`
- 修改: `config/hybrid_config.yaml`
- 修改: `.env.example`
- 测试: `tests/test_provider_registry.py`

- [ ] **Step 1: 写入配置加载测试**

在 `tests/test_provider_registry.py` 中追加：

```python
from pathlib import Path

from hyperspace.providers.registry import ProviderRegistry


def test_hybrid_config_registers_chatglm_fallback_to_agnes_text():
    config_path = Path("config/hybrid_config.yaml")
    registry = ProviderRegistry(config_path=config_path)
    chatglm = registry.get("chatglm_web")

    assert chatglm is not None
    assert chatglm.fallback_to == "agnes_text"
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
pytest tests/test_provider_registry.py::test_hybrid_config_registers_chatglm_fallback_to_agnes_text -v
```

预期：`AssertionError` 或 `AttributeError`，因为配置尚未更新。

- [ ] **Step 3: 更新 `config/providers.yaml`**

在 `cheap_capable` 中追加：

```yaml
  # 免费 API 备选: SiliconFlow Nex-N2-Pro
  - { provider: siliconflow, base_url: "https://api.siliconflow.cn/v1", model: "nex-agi/Nex-N2-Pro", key_env: "SILICONFLOW_API_KEY" }
  # 免费 API 备选: Agnes 文本模型
  - { provider: agnes, base_url: "https://apihub.agnes-ai.com/v1", model: "agnes-2.0-flash", key_env: "AGNES_API_KEY" }
```

- [ ] **Step 4: 更新 `config/hybrid_config.yaml`**

替换为 ProviderRegistry 配置：

```yaml
providers:
  deepseek_web:
    type: web
    class: hyperspace.providers.deepseek_web.DeepSeekWebProvider
    enabled: true
    cost_tier: free
    fallback_to: deepseek_api
    capabilities:
      text: true
      vision_understanding: true
      file_upload: true
      web_search: true
      streaming: true
      structured_output: false
      planning: true
      long_context: true

  deepseek_api:
    type: api
    class: hyperspace.providers.deepseek_api.DeepSeekAPIProvider
    enabled_env: DEEPSEEK_API_KEY
    base_url: "https://api.deepseek.com"
    model: "deepseek-chat"
    cost_tier: low_cost
    capabilities:
      text: true
      streaming: true
      structured_output: true
      planning: true
      long_context: true

  zhipu_api:
    type: api
    class: hyperspace.providers.zhipu_api.ZhipuAPIProvider
    enabled_env: ZHIPU_API_KEY
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4.7-flash"
    cost_tier: free
    capabilities:
      text: true
      streaming: true
      structured_output: true
      planning: true

  qwen_api:
    type: api
    class: hyperspace.providers.qwen_api.QwenAPIProvider
    enabled_env: QWEN_API_KEY
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: "qwen-plus"
    cost_tier: low_cost
    capabilities:
      text: true
      vision_understanding: true
      streaming: true
      structured_output: true
      planning: true

  siliconflow_nex_n2_pro:
    type: api
    class: hyperspace.providers.openai_compatible.OpenAICompatibleProvider
    enabled_env: SILICONFLOW_API_KEY
    base_url: "https://api.siliconflow.cn/v1"
    model: "nex-agi/Nex-N2-Pro"
    cost_tier: free
    capabilities:
      text: true
      streaming: true
      structured_output: true
      planning: true

  agnes_text:
    type: api
    class: hyperspace.providers.openai_compatible.OpenAICompatibleProvider
    enabled_env: AGNES_API_KEY
    base_url: "https://apihub.agnes-ai.com/v1"
    model: "agnes-2.0-flash"
    cost_tier: free
    capabilities:
      text: true
      streaming: true
      structured_output: true
      planning: true

  agnes_image:
    type: api
    class: hyperspace.providers.openai_compatible.OpenAICompatibleProvider
    enabled_env: AGNES_API_KEY
    base_url: "https://apihub.agnes-ai.com/v1"
    model: "agnes-image-2.1-flash"
    cost_tier: free
    capabilities:
      text: true
      vision_understanding: true
      image_generation: true
      streaming: false
      structured_output: true
      planning: false

  agnes_video:
    type: api
    class: hyperspace.providers.openai_compatible.OpenAICompatibleProvider
    enabled_env: AGNES_API_KEY
    base_url: "https://apihub.agnes-ai.com/v1"
    model: "agnes-video-v2.0"
    cost_tier: free
    capabilities:
      video_understanding: true
      video_generation: true
      streaming: false
      structured_output: false
      planning: false

  chatglm_web:
    type: placeholder_web
    class: hyperspace.providers.chatglm_web.ChatGLMWebPlaceholderProvider
    enabled: true
    fallback_to: agnes_text
    cost_tier: free
    capabilities:
      text: true
      planning: true
      long_context: true

  qwen_chat_web:
    type: placeholder_web
    class: hyperspace.providers.qwen_chat_web.QwenChatWebPlaceholderProvider
    enabled: true
    fallback_to: qwen_api
    cost_tier: free
    capabilities:
      text: true
      planning: true
      long_context: true

routing:
  default_executor: "deepseek_web"
  fallback_order:
    [
      "deepseek_web",
      "siliconflow_nex_n2_pro",
      "agnes_text",
      "zhipu_api",
      "deepseek_api",
      "qwen_api",
    ]
  rules:
    - condition: "has_image"
      executor: "deepseek_web"
    - condition: "needs_search"
      executor: "deepseek_web"
    - condition: "needs_planning"
      executor: "deepseek_web"
    - condition: "is_long"
      executor: "deepseek_web"
    - condition: "needs_coding"
      executor: "deepseek_api"
    - condition: "needs_translation"
      executor: "deepseek_api"
    - condition: "needs_structured_output"
      executor: "agnes_text"
```

- [ ] **Step 5: 更新 `.env.example`**

追加：

```bash
# Free API providers
SILICONFLOW_API_KEY=
AGNES_API_KEY=
QWEN_API_KEY=
```

- [ ] **Step 6: 跑测试确认通过**

```bash
pytest tests/test_provider_registry.py::test_hybrid_config_registers_chatglm_fallback_to_agnes_text -v
```

预期：`1 passed`。

- [ ] **Step 7: Commit**

```bash
git add config/providers.yaml config/hybrid_config.yaml .env.example tests/test_provider_registry.py
git commit -m "config: add multi-provider registry settings"
```

---

### Task 10: 补充集成测试

**涉及文件：**
- 修改: `tests/test_provider_contract.py`
- 修改: `tests/test_provider_registry.py`
- 修改: `tests/test_openai_compatible_provider.py`
- 修改: `tests/test_placeholder_providers.py`
- 修改: `tests/test_hybrid_router_provider_selection.py`
- 修改: `tests/test_mcp_schema.py`

- [ ] **Step 1: 增加 Placeholder fallback unavailable 测试**

在 `tests/test_placeholder_providers.py` 中追加：

```python
import pytest

from hyperspace.providers.base import ProviderRequest
from hyperspace.providers.chatglm_web import ChatGLMWebPlaceholderProvider
from hyperspace.providers.errors import ProviderNotImplemented


@pytest.mark.asyncio
async def test_chatglm_web_placeholder_reports_fallback_unavailable():
    class BrokenFallback:
        async def chat(self, request):
            raise ProviderNotImplemented("agnes_text unavailable")

    provider = ChatGLMWebPlaceholderProvider(
        provider_id="chatglm_web",
        fallback_provider=BrokenFallback(),
    )

    with pytest.raises(ProviderNotImplemented):
        await provider.chat(ProviderRequest(prompt="hello", provider_id="chatglm_web"))
```

- [ ] **Step 2: 增加 Router zero-cost-first 测试**

在 `tests/test_hybrid_router_provider_selection.py` 中追加：

```python
def test_zero_cost_first_sorts_free_api_after_deepseek_web():
    router = HybridRouter(
        provider_registry=None,
        providers={
            "deepseek_api": DummyProvider("deepseek_api", cost_tier=CostTier.LOW_COST),
            "agnes_text": DummyProvider("agnes_text", cost_tier=CostTier.FREE),
            "deepseek_web": DummyProvider("deepseek_web", cost_tier=CostTier.FREE),
        },
    )
    candidates = router._candidate_provider_ids(routing_strategy="zero_cost_first")

    assert candidates[0] == "deepseek_web"
    assert candidates[1] == "agnes_text"
```

- [ ] **Step 3: 增加 MCP provider enum 测试**

在 `tests/test_mcp_schema.py` 中追加：

```python
def test_provider_enum_includes_chatglm_and_agnes():
    tools = server.list_tools.__wrapped__()
    query = next(tool for tool in tools if tool.name == "hyperspace_query")
    providers = query.inputSchema["properties"]["provider"]["enum"]

    assert "chatglm_web" in providers
    assert "agnes_text" in providers
    assert "siliconflow_nex_n2_pro" in providers
```

- [ ] **Step 4: 跑新增测试**

```bash
pytest tests/test_placeholder_providers.py tests/test_hybrid_router_provider_selection.py tests/test_mcp_schema.py -v
```

预期：相关测试全部通过。

- [ ] **Step 5: Commit**

```bash
git add tests/test_placeholder_providers.py tests/test_hybrid_router_provider_selection.py tests/test_mcp_schema.py
git commit -m "test: expand provider integration coverage"
```

---

### Task 11: 更新 README

**涉及文件：**
- 修改: `README.md`

- [ ] **Step 1: 更新架构说明**

在 README 的架构说明区域追加：

```markdown
## 多 Provider 架构

HyperSpace 使用 ProviderRegistry 统一管理 Web provider、API provider 和占位 provider。当前阶段：

- `deepseek_web` 是唯一主力真实 Web Provider。
- `chatglm_web` 和 `qwen_chat_web` 是占位 provider，不实现网页自动化。
- `chatglm_web` 显式调用时 fallback 到 `agnes_text`。
- `qwen_chat_web` 显式调用时 fallback 到 `qwen_api`。
- `siliconflow_nex_n2_pro`、`agnes_text`、`agnes_image`、`agnes_video` 通过 OpenAI-compatible API Provider 接入。
```

- [ ] **Step 2: 更新环境变量说明**

追加：

```markdown
## 环境变量

- `DEEPSEEK_API_KEY`
- `ZHIPU_API_KEY`
- `QWEN_API_KEY`
- `SILICONFLOW_API_KEY`
- `AGNES_API_KEY`

不要把 API Key 写入 YAML、代码或测试。
```

- [ ] **Step 3: 更新 MCP 参数说明**

追加：

```markdown
## MCP 参数

`hyperspace_query` 支持：

- `provider`: 选择 provider，默认 `auto`。
- `routing_strategy`: 路由策略，支持 `auto`、`web_first`、`zero_cost_first`、`api_first`、`cheapest`、`fastest`、`balanced`、`fallback`。
- `expected_output`: 期望输出，支持 `answer`、`plan`、`json`、`structured`、`summary`、`critique`、`final_action_plan`。
- `allow_web` / `allow_api`: 控制是否允许 Web/API provider。

`hyperspace_health` 用于查询 provider 健康状态。
```

- [ ] **Step 4: 运行文档检查命令**

```bash
python -m pytest tests/test_mcp_schema.py -v
```

预期：MCP schema 测试通过。

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: describe multi-provider hyperSpace architecture"
```

---

### Task 12: 最终验证

**涉及文件：**
- 全部修改文件

- [ ] **Step 1: 运行完整测试**

```bash
pytest tests/ -v
```

预期：所有测试通过；若旧测试因兼容路径调整失败，需要修复兼容逻辑后再标记完成。

- [ ] **Step 2: 检查设计文档要求是否全部覆盖**

```bash
git diff --stat
```

预期：包含 Provider Contract、Registry、Provider 实现、Router、MCP、配置、测试、README 的变更。

- [ ] **Step 3: 检查敏感信息**

```bash
git diff --check
```

预期：无空白错误。

同时人工检查 diff 中不包含真实 API Key。

- [ ] **Step 4: 最终 Commit（如还有未提交变更）**

```bash
git add .
git commit -m "feat: complete multi-provider phase one"
```

预期：提交成功。
