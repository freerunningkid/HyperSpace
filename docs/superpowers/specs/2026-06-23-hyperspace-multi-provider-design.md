# HyperSpace 多 Provider 架构第一阶段设计规格

- 日期：2026-06-23
- 范围：ProviderRegistry、标准 Provider 接口、DeepSeek Web 标准 Provider 迁移、Router/MCP 升级、ChatGLM/Qwen Web 占位、免费 OpenAI-compatible API Provider
- 状态：已批准，待实现

## 1. 背景与目标

HyperSpace 的长期目标是构建“网页端优先推理、低成本、多源混合架构”，为本地 Agent 提供统一 MCP 入口，屏蔽底层模型和网页端调度复杂度。

当前实现已经具备 DeepSeek Web 原生调用能力，但核心路径仍然深度绑定 DeepSeek：

- `HybridRouter` 直接依赖 DeepSeek Web 客户端。
- 路由规则只覆盖 `deepseek_web`、`deepseek_api`、`zhipu`。
- MCP schema 主要围绕 DeepSeek Web 模式设计。
- ChatGLM Web、Qwen Chat Web 尚未形成可扩展 provider 形态。

本阶段的目标不是完整实现所有网页端自动化，而是先把 HyperSpace 从“DeepSeek 中心化实现”改造成“多 Provider 可扩展架构”。

### 1.1 本阶段目标

本阶段完成后应满足：

1. 建立标准 Provider 接口。
2. 建立 ProviderRegistry，统一注册和管理 provider。
3. 将 DeepSeek Web 迁移为标准 provider。
4. 将 DeepSeek API、Zhipu API、Qwen API、SiliconFlow、Agnes 系列纳入统一 provider 体系。
5. 将 ChatGLM Web、Qwen Chat Web 作为占位 provider 注册，声明能力并 fallback 到 API。
6. 重构 HybridRouter，使其通过 Registry 和 Provider 接口选择与调用 provider。
7. 升级 MCP 接口，支持 provider、routing_strategy、expected_output、health 查询等参数。
8. 保持旧 `mode` 参数和 DeepSeek Web 现有能力尽量兼容。
9. 所有 API Key 只能通过环境变量或安全配置读取，禁止硬编码。

### 1.2 本阶段不做的事

为了避免范围失控，本阶段明确不做：

1. 不实现 ChatGLM Web 的 Playwright 自动化。
2. 不实现 Qwen Chat Web 的 Playwright 自动化。
3. 不统一 Proxy 模式和 MCP 模式的底层调度。
4. 不重写 DeepSeek Web 的 PoW、SSE、文件上传细节。
5. 不引入 LangChain、AutoGen、CrewAI。
6. 不引入 LiteLLM Proxy 作为第一阶段必需依赖。
7. 不实现完整 Cookie 加密体系。
8. 不承诺 Agnes 图片/视频能力的实际可用性，只先在 capability 中预留并配置驱动。

---

## 2. 目标架构

本阶段目标架构如下：

```text
本地 Agent
  → MCP stdio
    → hyperspace_query
    → hyperspace_health
        ↓
    HyperSpace Server
        ↓
    HybridRouter
        ↓
    TaskAnalyzer
        ↓
    ProviderRegistry
        ↓
    ProviderRouter
        ↓
    Provider Adapters
        ├─ DeepSeekWebProvider
        ├─ DeepSeekAPIProvider
        ├─ ZhipuAPIProvider
        ├─ QwenAPIProvider
        ├─ SiliconFlowNexProvider
        ├─ AgnesTextProvider
        ├─ AgnesImageProvider
        ├─ AgnesVideoProvider
        ├─ ChatGLMWebPlaceholderProvider
        └─ QwenChatWebPlaceholderProvider
```

核心原则：

1. `HybridRouter` 只处理策略，不处理 provider 内部细节。
2. `ProviderRegistry` 负责 provider 注册、配置加载、能力查询、健康查询。
3. 每个 provider 实现统一接口。
4. Web provider 和 API provider 在 Router 层统一调度。
5. 占位 provider 可以被注册、查询、显式 fallback，但默认不进入 auto 路由。

---

## 3. Provider 类型

### 3.1 ProviderType

```python
class ProviderType(str, Enum):
    WEB = "web"
    API = "api"
    PLACEHOLDER_WEB = "placeholder_web"
```

### 3.2 ProviderStatus

```python
class ProviderStatus(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_IMPLEMENTED = "not_implemented"
    DISABLED = "disabled"
```

### 3.3 CostTier

```python
class CostTier(str, Enum):
    FREE = "free"
    LOW_COST = "low_cost"
    PAID = "paid"
    UNKNOWN = "unknown"
```

说明：

- `FREE` 表示当前配置认为该 provider 可免费使用。
- 免费状态可能随平台策略变化，因此必须配置驱动，不能写死在代码逻辑里。
- Router 使用 `cost_tier` 参与排序，但最终成本以实际观测和配置为准。

---

## 4. Provider 能力模型

### 4.1 ProviderCapabilities

每个 provider 声明自己的能力：

```python
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
```

### 4.2 能力解释

| 能力 | 说明 |
|---|---|
| `text` | 文本对话 |
| `vision_understanding` | 图片理解 |
| `image_generation` | 图片生成 |
| `video_understanding` | 视频理解 |
| `video_generation` | 视频生成 |
| `file_upload` | 文件上传 |
| `web_search` | 联网搜索 |
| `streaming` | 流式输出 |
| `structured_output` | 稳定结构化输出，例如 JSON |
| `planning` | 适合做计划、拆解、分析 |
| `long_context` | 长文本处理 |
| `tool_calling` | 工具调用 |

### 4.3 第一阶段能力基线

| Provider | 类型 | 能力基线 |
|---|---|---|
| `deepseek_web` | `web` | `text`, `vision_understanding`, `file_upload`, `web_search`, `streaming`, `planning`, `long_context` |
| `deepseek_api` | `api` | `text`, `streaming`, `structured_output`, `planning`, `long_context` |
| `zhipu_api` | `api` | `text`, `streaming`, `structured_output`, `planning` |
| `qwen_api` | `api` | `text`, `vision_understanding`, `streaming`, `structured_output`, `planning` |
| `siliconflow_nex_n2_pro` | `api` | `text`, `streaming`, `structured_output`, `planning` |
| `agnes_text` | `api` | `text`, `streaming`, `structured_output`, `planning` |
| `agnes_image` | `api` | `text`, `vision_understanding`, `image_generation`，具体以模型能力实测为准 |
| `agnes_video` | `api` | `video_understanding`, `video_generation`，具体以模型能力实测为准 |
| `chatglm_web` | `placeholder_web` | `text`, `planning`, `long_context`，但 web 自动化未实现 |
| `qwen_chat_web` | `placeholder_web` | `text`, `planning`, `long_context`，但 web 自动化未实现 |

---

## 5. Provider 标准接口

### 5.1 ProviderRequest

统一请求结构：

```python
class ProviderRequest:
    prompt: str
    provider_id: ProviderId
    mode: str | None = None
    web_mode: str | None = None
    search_enabled: bool = False
    session_id: str | None = None
    files: list[str] | None = None
    images: list[str] | None = None
    expected_output: str = "answer"
    routing_strategy: str = "auto"
    context: list[dict] | None = None
```

### 5.2 ProviderResponse

统一响应结构：

```python
class ProviderResponse:
    answer: str
    provider_id: ProviderId
    provider_type: ProviderType
    model: str | None = None
    raw_metadata: dict[str, Any]
    usage: dict[str, Any] | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    error: str | None = None
```

### 5.3 ProviderHealth

统一健康结构：

```python
class ProviderHealth:
    status: ProviderStatus
    score: float
    last_checked_at: str | None
    last_error: str | None
    latency_ms: float | None
    success_rate: float | None
    message: str
```

### 5.4 BaseProvider

所有 provider 实现统一接口：

```python
class BaseProvider:
    id: ProviderId
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
        pass
```

---

## 6. ProviderRegistry 设计

### 6.1 职责

`ProviderRegistry` 负责：

1. 从 YAML 配置加载 provider。
2. 创建 provider 实例。
3. 根据 provider id 查找 provider。
4. 列出所有 provider。
5. 查询 provider capability。
6. 查询 provider health。
7. 为 Router 提供候选 provider 列表。
8. 支持显式 provider 选择和 auto 路由过滤。

### 6.2 Registry 行为约束

1. Registry 不决定路由策略。
2. Registry 不直接调用模型。
3. Registry 只负责 provider 生命周期、配置、能力、健康状态。
4. Router 负责根据任务画像、能力、health、cost、strategy 选择 provider。
5. Provider 负责自己的认证、会话、请求、响应解析。

### 6.3 Provider 注册配置示例

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
    base_url: https://api.deepseek.com/v1
    model: deepseek-chat
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
    base_url: https://open.bigmodel.cn/api/paas/v4
    model: glm-4-flash
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
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: qwen-plus
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
    base_url: https://api.siliconflow.cn/v1
    model: nex-agi/Nex-N2-Pro
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
    base_url: https://apihub.agnes-ai.com/v1
    model: agnes-2.0-flash
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
    base_url: https://apihub.agnes-ai.com/v1
    model: agnes-image-2.1-flash
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
    base_url: https://apihub.agnes-ai.com/v1
    model: agnes-video-v2.0
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
    fallback_to: zhipu_api
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
```

说明：

- 配置中的模型名、base_url、cost_tier 均可调整。
- `enabled_env` 表示该 provider 只有在对应环境变量存在时才启用。
- 配置示例不应包含真实 API Key。
- 真实 API Key 应放入 `.env` 或运行环境，不写入 git。

---

## 7. API Provider 设计

### 7.1 OpenAICompatibleProvider

SiliconFlow 和 Agnes 系列都采用 OpenAI-compatible Chat Completions 格式，因此第一阶段建议实现一个通用 provider：

```text
hyperspace.providers.openai_compatible.OpenAICompatibleProvider
```

它负责：

1. 读取 `base_url`。
2. 读取 `model`。
3. 读取 API Key。
4. 调用 `/chat/completions`。
5. 支持流式和非流式。
6. 支持 text 和 vision 消息格式。
7. 返回 `ProviderResponse`。
8. 实现 health check。

### 7.2 专用 provider 包装

为了 Registry 和 Router 可读性，可以在配置中声明多个 OpenAI-compatible provider：

```text
siliconflow_nex_n2_pro
agnes_text
agnes_image
agnes_video
```

它们共享底层 `OpenAICompatibleProvider` 实现，但拥有不同 provider id、model、capabilities、cost_tier 和 fallback 目标。

### 7.3 API Key 安全要求

所有 API Key 必须通过环境变量读取：

```text
DEEPSEEK_API_KEY
ZHIPU_API_KEY
QWEN_API_KEY
SILICONFLOW_API_KEY
AGNES_API_KEY
```

禁止：

1. 在代码中硬编码 API Key。
2. 在设计文档中记录真实 API Key。
3. 将 API Key 写入 YAML。
4. 将 API Key 写入测试。
5. 将 API Key 写入日志。

如果用户误将密钥粘贴到对话或文件中，应优先建议轮换密钥，并从项目中移除明文副本。

---

## 8. DeepSeek Web Provider 迁移

### 8.1 目标

将现有 DeepSeek Web 逻辑迁移为标准 provider，但不重写核心能力。

现有逻辑主要来自：

- `hyperspace/hybrid_engine/deepseek_web_client.py`
- `hyperspace/hybrid_engine/context_window_manager.py`
- `hyperspace/hybrid_engine/web_auth.py`
- `hyperspace/hybrid_engine/result_processor.py`

### 8.2 保留能力

`DeepSeekWebProvider` 应继续支持：

1. DeepSeek Web PoW challenge。
2. PoW solver。
3. DeepSeek session 创建。
4. SSE 流解析。
5. 文件上传。
6. 图片/文件引用。
7. session 摘要压缩。
8. DeepSeek Web auth 提取。
9. search_enabled。
10. web_mode 映射。

### 8.3 迁移边界

迁移后：

- `HybridRouter` 不直接 import `DeepSeekWebClient`。
- `HybridRouter` 不直接 import `ContextWindowManager`。
- `DeepSeekWebProvider` 内部可以继续复用这些类。
- DeepSeek Web 的具体协议细节被隔离在 provider adapter 内。

### 8.4 DeepSeekWebProvider.chat

`DeepSeekWebProvider.chat()` 负责：

1. 校验认证状态。
2. 创建或复用 DeepSeek Web session。
3. 处理图片和文件引用。
4. 调用 DeepSeek Web chat completion。
5. 解析 SSE 响应。
6. 提取思考内容和最终答案。
7. 返回 `ProviderResponse`。

### 8.5 DeepSeekWebProvider.health_check

建议支持两级健康检查：

#### 轻量健康检查

默认执行：

1. 凭据文件是否存在。
2. cookie 是否包含关键字段。
3. token 是否可读取。
4. 最近失败次数是否过高。
5. 最近成功时间是否过久。

#### 可选 smoke test

可选执行一次极低成本探测请求：

1. 不启用 search。
2. 不上传文件。
3. 不要求结构化输出。
4. prompt 极短。
5. 默认关闭，由用户或配置显式启用。

---

## 9. ChatGLM Web / Qwen Chat Web 占位 Provider

### 9.1 目标

本阶段不实现真实网页自动化，只保留未来扩展点。

它们应满足：

1. 有 provider id。
2. 有能力声明。
3. 有 fallback 目标。
4. 有明确 health 状态。
5. 被显式调用时 fallback 到 API。
6. 如果 fallback API 不可用，返回明确错误。
7. 默认不进入 auto 路由。

### 9.2 ChatGLMWebPlaceholderProvider

建议配置：

```text
id: chatglm_web
type: placeholder_web
fallback_to: zhipu_api
```

当用户显式选择：

```json
{
  "provider": "chatglm_web"
}
```

如果 `zhipu_api` 可用，则调用 `zhipu_api`，并返回：

```json
{
  "fallback_used": true,
  "fallback_reason": "chatglm_web_automation_not_implemented"
}
```

如果 `zhipu_api` 不可用，则返回：

```text
ProviderUnavailable:
ChatGLM Web provider is registered but web automation is not implemented,
and configured fallback provider zhipu_api is unavailable.
```

### 9.3 QwenChatWebPlaceholderProvider

建议配置：

```text
id: qwen_chat_web
type: placeholder_web
fallback_to: qwen_api
```

行为与 ChatGLM Web 占位 provider 一致。

### 9.4 auto 路由行为

默认规则：

1. `provider="auto"` 不选择占位 provider。
2. `provider="chatglm_web"` 或 `provider="qwen_chat_web"` 是显式请求，允许 fallback。
3. 未来真实 Web 自动化完成后，可将占位 provider 改为真实 provider，并允许进入 auto 路由。

---

## 10. Router 重构设计

### 10.1 当前问题

当前 `HybridRouter` 直接写死了：

```text
deepseek_web
deepseek_api
zhipu
```

并且直接调用 DeepSeek 相关对象。

这会导致新增 provider 必须改 Router。

### 10.2 新 Router 职责

新的 `HybridRouter` 只做策略：

1. 分析任务。
2. 根据任务画像生成候选 provider。
3. 根据 capability 过滤 provider。
4. 根据 health score 排序。
5. 根据 routing_strategy 执行。
6. 返回统一 `ProviderResponse`。
7. 不关心 provider 内部实现。

### 10.3 新执行流程

```text
execute()
  → analyze_task()
  → build_candidate_providers()
  → filter_by_capabilities()
  → filter_by_health()
  → sort_by_routing_strategy()
  → execute_with_fallback()
  → normalize_response()
```

### 10.4 routing_strategy

建议支持：

```text
auto
web_first
zero_cost_first
api_first
cheapest
fastest
balanced
fallback
force_provider
```

| 策略 | 行为 |
|---|---|
| `auto` | 默认策略，Web 优先；严格 JSON、高可靠、关键执行倾向 API |
| `web_first` | 优先 Web provider，失败再 API |
| `zero_cost_first` | 优先免费资源：DeepSeek Web → 免费 API → 低成本 API → 付费 API |
| `api_first` | 优先 API provider |
| `cheapest` | 按 `cost_tier` 和配置成本排序 |
| `fastest` | 按最近平均延迟排序 |
| `balanced` | 综合成本、速度、成功率、能力匹配 |
| `fallback` | 按 fallback chain 执行 |
| `force_provider` | 强制指定 provider，不自动换；失败时返回错误，除非配置允许 fallback |

### 10.5 expected_output 对路由的影响

`expected_output` 应影响 provider 选择。

| expected_output | 路由倾向 |
|---|---|
| `answer` | Web 优先 |
| `summary` | Web 优先 |
| `plan` | Web 优先 |
| `critique` | Web 优先 |
| `json` | API 优先 |
| `structured` | API 优先 |
| `final_action_plan` | Web 出计划，必要时 API 校验 |

如果用户要求：

```json
{
  "expected_output": "json"
}
```

Router 应优先选择支持 `structured_output` 的 API provider，而不是 DeepSeek Web。

### 10.6 能力匹配规则

Router 根据任务画像过滤 provider：

| 任务需求 | 必需/偏好能力 |
|---|---|
| 纯文本问答 | `text` |
| 图片理解 | `vision_understanding` |
| 图片生成 | `image_generation` |
| 视频理解 | `video_understanding` |
| 视频生成 | `video_generation` |
| 文件分析 | `file_upload` |
| 联网搜索 | `web_search` |
| 严格 JSON | `structured_output` |
| 计划/拆解 | `planning` |
| 长文处理 | `long_context` |

### 10.7 免费资源排序

当 `routing_strategy="zero_cost_first"` 或 `cheapest` 时，建议排序：

```text
1. DeepSeek Web
2. SiliconFlow Nex-N2-Pro
3. Agnes 文本模型
4. Zhipu API
5. 其他免费 API
6. DeepSeek API
7. Qwen API
8. 付费 API
```

说明：

- 实际排序应由配置决定，代码只实现排序逻辑。
- “免费”状态可能变化，因此 `cost_tier` 必须配置驱动。
- 如果某个免费 API 未配置 key，应跳过或 fallback。

---

## 11. Health Score 设计

### 11.1 目标

Health Score 不只是布尔值，而是 Router 排序依据。

建议分数范围：

```text
0 - 100
```

### 11.2 评分组成

建议：

```text
score =
  availability_score * 0.35
  + success_rate_score * 0.25
  + latency_score * 0.20
  + capability_match_score * 0.15
  + recency_score * 0.05
  - error_penalty
```

### 11.3 Provider 状态

建议至少支持：

```text
available
degraded
unavailable
not_implemented
disabled
```

### 11.4 API provider health

API provider 默认轻量检查：

1. API Key 是否存在。
2. base_url 是否配置。
3. model 是否配置。
4. 最近失败次数。
5. 最近成功时间。

可选 smoke test：

1. 调用 `/models` 或极短 `/chat/completions`。
2. 默认关闭。
3. 由 `hyperspace_health(check_mode="smoke")` 或配置显式启用。

### 11.5 占位 provider health

对于 `chatglm_web` 和 `qwen_chat_web`：

```text
web_status = not_implemented
api_fallback_status = depends_on_api_key
overall_status = degraded 或 unavailable
```

Router 默认不选它们，但 health 工具应该能看到它们。

---

## 12. Fallback 设计

### 12.1 普通 fallback

普通 fallback 逻辑：

```text
候选 provider 1 失败
  → 判断错误是否可重试
  → 可重试则重试
  → 仍失败则尝试候选 provider 2
```

### 12.2 占位 provider fallback

对于 ChatGLM/Qwen Web 占位 provider：

```text
用户选择 chatglm_web
  → 检测到 web_automation_not_implemented
  → fallback_to = zhipu_api
  → 调用 zhipu_api
  → 返回 metadata.fallback_used = true
```

### 12.3 fallback metadata

所有 fallback 都应在返回 metadata 中体现：

```json
{
  "provider": "zhipu_api",
  "requested_provider": "chatglm_web",
  "fallback_used": true,
  "fallback_reason": "chatglm_web_automation_not_implemented"
}
```

---

## 13. 错误分类

建议统一错误类型：

```text
ProviderUnavailable
ProviderNotImplemented
AuthenticationError
RateLimitError
TimeoutError
FileUploadError
StructuredOutputError
UpstreamError
ValidationError
```

每个错误都应映射为 Router 可理解的分类：

| 错误 | 是否重试 | 是否 fallback |
|---|---:|---:|
| timeout | 是 | 是 |
| rate_limit | 是 | 是 |
| auth_expired | 否 | 是 |
| not_implemented | 否 | 是 |
| validation_error | 否 | 视情况 |
| file_upload_error | 否 | 是 |
| structured_output_error | 视情况 | 是 |

---

## 14. MCP 接口升级

### 14.1 保留现有工具

继续保留：

```text
hyperspace_query
```

并尽量保持旧参数兼容。

### 14.2 扩展 hyperspace_query

建议新增参数：

```json
{
  "provider": "auto",
  "routing_strategy": "auto",
  "expected_output": "answer",
  "allow_web": true,
  "allow_api": true,
  "include_metadata": true
}
```

完整参数建议：

```json
{
  "prompt": "...",
  "mode": "auto | force_web | force_api | force_zhipu",
  "provider": "auto | deepseek_web | deepseek_api | zhipu_api | qwen_api | siliconflow_nex_n2_pro | agnes_text | agnes_image | agnes_video | chatglm_web | qwen_chat_web",
  "routing_strategy": "auto | web_first | zero_cost_first | api_first | cheapest | fastest | balanced | fallback",
  "web_mode": "auto | quick | expert | vision",
  "search_enabled": true,
  "session_id": "main",
  "files": [],
  "images": [],
  "expected_output": "answer | plan | json | structured | summary | critique | final_action_plan",
  "allow_web": true,
  "allow_api": true,
  "include_metadata": true
}
```

### 14.3 新增 hyperspace_health

用途：

```text
查询所有 provider 的可用性、能力、最近错误、平均延迟和 fallback 状态。
```

返回结构示例：

```json
{
  "providers": {
    "deepseek_web": {
      "status": "available",
      "score": 87,
      "capabilities": {
        "text": true,
        "vision_understanding": true,
        "file_upload": true,
        "web_search": true
      },
      "last_error": null
    },
    "siliconflow_nex_n2_pro": {
      "status": "available",
      "score": 90,
      "cost_tier": "free",
      "capabilities": {
        "text": true,
        "structured_output": true
      },
      "last_error": null
    },
    "chatglm_web": {
      "status": "degraded",
      "score": 40,
      "capabilities": {
        "text": true,
        "planning": true
      },
      "fallback_to": "zhipu_api",
      "last_error": "web_automation_not_implemented"
    }
  }
}
```

### 14.4 可选新增 hyperspace_providers

用途：

```text
列出已注册 provider、类型、能力、fallback 目标和实现状态。
```

第一阶段可以暂不新增该工具，只通过 `hyperspace_health` 返回 provider 列表。

---

## 15. 文件与模块实施建议

### 15.1 新增模块

```text
HyperSpace/
  hyperspace/
    providers/
      base.py
      registry.py
      capabilities.py
      health.py
      errors.py
      openai_compatible.py
      deepseek_web.py
      deepseek_api.py
      zhipu_api.py
      qwen_api.py
      chatglm_web.py
      qwen_chat_web.py
```

### 15.2 修改模块

```text
hyperspace/hybrid_engine/hybrid_router.py
hyperspace/server.py
config/providers.yaml
config/hybrid_config.yaml
.env.example
tests/test_hybrid_engine.py
tests/test_deepseek_web_client.py
README.md
```

### 15.3 暂时不改

```text
hyperspace/proxy_server.py
hyperspace/proxy/
config/proxy_config.yaml
```

原因：

Proxy 统一到底层 Scheduler 是下一阶段目标。当前阶段先把 MCP 路径打通，避免范围过大。

---

## 16. 实施步骤

### Step 1：定义 Provider Contract

目标文件：

```text
hyperspace/providers/base.py
hyperspace/providers/capabilities.py
hyperspace/providers/health.py
hyperspace/providers/errors.py
```

完成标准：

- `BaseProvider`
- `ProviderCapabilities`
- `ProviderHealth`
- `ProviderRequest`
- `ProviderResponse`
- `ProviderStatus`
- `ProviderType`
- `CostTier`
- 统一错误类型

### Step 2：实现 ProviderRegistry

目标文件：

```text
hyperspace/providers/registry.py
```

完成标准：

- 可以从 YAML 配置加载 provider。
- 可以按 id 获取 provider。
- 可以列出所有 provider。
- 可以获取所有 provider health。
- 不依赖 DeepSeek 专用类。
- 支持 `enabled_env`。
- 支持 `fallback_to`。
- 支持 capability 查询。

### Step 3：实现 OpenAI-compatible API Provider

目标文件：

```text
hyperspace/providers/openai_compatible.py
```

完成标准：

- 支持 OpenAI-compatible `/chat/completions`。
- 支持 base_url、model、api_key_env 配置。
- 支持 text 消息。
- 支持 vision 消息基础格式。
- 支持 streaming 和非 streaming。
- 返回 `ProviderResponse`。
- 支持 health check。
- 不硬编码任何 API Key。

### Step 4：实现 API Provider 包装

目标文件：

```text
hyperspace/providers/deepseek_api.py
hyperspace/providers/zhipu_api.py
hyperspace/providers/qwen_api.py
```

完成标准：

- 复用或迁移现有 API 调用逻辑。
- 避免通过临时修改 `os.environ` 注入 API key。
- 统一返回 `ProviderResponse`。
- 支持 health check。
- 支持 fallback metadata。

### Step 5：实现 SiliconFlow 和 Agnes Provider

目标文件：

```text
config/providers.yaml
```

完成标准：

- `siliconflow_nex_n2_pro` 使用 `OpenAICompatibleProvider`。
- `agnes_text` 使用 `OpenAICompatibleProvider`。
- `agnes_image` 使用 `OpenAICompatibleProvider`。
- `agnes_video` 使用 `OpenAICompatibleProvider`。
- 所有 API Key 通过环境变量读取。
- 所有模型名、base_url、cost_tier 配置驱动。
- 不在代码、配置、文档中写入真实 API Key。

### Step 6：实现 ChatGLM/Qwen Web 占位 Provider

目标文件：

```text
hyperspace/providers/chatglm_web.py
hyperspace/providers/qwen_chat_web.py
```

完成标准：

- 有 capability 声明。
- 有 fallback_to 配置。
- 被显式调用时 fallback 到 API。
- health 状态明确显示 `not_implemented`。
- auto 路由默认不选它们。

### Step 7：实现 DeepSeekWebProvider Adapter

目标文件：

```text
hyperspace/providers/deepseek_web.py
```

完成标准：

- 复用现有 `DeepSeekWebClient` 和 `ContextWindowManager`。
- 实现 `health_check()`。
- 实现 `chat()`。
- 返回 `ProviderResponse`。
- 保留现有 DeepSeek Web 能力。
- 不让 `HybridRouter` 直接 import `DeepSeekWebClient`。

### Step 8：重构 HybridRouter

目标文件：

```text
hyperspace/hybrid_engine/hybrid_router.py
```

完成标准：

- Router 只依赖 `ProviderRegistry`。
- 不再直接依赖 `DeepSeekWebClient`。
- 支持 provider、routing_strategy、expected_output。
- 支持 health-aware 排序。
- 支持 zero-cost-first 排序。
- 支持 fallback metadata。
- 保持旧 mode 参数兼容。

### Step 9：升级 MCP Server

目标文件：

```text
hyperspace/server.py
```

完成标准：

- `hyperspace_query` 增加新参数。
- 新增 `hyperspace_health` 工具。
- 返回结构化 metadata。
- 错误不再只返回纯文本。
- 旧调用方式仍可用。

### Step 10：更新配置

目标文件：

```text
config/providers.yaml
config/hybrid_config.yaml
.env.example
```

完成标准：

- provider 注册表清晰。
- fallback 配置清晰。
- API key 环境变量清晰。
- DeepSeek Web 配置清晰。
- ChatGLM/Qwen Web 占位状态清晰。
- SiliconFlow、Agnes provider 配置清晰。

### Step 11：补充测试

目标文件：

```text
tests/test_provider_contract.py
tests/test_provider_registry.py
tests/test_openai_compatible_provider.py
tests/test_placeholder_providers.py
tests/test_hybrid_router_provider_selection.py
tests/test_mcp_schema.py
```

完成标准：

- Provider contract 测试通过。
- Registry 测试通过。
- OpenAI-compatible provider 测试通过。
- Router 选择逻辑测试通过。
- DeepSeek Web 旧行为测试尽量保留。
- ChatGLM/Qwen placeholder fallback 测试通过。
- MCP schema 测试通过。
- 所有测试不得包含真实 API Key。

### Step 12：更新 README

目标文件：

```text
README.md
```

完成标准：

- 说明当前支持状态。
- 说明 provider registry。
- 说明 routing strategy。
- 说明 expected_output。
- 说明 health 工具。
- 说明 SiliconFlow、Agnes 免费 API provider。
- 说明 ChatGLM/Qwen Web 当前只是占位 + API fallback。
- 说明未来如何接入真实 ChatGLM/Qwen Web provider。

---

## 17. 测试策略

### 17.1 Provider contract 测试

验证所有 provider 都实现：

- `health_check`
- `chat`
- `upload_file`
- `close_session`

### 17.2 Registry 测试

验证：

1. 可以从 YAML 加载 provider。
2. 缺少 API Key 的 provider 被禁用或标记 unavailable。
3. 可以按 id 获取 provider。
4. 可以列出所有 provider。
5. 占位 provider 有 fallback 配置。

### 17.3 Router 测试

验证：

1. `auto` 默认倾向 DeepSeek Web。
2. `zero_cost_first` 优先免费资源。
3. `json` expected_output 倾向 API。
4. 图片任务过滤掉不支持 vision 的 provider。
5. 占位 provider 默认不进入 auto 路由。
6. 显式选择占位 provider 会 fallback。

### 17.4 Placeholder provider 测试

验证：

1. `chatglm_web` fallback 到 `zhipu_api`。
2. `qwen_chat_web` fallback 到 `qwen_api`。
3. fallback metadata 正确。
4. fallback API 不可用时返回明确错误。

### 17.5 OpenAI-compatible provider 测试

使用 mock HTTP server 或 monkeypatch，不使用真实网络。

验证：

1. base_url 正确。
2. model 正确。
3. Authorization header 正确。
4. request body 正确。
5. streaming 解析正确。
6. 错误分类正确。

### 17.6 MCP schema 测试

验证：

1. `hyperspace_query` 接受 provider。
2. `hyperspace_query` 接受 routing_strategy。
3. `hyperspace_query` 接受 expected_output。
4. `hyperspace_health` 存在。
5. 旧 mode 参数仍可用。

---

## 18. 安全与合规要求

### 18.1 密钥管理

要求：

1. API Key 只能从环境变量读取。
2. `.env.example` 只写变量名，不写真实值。
3. YAML 不写真实 API Key。
4. 测试不写真实 API Key。
5. 日志不写 API Key。
6. 错误信息不泄露 API Key。

### 18.2 用户提供的密钥处理

如果用户在对话、文件、配置中粘贴了真实 API Key：

1. 不在设计文档中记录该密钥。
2. 建议用户轮换该密钥。
3. 从项目中移除明文副本。
4. 使用环境变量替代。

### 18.3 文件上传

本阶段沿用现有文件上传行为，但 Router 和 MCP 返回 metadata 中应体现：

- 使用了哪个 provider。
- 是否发生 fallback。
- fallback 原因。

更细的文件沙箱、MIME 限制、路径白名单属于后续安全增强范围。

### 18.4 网页端自动化合规

本阶段不新增网页端自动化。

未来接入真实 ChatGLM Web / Qwen Chat Web 时，应明确：

1. 遵守平台服务条款。
2. 不使用破坏性、规避安全控制或绕过付费机制的技术。
3. 只支持用户主动登录后的本地自动化。
4. 提供关闭网页端自动化的配置开关。

---

## 19. 验收标准

### 19.1 功能验收

1. `hyperspace_query` 可以继续调用 DeepSeek Web。
2. `hyperspace_query(provider="deepseek_web")` 可以显式选择 DeepSeek Web。
3. `hyperspace_query(provider="siliconflow_nex_n2_pro")` 可以调用 SiliconFlow Nex-N2-Pro。
4. `hyperspace_query(provider="agnes_text")` 可以调用 Agnes 文本模型。
5. `hyperspace_query(provider="agnes_image")` 可以按 capability 参与图片任务路由。
6. `hyperspace_query(provider="chatglm_web")` 可以 fallback 到 Zhipu API。
7. `hyperspace_query(provider="qwen_chat_web")` 可以 fallback 到 Qwen API。
8. `hyperspace_health` 可以列出所有 provider 状态。
9. `HybridRouter` 不再直接 import `DeepSeekWebClient`。
10. 新增 provider 不需要改 Router 核心代码。

### 19.2 架构验收

1. Provider 能力由统一 interface 表达。
2. Provider 注册由 Registry 管理。
3. Router 只处理策略，不处理 provider 内部细节。
4. DeepSeek Web 逻辑被隔离在 provider adapter 内。
5. ChatGLM/Qwen Web 占位 provider 不阻塞架构扩展。
6. SiliconFlow、Agnes 通过通用 OpenAI-compatible provider 接入。
7. 所有 API Key 通过环境变量读取。

### 19.3 兼容性验收

1. 旧 `mode` 参数尽量可用。
2. 旧 DeepSeek Web 调用路径不破坏。
3. 旧配置文件尽量兼容。
4. 现有测试尽量通过，必要时迁移测试。
5. 新测试不依赖真实 API Key 或真实网络。

---

## 20. 风险与缓解

### 20.1 DeepSeek Web 迁移风险

风险：

- 迁移时破坏现有 DeepSeek Web 调用能力。

缓解：

- 先写 provider contract 和测试。
- DeepSeek Web 迁移尽量只做适配层，不改 PoW/SSE/文件上传核心逻辑。
- 保留旧模式兼容路径。

### 20.2 OpenAI-compatible provider 能力不一致风险

风险：

- SiliconFlow、Agnes 虽然都是 OpenAI-compatible，但实际支持的模型能力可能不同。

缓解：

- 用 capability 配置表达差异。
- 第一阶段不承诺未实测能力。
- 对 `agnes_image`、`agnes_video` 的能力标记为配置驱动，后续通过 smoke test 或人工验证修正。

### 20.3 免费 API 状态变化风险

风险：

- 平台可能从免费变为收费，或调整配额。

缓解：

- `cost_tier` 配置驱动。
- Router 不写死“永远免费”。
- health 和 usage metadata 记录实际调用结果。
- 用户可调整配置。

### 20.4 占位 provider 被误用风险

风险：

- 用户以为 ChatGLM Web/Qwen Chat Web 已经真实可用。

缓解：

- health 工具明确显示 `not_implemented`。
- fallback metadata 明确显示 fallback 原因。
- README 明确说明当前只是占位。

### 20.5 密钥泄露风险

风险：

- API Key 被写入代码、配置、日志或文档。

缓解：

- 所有 provider 使用 `enabled_env`。
- 测试禁止真实 key。
- 文档只写环境变量名。
- 发现明文密钥时建议轮换。

---

## 21. 后续扩展方向

本阶段完成后，后续可以继续推进：

1. 真实 ChatGLM Web provider。
2. 真实 Qwen Chat Web provider。
3. Proxy 模式统一到底层 ProviderRegistry。
4. LiteLLM Proxy 或 OpenRouter 思路接入。
5. 更完整的成本统计。
6. Cookie/token 加密存储。
7. 文件上传沙箱。
8. 更细的 MCP 工具拆分。
9. Provider health smoke test。
10. Agnes 图片/视频能力实测和 capability 修正。

---

## 22. 设计自检

### 22.1 Placeholder scan

本设计没有使用 `TBD` 作为核心需求。对于 ChatGLM Web、Qwen Chat Web、Agnes 图片/视频能力，已明确标注为占位或配置驱动，不假装已经实现。

### 22.2 Internal consistency

本设计与用户收缩后的范围一致：

- 第一阶段只做 DeepSeek Web 真实迁移。
- ChatGLM Web、Qwen Chat Web 只占位。
- SiliconFlow、Agnes 作为 OpenAI-compatible 免费 API provider 纳入资源池。
- Router 和 Registry 设计为多 provider 可扩展。

### 22.3 Scope check

本阶段聚焦于 Provider Registry、标准接口、Router、MCP 接口和 provider 适配，不扩展到 Proxy 统一、LangChain、真实 ChatGLM/Qwen Web 自动化。

### 22.4 Ambiguity check

已明确：

1. `auto` 不选择占位 provider。
2. 显式选择占位 provider 时允许 fallback。
3. 免费 API provider 通过通用 OpenAI-compatible provider 实现。
4. API Key 只通过环境变量读取。
5. DeepSeek Web 迁移放在 DeepSeek provider adapter 阶段完成，不在第一步重写。
