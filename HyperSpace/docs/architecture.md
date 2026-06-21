# HyperSpace 架构文档（v2.0 原生实现 · 2026-06-21）

## 目标

让本地 AI Agent（Reasonix / Claude Code / VS Code Copilot 等）优先调用 **DeepSeek Web（原生 Python 客户端，零成本）→ DeepSeek API（低成本）→ 智谱 GLM（免费兜底）** 的三层混合推理架构，将整体推理成本降低 70-90%。

## 设计原则

1. **合法优先**: 全部走厂商官方 OpenAI 兼容 API 或 Web 用户界面
2. **三层降级**: DeepSeek Web（原生客户端）→ DeepSeek API → 智谱 GLM，自动降级不中断
3. **零 token 路由**: 纯规则任务分析，不把路由决策外包给大模型
4. **配置驱动**: 所有路由规则和 executor 配置在 YAML，不改代码
5. **向后兼容**: 旧 mode（free_text/cheap_capable/premium）继续工作，不改已有代码
6. **自包含**: DeepSeek Web 客户端为独立 Python 实现（PoW 求解 + SSE 流），不依赖任何外部代理服务

## 架构总览

```
┌────────────┐     MCP stdio      ┌─────────────────────────────────────┐
│  Agent      │ ◄─────────────────►  HyperSpace Server (server.py)       │
│ (Reasonix / │   hyperspace_query └──────┬──────────────────────────────┘
│  ClaudeCode)│                           │
└────────────┘                     ┌──────┴──────────┐
                                  │  mode 判定       │
                                  │ force_web/api/   │
                                  │ zhipu → 混合引擎 │
                                  │ legacy → 旧路由   │
                                  └──────┬──────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────┐
         ▼                               ▼                       ▼
  ┌──────────────────┐         ┌───────────────────┐     ┌──────────────┐
  │ 混合引擎 (v2)    │         │ 旧路由 (v1)       │     │ experimental │
  │ HybridRouter     │         │ select_tier      │     │ (严格隔离)   │
  └──────┬───────────┘         └───────────────────┘     └──────────────┘
         │
    ┌────┴────┐
    │ Task    │
    │Analyzer │──→ 特征分析: 图片/搜索/规划/长文本/代码/翻译/结构化
    └────┬────┘
         │
    ┌────┴────┐
    │ Health  │──→ 健康探测: DeepSeek Web 凭据检查 + DeepSeek API 可达性
    │Checker  │    缓存 60s，智谱始终视为 available
    └────┬────┘
         │
    ┌────┴────┐
    │ Hybrid  │──→ 优先级规则 → 路由决策
    │ Router  │
    └────┬────┘
         │
         ├──── DeepSeek Web 原生客户端 → 直接调用 chat.deepseek.com 内部 API
         ├──── DeepSeek API (OpenAI 兼容) → api.deepseek.com
         └──── 智谱 GLM API → GLM-4.7-Flash / GLM-4.6V-Flash

    ┌────┴────┐
    │ Context │──→ 追踪 session 状态，≥85% 阈值自动压缩历史 → 新 session + 摘要注入
    │  Window │    连续失败检测（≥3 次触发降级）
    │ Manager │
    └────┬────┘
         │
    ┌────┴────┐
    │Fallback │──→ 降级链: DeepSeek Web → DeepSeek API → 智谱 GLM
    │Manager  │    指数退避重试: 0ms → 100ms → 200ms → 400ms
    └────┬────┘
         │
    ┌────┴────┐
    │ Result  │──→ 后处理: 提取 <thinking> 思维链, 分离最终答案
    │Processor│
    └─────────┘
```

## 核心组件

### 1. server.py（MCP 入口）

- 低级 `mcp` SDK（`from mcp.server import Server`），stdio 传输
- **双路径执行**:
  - `force_web` / `force_api` / `force_zhipu` / `auto` → 混合引擎（HybridRouter）
  - `free_text` / `free_vision` / `cheap_capable` / `premium` → 旧路由（select_tier + Executor）
- 唯一工具 `hyperspace_query(prompt, images?, context?, mode?, session_id?)`
- 启动诊断：逐档位输出可用候选、混合引擎状态、凭据状态、成本日志条目数

### 2. 混合引擎（hybrid_engine/）

#### 2.1 TaskAnalyzer（`task_analyzer.py`）

**输入**: `prompt` 字符串 + 可选 `images` / `context`
**输出**: `TaskProfile` 对象（含 `complexity_score` 属性）

判定维度（关键词+正则匹配，纯规则零 token）:

| 维度 | 判定方式 | 示例信号 |
|------|----------|----------|
| `has_image` | images 列表非空 | `images=["photo.jpg"]` |
| `is_long` | 字符 > 5000 | 长文档/大段代码 |
| `needs_search` | 关键词匹配 | "搜索"/"查找"/"最新"/"search"/"latest" |
| `needs_planning` | 关键词匹配 | "计划"/"方案"/"步骤"/"大纲"/"plan"/"strategy" |
| `needs_coding` | 代码围栏 + 关键词 | ` ``` `、`def `、`class `、`function `、"实现"/"fix" |
| `needs_translation` | 关键词匹配 | "翻译"/"译成"/"translate" |
| `needs_structured_output` | 关键词匹配 | "JSON"/"表格"/"CSV"/"XML"/"YAML" |

#### 2.2 HealthChecker（`health_checker.py`）

- DeepSeek Web：检查本地凭据文件（`data/deepseek_web_auth.json`）中 Cookie 是否含有效 session id
- DeepSeek API：异步探测 `https://api.deepseek.com/v1/models`（200/401 均视为可达）
- 智谱 GLM：始终视为 `available`（直接 API 调用，无需本地服务）
- 每 60 秒缓存结果，缓存过期前不重复探测
- 超时 5 秒

#### 2.3 DeepSeekWebClient（`deepseek_web_client.py`）🆕 核心创新

独立 Python 实现，直接调用 `chat.deepseek.com` 内部 API，**零外部依赖**:

- **PoW 求解**: SHA256 前导零位挑战，`solve_sha256_pow()` 自实现
- **流式对话**: SSE 流解析（`aiter_lines`），分离 `thinking` 和 `text` 事件
- **文件上传**: multipart 上传 + 轮询状态确认（最多 30 次，1s 间隔）
- **会话管理**: 自动创建/复用 `chat_session_id`
- **认证**: Cookie + Bearer Token，通过 `web_auth.py` 从 Chrome 提取

#### 2.4 ContextWindowManager（`context_window_manager.py`）🆕

DeepSeek Web 对话上下文管理器，保证多轮对话不因窗口满而断开:

- **状态追踪**: 每个 session 记录 message_count、estimated_tokens
- **自动压缩**: ≥85% 阈值时触发 → 调用压缩 API 生成摘要 → 创建新 session → 注入摘要
- **故障恢复**: 连续失败 ≥3 次触发 RuntimeError → FallbackManager 降级到下一执行器
- **无状态模式**: `session_key=""` 时每次新建 session

#### 2.5 WebAuth（`web_auth.py`）🆕

通过 Playwright CDP 从 Chrome 浏览器提取 DeepSeek Web 登录凭据:

- 连接 Chrome DevTools Protocol（`--remote-debugging-port=9222`）
- 提取 Cookie（含 `d_id` / `ds_session_id`）
- 拦截 API 请求获取 Bearer Token
- 支持已登录状态的快速提取和未登录时的等待登录流程

#### 2.6 HybridRouter（`hybrid_router.py`）

核心路由决策，优先级从高到低:

| 优先级 | 条件 | 路由 | 理由 |
|--------|------|------|------|
| 1 | `has_image` | DeepSeek Web | 原生识图，零成本 |
| 2 | `needs_search` | DeepSeek Web | 可联网搜索 |
| 3 | `needs_planning` | DeepSeek Web | 长文本规划，1M 上下文 |
| 4 | `is_long` | DeepSeek Web | 1M 上下文窗口 |
| 5 | `needs_coding` | DeepSeek API | API 输出代码更稳定 |
| 6 | `needs_translation` | DeepSeek API | 标准化翻译 |
| 7 | `needs_structured_output` | DeepSeek API | JSON 模式支持 |
| 8 | 默认 | DeepSeek Web | 经济优先 |

Force 模式覆盖:
- `force_web` → 强制 DeepSeek Web
- `force_api` → 强制 DeepSeek API
- `force_zhipu` → 强制智谱 GLM

#### 2.7 ResultProcessor（`result_processor.py`）

- 提取 `<thinking>` / `<details>` / `[思考]` 标签作为思维链
- 分离思维链与最终回答
- 标准化输出 `ProcessedResult {answer, plan, raw_response, used_executor, used_model}`

#### 2.8 FallbackManager（`fallback.py`）

- 降级链: `DeepSeek Web → DeepSeek API → 智谱 GLM → 友好错误`
- 瞬时错误（timeout/429/503/connection/ratelimit）→ 指数退避重试 0ms→100ms→200ms→400ms
- 持久错误（auth/401/403）→ 立即切下一 executor
- 记录完整错误链供诊断

### 3. 旧路由（router.py — 保留兼容）

```
select_tier(mode, images, prompt):
  if mode != AUTO → 强制该定级
  if images 存在   → FREE_VISION
  if _looks_complex(prompt) → CHEAP_CAPABLE
  else            → FREE_TEXT
```

### 4. Provider 层（`openai_compat.py` — 不变）

- 统一 OpenAI 兼容 client（智谱/DeepSeek/Kimi/OpenRouter 共用）
- 异常分类: RateLimitError / TransientError / AuthError / ProviderTimeout
- 图片处理：本地路径自动转 base64 data URL

### 5. 成本追踪（cost.py — 不变）

- 每次调用记录 `{ts, provider, model, tier, tokens, actual_cost, equivalent_premium, saved}`
- 写入 `data/hyperspace_cost.log`（JSONL）
- 工具命令：`python -m hyperspace.summary` / `python -m hyperspace.info`

## 配置体系

```
config/
├── providers.yaml             # 旧 tier → provider 映射
├── routing.yaml               # 旧路由规则
└── hybrid_config.yaml         # 混合引擎配置（routing 规则/executor/降级链/日志）
```

混合引擎配置 `hybrid_config.yaml`:

```yaml
routing:
  default_executor: "deepseek_web"
  fallback_order: ["deepseek_web", "deepseek_api", "zhipu"]
  rules:
    - condition: "has_image"            → executor: "deepseek_web"
    - condition: "needs_search"         → executor: "deepseek_web"
    - condition: "needs_planning"       → executor: "deepseek_web"
    - condition: "is_long"              → executor: "deepseek_web"
    - condition: "needs_coding"         → executor: "deepseek_api"
    - condition: "needs_translation"    → executor: "deepseek_api"
    - condition: "needs_structured_output" → executor: "deepseek_api"

executors:
  deepseek_web:
    model: "deepseek-chat"
    timeout: 120
    search_enabled: true
    thinking_enabled: true
  deepseek_api:
    provider: "deepseek"
    base_url: "https://api.deepseek.com"
    model: "deepseek-chat"
    timeout: 60
  zhipu:
    provider: "zhipu"
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4.7-flash"
    timeout: 30
```

## 凭据管理

DeepSeek Web 凭据通过 Playwright CDP 从 Chrome 提取，保存到 `data/deepseek_web_auth.json`（gitignored）:

```bash
# 以调试模式启动 Chrome
chrome.exe --remote-debugging-port=9222
# 登录 chat.deepseek.com 后提取凭据
python -m hyperspace.hybrid_engine.web_auth --extract
# 查看凭据状态
python -m hyperspace.hybrid_engine.web_auth --status
```

API Key 从 `.env` 读取:
- `ZHIPU_API_KEY` — 免费档必填（智谱 GLM-4.7-Flash / GLM-4.6V-Flash）
- `DEEPSEEK_API_KEY` — 廉价档推荐（DeepSeek API）
- `MOONSHOT_API_KEY` — 廉价档备选（Kimi）

## 安全与隔离

| 区域 | 内容 | 是否接入 MCP | 是否可开源 |
|------|------|-------------|-----------|
| `hyperspace/` 核心 | 合法 API 路由器 | ✓ | ✓ MIT |
| `hyperspace/hybrid_engine/` | 混合引擎（原生实现） | ✓（auto/force 模式） | ✓ MIT |
| `hyperspace/experimental/` | 浏览器自动化（违 ToS） | **否** | **否**（仅个人） |

## 测试策略

- `tests/test_router.py`: 旧路由规则测试，零网络，16 用例
- `tests/test_providers.py`: Provider 异常 + 回退链，mock 测试，9 用例
- `tests/test_hybrid_engine.py`: 混合引擎测试，39 用例
  - TaskAnalyzer: 13 用例（各类特征判定）
  - HybridRouter: 14 用例（路由决策、force 模式、优先级）
  - FallbackManager: 5 用例（降级链、重试、异常分类）
  - ResultProcessor: 7 用例（思维链提取、纯文本、空响应）

全部测试纯单元测试，零网络零 key，mock 全部外部调用。运行命令：`pytest tests/ -v`（64/64 全绿）。

## 诚实口径

- **不说"省 90%"**。成本日志真实显示: N% 请求走 Web 端免费，M% API 低成本，等效节省 ¥XX
- 节省比例因使用模式而异，以 `data/hyperspace_cost.log` 实测为准
