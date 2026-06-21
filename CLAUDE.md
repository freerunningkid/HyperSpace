# HyperSpace v2.0 项目上下文（2026-06-21 最新版 · 原生实现）

## 项目概述
HyperSpace 是一个 MCP stdio 服务，为本地 AI Agent（Claude Code / Reasonix / VS Code Copilot）提供三层混合推理路由：
**DeepSeek Web（原生 Python 客户端，零成本）→ DeepSeek API（低成本）→ 智谱 GLM（免费兜底）**

核心创新：不依赖 OpenClaw / FreeLLMAPI 等外部服务。独立实现了 DeepSeek Web 内部 API 的完整调用链（PoW 求解、SSE 流、文件上传、会话管理），零外部依赖。

## 技术栈
- Python 3.10+
- 异步：asyncio + httpx
- 可选依赖：playwright（仅用于 Chrome CDP 凭据提取）
- MCP 协议：低级 `mcp.server.stdio`（非 FastMCP）
- 配置格式：YAML + .env
- 测试：pytest + pytest-asyncio（asyncio_mode = auto）

## 核心架构（三层降级链）
```
Agent (MCP) → server.py
                ├─ auto / force_web / force_api / force_zhipu → HybridRouter (v2)
                └─ free_text / free_vision / cheap_capable / premium → 旧路由 (v1 兼容)
                       │
              HybridRouter
                ├─ TaskAnalyzer → 7 维特征分析（纯规则，零 token）
                ├─ HealthChecker → 异步健康探测（60s 缓存）
                ├─ FallbackManager → 降级链 + 指数退避（100ms→200ms→400ms）
                └─ ResultProcessor → 思维链提取 + 标准化输出
                       │
              ┌────────┼────────┐
         deepseek_web  deepseek_api  zhipu
         (原生客户端)   (OpenAI兼容)  (OpenAI兼容)
```

## 路由铁律（不可违背）
- `has_image` / `needs_search` / `needs_planning` / `is_long` → **DeepSeek Web（原生客户端）**
- `needs_coding` / `needs_translation` / `needs_structured_output` → **DeepSeek API**
- 默认（简单问答/闲聊）→ **DeepSeek Web（经济优先）**
- 降级链严格按照 DeepSeek Web → DeepSeek API → 智谱 GLM 顺序

## 关键模块与职责

| 模块 | 职责 | 文件 |
|------|------|------|
| **MCP 入口** | stdio 传输，双路径分发（混合引擎 + 旧路由），启动诊断 | `hyperspace/server.py` |
| **TaskAnalyzer** | 任务特征提取：has_image, needs_search, needs_planning, is_long, needs_coding, needs_translation, needs_structured_output | `hyperspace/hybrid_engine/task_analyzer.py` |
| **HybridRouter** | 核心路由决策（8 级优先级），force 模式覆盖，配置加载与合并 | `hyperspace/hybrid_engine/hybrid_router.py` |
| **DeepSeekWebClient** | 原生 Python 客户端：PoW 求解（SHA256 前导零位）、SSE 流解析、文件上传+轮询、session 管理 | `hyperspace/hybrid_engine/deepseek_web_client.py` |
| **ContextWindowManager** | 上下文窗口追踪（≥85% 触发压缩），自动压缩历史→创建新 session→注入摘要，连续失败检测 | `hyperspace/hybrid_engine/context_window_manager.py` |
| **WebAuth** | 通过 Playwright CDP 提取 Chrome 中 chat.deepseek.com 的 Cookie + Bearer Token | `hyperspace/hybrid_engine/web_auth.py` |
| **HealthChecker** | 异步探测 Web/API 可用性，60s 缓存，智谱始终视为 available | `hyperspace/hybrid_engine/health_checker.py` |
| **FallbackManager** | 降级链遍历，瞬时错误指数退避重试，异常分类（timeout/429/503/auth/connection） | `hyperspace/hybrid_engine/fallback.py` |
| **ResultProcessor** | 提取 `<thinking>` / `[思考]` 标签作为思维链，分离最终回答 | `hyperspace/hybrid_engine/result_processor.py` |
| **OpenAICompatProvider** | 统一 OpenAI 兼容客户端（智谱/DeepSeek/Kimi/OpenRouter），异常分类 | `hyperspace/providers/openai_compat.py` |
| **旧路由层** | select_tier + Executor（保留兼容 legacy mode），含回退/升档链 | `hyperspace/router.py` + `hyperspace/executor.py` |
| **成本追踪** | JSONL 写入 data/hyperspace_cost.log，含等效节省计算 | `hyperspace/cost.py` |
| **系统信息** | `python -m hyperspace.info` 查看档位/Key/成本快照 | `hyperspace/info.py` |
| **成本摘要** | `python -m hyperspace.summary` 统计展示 | `hyperspace/summary.py` |

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/providers.yaml` | 旧 tier → provider 映射（free_text/free_vision/cheap_capable/premium） |
| `config/routing.yaml` | 旧路由规则（code_markers/complex_keywords/length_threshold/escalation_chain） |
| `config/hybrid_config.yaml` | 混合引擎配置（routing 规则/executor 参数/降级链/日志） |
| `.env` | API Key（ZHIPU_API_KEY 必填，DEEPSEEK_API_KEY 推荐） |
| `data/deepseek_web_auth.json` | DeepSeek Web 登录凭据（gitignored，由 web_auth --extract 生成） |
| `data/hyperspace_cost.log` | 成本日志 JSONL（gitignored） |

## 测试要求
- 现有 **202 个测试**（64 旧 + 138 新），必须保持全绿。
- 所有测试为纯单元测试，零网络零 key，mock 全部外部调用。
- `test_router.py`（16 用例）：旧路由规则、复杂度判定、边界
- `test_providers.py`（9 用例）：异常分类、回退/升档链
- `test_hybrid_engine.py`（39 用例）：TaskAnalyzer(13) + HybridRouter(14) + FallbackManager(5) + ResultProcessor(7)
- `test_deepseek_web_client.py`（57 用例）：🆕 Auth(8) + Headers(3) + PowChallenge(3) + LeadingZeroBits(5) + SolvePow(4) + ClientHelpers(3) + CreatePowChallenge(4) + CreateSession(4) + ParseSSE(7) + ChatCompletion(3) + UploadFile(5) + ChatConvenience(2) + VerifyAuth(6)
- `test_context_window_manager.py`（45 用例）：EstimateTokens(6) + SessionState(2) + Init(3) + FirstMessage(6) + StatelessMode(2) + MultiTurn(4) + CompressionTrigger(5) + SummaryInjection(4) + ConsecutiveFailures(3) + SessionStateMgmt(7) + Constants(3)
- `test_health_checker.py`（36 用例）：ServiceStatus(2) + HealthResult(2) + Init(2) + ProbeWeb(8) + ProbeApi(8) + CheckAll(4) + CacheMechanism(6) + Concurrency(1) + BuildResult(3)

## 代码禁区
- **严禁修改** `hyperspace/experimental/` 目录下的任何代码（个人实验区，严格隔离）。
- **严禁修改** `hyperspace/providers/openai_compat.py` 的底层接口签名（除非明确允许）。
- **严禁硬编码密钥**，所有 API Key 必须从 `.env` 读取。

## 已知问题（待处理）
1. **`web_auth.py:26`** — `_PKG_DIR` 计算路径为三级 `.parent`，逻辑正确但脆弱（注释说明即可）

## 常用命令
```bash
# 运行全部测试
pytest tests/ -v

# 提取 DeepSeek Web 凭据（需 Chrome 调试模式：chrome.exe --remote-debugging-port=9222）
python -m hyperspace.hybrid_engine.web_auth --extract

# 查看凭据状态
python -m hyperspace.hybrid_engine.web_auth --status

# 系统信息
python -m hyperspace.info

# 成本摘要
python -m hyperspace.summary

# 启动 MCP 服务（通常由 Agent 自动启动）
python hyperspace/server.py
```

## 设计原则
1. **合法优先**：全部走厂商官方 API 或 Web 用户界面
2. **零 token 路由**：纯规则任务分析，路由决策不消耗 token
3. **配置驱动**：路由规则和 executor 配置在 YAML，不硬编码
4. **向后兼容**：旧 mode（free_text/cheap_capable/premium）继续工作
5. **诚实口径**：成本日志说实际数据，不预设"省 90%"宣传数字
