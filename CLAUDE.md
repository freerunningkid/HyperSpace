# HyperSpace v2.1 项目上下文（2026-06-25 · Skill + CLI）

## 项目概述
HyperSpace 是一个 **Agent Skill + CLI 工具**，为本地 AI Agent（Claude Code / CodeWhale / Reasonix）提供多层混合推理路由：
**DeepSeek Web（原生 Python 客户端，¥0）→ DeepSeek API（低成本）→ 智谱 GLM（免费兜底）→ 多 Provider**

核心创新：不依赖 OpenClaw / FreeLLMAPI 等外部服务。独立实现 DeepSeek Web 内部 API 完整调用链（PoW 求解、SSE 流、文件上传、会话管理、**自动凭据刷新**），零外部依赖。

## 技术栈
- Python 3.10+
- 异步：asyncio + httpx
- Playwright：自动凭据提取（Cookie 注入 + Bearer 拦截，非 CDP 依赖）
- 配置格式：YAML + .env
- 测试：pytest + pytest-asyncio（asyncio_mode = auto）
- Skill 注册：`<user>/.claude/skills/hyperspace/SKILL.md`

## 核心架构（三级降级链）
```
Agent (Skill) → hyperspace ask <prompt>
                  │
            HybridRouter
              ├─ TaskAnalyzer → 7 维特征分析（纯规则，零 token）
              ├─ HealthChecker → 异步健康探测（60s 缓存）
              ├─ WebAuth → 自动凭据提取/刷新（CDP → Playwright → Chrome 启动）
              ├─ FallbackManager → 降级链 + 指数退避（100ms→200ms→400ms）
              └─ ResultProcessor → 思维链提取 + 标准化输出
                  │
            ┌─────┼─────┐
       deepseek_web  deepseek_api  zhipu
       (原生客户端)  (OpenAI兼容)   (OpenAI兼容)
```

## 路由铁律（不可违背）
- `has_image` / `needs_search` / `needs_planning` / `is_long` → **DeepSeek Web（原生客户端）**
- `needs_coding` / `needs_translation` / `needs_structured_output` → **DeepSeek API**
- 默认（简单问答/闲聊）→ **DeepSeek Web（经济优先）**
- 降级链严格按照 DeepSeek Web → DeepSeek API → 智谱 GLM 顺序

## 关键模块与职责

| 模块 | 职责 | 文件 |
|------|------|------|
| **CLI 入口** | ask/chat/info/summary 命令，Skill 触发入口 | `hyperspace/cli.py` |
| **HybridRouter** | 核心路由决策（8 级优先级），自动凭据初始化和刷新，force 模式覆盖 | `hyperspace/hybrid_engine/hybrid_router.py` |
| **TaskAnalyzer** | 任务特征提取：has_image, needs_search, needs_planning, is_long, needs_coding, needs_translation, needs_structured_output | `hyperspace/hybrid_engine/task_analyzer.py` |
| **DeepSeekWebClient** | 原生 Python 客户端：PoW 求解（SHA256 前导零位）、SSE 流解析、文件上传+轮询、session 管理、verify_auth（检查 body code==0） | `hyperspace/hybrid_engine/deepseek_web_client.py` |
| **ContextWindowManager** | 上下文窗口追踪（≥85% 触发压缩），自动压缩历史→创建新 session→注入摘要 | `hyperspace/hybrid_engine/context_window_manager.py` |
| **WebAuth** | 🆕 三级自动凭据提取：CDP → Playwright Cookie 注入 → Chrome 启动。Bearer 缺失时 `HybridRouter._init_web_client` 自动触发刷新 | `hyperspace/hybrid_engine/web_auth.py` |
| **HealthChecker** | 异步探测 Web/API 可用性，60s 缓存，智谱始终视为 available | `hyperspace/hybrid_engine/health_checker.py` |
| **FallbackManager** | 降级链遍历，瞬时错误指数退避重试，异常分类（timeout/429/503/auth/connection） | `hyperspace/hybrid_engine/fallback.py` |
| **ResultProcessor** | 提取 `<thinking>` / `[思考]` 标签作为思维链，分离最终回答 | `hyperspace/hybrid_engine/result_processor.py` |
| **OpenAICompatProvider** | 统一 OpenAI 兼容客户端（智谱/DeepSeek/Kimi/OpenRouter），异常分类 | `hyperspace/providers/openai_compat.py` |
| **旧路由层** | select_tier + Executor（保留兼容 legacy mode） | `hyperspace/router.py` + `hyperspace/executor.py` |
| **成本追踪** | JSONL 写入 data/hyperspace_cost.log | `hyperspace/cost.py` |
| **系统信息** | `hyperspace info` 查看档位/Key/成本快照 | `hyperspace/info.py` |
| **成本摘要** | `hyperspace summary` 统计展示 | `hyperspace/summary.py` |

## 凭据自动刷新机制（2026-06-25 新增）

三级策略，零手动：
1. **CDP** — 如果 Chrome 以 `--remote-debugging-port=9222` 运行，直接连接提取
2. **Playwright Cookie 注入** — 注入已有 Cookie → 导航 chat.deepseek.com → 拦截 API 请求捕获 Bearer Token。不依赖 CDP，Chrome 正在运行也能用
3. **Chrome 启动** — 复制 Default profile → 启动 Chrome → CDP 提取（需 Chrome 空闲）

`HybridRouter._init_web_client()` 发现 Bearer 缺失时自动调用 `web_auth.auto_extract_sync()`。

## Cookie 兼容性
- `d_id=` — 旧版 DeepSeek 会话标识 ✅
- `ds_session_id=` — 新版会话标识 ✅（2026-06-25 修复，is_auth_valid / DeepSeekAuth.is_valid / extract_from_browser 均已兼容）

## verify_auth 修复
- 旧逻辑：仅检查 `resp.status_code == 200` → 假阳性（API 返回 200 + `{"code":40002,"msg":"Missing Token"}`）
- 新逻辑：检查 `resp.status_code == 200` **且** `data.get("code") == 0`

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/hybrid_config.yaml` | 混合引擎配置（routing 规则/executor 参数/降级链/日志） |
| `.env` | API Key（ZHIPU_API_KEY 必填，DEEPSEEK_API_KEY 推荐） |
| `data/deepseek_web_auth.json` | 🆕 DeepSeek Web 登录凭据（cookie + bearer，gitignored，自动刷新） |
| `data/hyperspace_cost.log` | 成本日志 JSONL（gitignored） |

## 测试要求
- 现有 **225 个测试**，必须保持全绿。
- 所有测试为纯单元测试，零网络零 key，mock 全部外部调用。
- `test_deepseek_web_client.py`（58 用例）：Auth(8) + Headers(3) + PowChallenge(3) + LeadingZeroBits(5) + SolvePow(4) + ClientHelpers(3) + CreatePowChallenge(4) + CreateSession(4) + ParseSSE(7) + ChatCompletion(3) + UploadFile(5) + ChatConvenience(2) + VerifyAuth(7)

## 代码禁区
- **严禁修改** `hyperspace/experimental/` 目录下的任何代码（个人实验区，严格隔离）。
- **严禁修改** `hyperspace/providers/openai_compat.py` 的底层接口签名（除非明确允许）。
- **严禁硬编码密钥**，所有 API Key 必须从 `.env` 读取。

## 常用命令
```bash
# 运行全部测试
pytest tests/ -v

# 自动提取/刷新 DeepSeek Web 凭据（零手动）
python -m hyperspace.hybrid_engine.web_auth --auto

# 查看凭据状态
python -m hyperspace.hybrid_engine.web_auth --status

# 手动凭据提取（需 Chrome 调试模式）
python -m hyperspace.hybrid_engine.web_auth --extract

# CLI 一问一答
python -m hyperspace.cli ask "你好"

# 系统信息
python -m hyperspace.info

# 成本摘要
python -m hyperspace.summary
```

## 设计原则
1. **合法优先**：全部走厂商官方 API 或 Web 用户界面
2. **零 token 路由**：纯规则任务分析，路由决策不消耗 token
3. **配置驱动**：路由规则和 executor 配置在 YAML，不硬编码
4. **自动凭据**：Bearer Token 自动提取+刷新，不依赖用户手动操作
5. **诚实口径**：成本日志记录实际数据
