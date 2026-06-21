# HyperSpace 架构文档

## 目标

让本地 AI Agent（Reasonix / ClaudeCode / VS Code Copilot 等）优先调用**厂商官方免费/廉价云端大模型 API**，仅高精度任务走付费 API，将整体推理成本降低 70-90%。

## 设计原则

1. **合法优先**: 全部走厂商官方 OpenAI 兼容 API，不爬网页聊天界面
2. **配置驱动**: 厂商/model/base_url 全在 YAML，不改代码
3. **廉价规则路由**: 零 token 成本的任务复杂度判定，不把路由决策外包给大模型
4. **回退防脆弱**: 限流/网络/鉴权失败自动降级/升档
5. **严格隔离**: experimental 个人实验模块不接入 MCP，不参与核心流程

## 架构总览

```
┌────────────┐     MCP stdio      ┌─────────────────────────────────┐
│  Agent      │ ◄──────────────────►  HyperSpace MCP Server         │
│ (Reasonix / │   tools/list       │  hyperspace_query(prompt, …)   │
│  ClaudeCode)│   tools/call       └──────────┬──────────────────────┘
└────────────┘                                │
                                              │ select_tier()
                                              ▼
                                    ┌──────────────────────────┐
                                    │  Router (router.py)       │
                                    │  mode/AUTO?               │
                                    │  images? → FREE_VISION    │
                                    │  complex? → CHEAP_CAPABLE │
                                    │  default → FREE_TEXT      │
                                    └──────────┬───────────────┘
                                              │
                                              ▼
                                    ┌──────────────────────────┐
                                    │  Executor (executor.py)   │
                                    │  按 tier 依次尝试候选     │
                                    │  失败→下一候选→升档       │
                                    └──────────┬───────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────┐
                    ▼                         ▼                     ▼
            ┌─────────────┐        ┌──────────────┐       ┌────────────┐
            │ 免费文本     │        │ 免费识图      │       │ 廉价能力   │
            │ glm-4.7-    │        │ glm-4.6v-     │       │ deepseek-  │
            │ flash       │        │ flash        │       │ chat       │
            │ (智谱,免费) │        │ (智谱,免费)  │       │ ($0.27/M)  │
            └─────────────┘        └──────────────┘       └────────────┘
```

## 核心组件

### 1. server.py (MCP 入口)

- 低级 `mcp` SDK (`from mcp.server import Server`)，stdio 传输
- 唯一工具 `hyperspace_query(prompt, images?, context?, mode?)`
- 对齐 os-safe/voice 等现有 MCP 服务启动规范

### 2. 路由算法 (router.py)

```
select_tier(mode, images, prompt):
  if mode != AUTO → 强制该定级
  if images存在   → FREE_VISION
  if _looks_complex(prompt) → CHEAP_CAPABLE
  else            → FREE_TEXT
```

复杂度判定 (零 token 成本):
- 含代码标记 (` ``` `, `def `, `class `, `function `)
- 含复杂关键词 (重构/实现/调试/分析/refactor/implement...)
- 长度超过阈值 (默认 800 字符)
- 以上规则全部在 `config/routing.yaml` 可调

### 3. Provider 层 (openai_compat.py)

- 统一 OpenAI 兼容 client（智谱/DeepSeek/Kimi/OpenRouter 共用）
- 异常分类:
  - `RateLimitError` (429) → 回退下一候选
  - `TransientError` (网络/500 级) → 回退
  - `AuthError` (401/403) → 跳过该 provider
  - `ProviderTimeout` → 回退
- 图片处理: 本地路径 → data URL, http URL 原样传, 直接粘贴 base64

### 4. Executor (executor.py)

按 `tier → candidates → fallback → escalation` 链执行：
```
for tier in [requested_tier, ...escalation_chain]:
  for candidate in cfg.candidates_for(tier):
    try: return await candidate.chat(prompt, images)
    except ProviderError: continue
raise ProviderError("所有候选均失败")
```

### 5. 成本追踪 (cost.py)

- 每次调用记录 `{ts, provider, model, tier, tokens, actual_cost, equivalent_premium, saved}`
- 写入 `data/hyperspace_cost.log` (JSONL)
- 以 Claude/GPT premium 价为等效基线估算节省

## 配置体系

```
config/
├── providers.yaml    # tier → 有序候选 (provider, base_url, model, key_env)
└── routing.yaml      # 路由规则 (复杂度关键词/长度/升档链)
```

- 加新 provider: `providers.yaml` 加一行 + `.env` 加 key
- 调路由规则: 改 `routing.yaml`，不改代码

## 安全与隔离

| 区域 | 内容 | 是否接入 MCP | 是否可开源 |
|------|------|-------------|-----------|
| `hyperspace/` 核心 | 合法 API 路由器 | ✓ | ✓ MIT |
| `hyperspace/experimental/` | 浏览器自动化 (违 ToS) | **否** | **否** (仅个人) |

## 测试策略

- `tests/test_router.py`: 纯规则测试，零网络零 key，16 个用例
- `tests/test_providers.py`: mock 测试，不打真实 API，验证异常分类 + 回退链，9 个用例

## 诚实口径

- **不说 "省 90%"**。成本日志真实显示: N% 请求免费档, M% 廉价档, 等效节省 ¥XX
- 节省比例因使用模式而异，以 `data/hyperspace_cost.log` 实测为准
