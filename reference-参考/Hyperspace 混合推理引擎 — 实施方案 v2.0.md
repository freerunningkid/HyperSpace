
## Hyperspace 混合推理引擎 — 实施方案 v2.0


我最初想法是： 项目名称HyperSpace，将“网页端大模型（如 DeepSeek Web）”作为廉价/免费的推理资源，与本地 Agent（Reasonix/ClaudeCode/Copilot）深度整合，实现“API 调用降本增效”。构建一个 “网页端推理优先” 的混合架构，做一个合法的MCP 服务，让本地 Agent（Reasonix、ClaudeCode、Copilot 等）在绝大多数场景下优先调用厂商大模型的 Web 端对话能力（免费/低成本），仅在极少数高精度、高控制需求的关键环节才触发付费 API 调用。通过这种方式，将整体 Token 消耗成本降低 70%-90%，同时充分利用网页端的识图、长文本等原生能力。不用本地大模型。 后来Agent做出的项目优先采用了智谱 GLM-4.7-Flash、 GLM-4.6V-Flash，没有达到我预期的效果，我想要智谱 GLM-4.7-Flash、 GLM-4.6V-Flash这两个大模型只是兜底而已；日常的问答和复杂任务，有判定原则（api调用和DeepSeek 网页端相辅相成，互补互助，具体遇到的任务各类复杂情况、各种环节，都要预先设定好判定条件交给谁做，以及网页端做完反馈的内容agent如何抓取的相关技术），主力仍是api调用和DeepSeek 网页端；

> **核心目标**：构建以 DeepSeek 生态为绝对主力的双引擎推理架构。DeepSeek 网页端（规划/研究/识图/长文）和 DeepSeek API（执行/代码/翻译）各司其职，智谱 GLM-4.7-Flash / 4.6V-Flash 仅作最后兜底。

---

### 一、架构总览

```
本地 Agent (Reasonix / ClaudeCode)
   │
   ▼
Hyperspace MCP Server (hyperspace_query)
   │
   ▼
┌──────────────────────────────────────────────┐
│          HybridRouter (混合路由器)            │
│                                              │
│  任务分析 → 服务健康检查 → 路由决策 → 执行    │
└──────┬───────────────────────┬───────────────┘
       │                       │
       ▼                       ▼
┌──────────────┐    ┌──────────────────────┐
│  OpenClaw    │    │    FreeLLMAPI         │
│  Zero Token  │    │  (DeepSeek API 主力)  │
│              │    │  (Gemini/Claude 备选)  │
│ DeepSeek Web │    └──────────┬───────────┘
│ 规划/搜索/识图│               │
└──────────────┘               │
       │                       │
       └───────────┬───────────┘
                   │ (两者都不可用时)
                   ▼
         ┌─────────────────┐
         │  智谱 GLM API   │
         │  4.7/4.6V-Flash │  ← 最后兜底
         └─────────────────┘
```

**三层降级链**：`DeepSeek Web (OpenClaw) ↔ DeepSeek API (FreeLLMAPI) → 智谱 GLM (兜底)`

---

### 二、工具选型与职责

| 工具 | 在架构中的角色 | 核心用途 |
|------|---------------|----------|
| **OpenClaw Zero Token** | DeepSeek 网页端引擎 | 将网页登录转为 OpenAI 兼容 API；负责规划、搜索、识图、长文 |
| **FreeLLMAPI** | API 聚合引擎 | 聚合 DeepSeek API + 其他免费 API；负责代码生成、翻译、结构化输出 |
| **智谱 GLM-4.7-Flash / 4.6V-Flash** | 最后兜底 | 前两者都不可用时的保险 |

> **现有 `hyperspace/` 核心代码** 将被重构：`router.py` 和 `executor.py` 需重写为新的 `HybridRouter`；`providers/openai_compat.py` 保留用于对接 OpenClaw 和 FreeLLMAPI 的 OpenAI 兼容接口。

---

### 三、项目实施阶段

#### 阶段 0：环境准备（1天）

**0.1 基础依赖**
```bash
# Node.js >= 22.12.0（OpenClaw 和 FreeLLMAPI 需要）
# pnpm >= 9.0.0
# Chrome 浏览器
```

**0.2 克隆并构建 OpenClaw Zero Token**
```bash
git clone https://github.com/linuxhsj/openclaw-zero-token.git
cd openclaw-zero-token
npm install
npm run build
pnpm ui:build          # 必须执行，否则 Web 界面不可用
```

**0.3 克隆并构建 FreeLLMAPI**
```bash
git clone https://github.com/tashfeenahmed/freellmapi
cd freellmapi
npm install
cp .env.example .env
```

**0.4 安装 Playwright（Hyperspace 已有依赖，确认即可）**
```bash
pip install playwright
playwright install chromium
```

---

#### 阶段 1：启动与认证配置（1天）

**1.1 启动 Chrome 调试模式并登录**
```bash
# 在 OpenClaw 目录下
./start-chrome-debug.sh
# 会打开带远程调试端口的 Chrome 窗口
```
在调试模式的 Chrome 中手动登录 `chat.deepseek.com`。

**1.2 运行 OpenClaw 配置向导**
```bash
./onboard.sh
```
按提示选择 `deepseek-web`，向导会自动抓取登录凭证并加密存储。

**1.3 配置 FreeLLMAPI**
编辑 `.env`，填入各平台 API Key：
```env
DEEPSEEK_API_KEY=你的key
GOOGLE_API_KEY=你的key    # 可选
GROQ_API_KEY=你的key      # 可选
# ... 其他平台按需
```
访问 `localhost:5173` 管理面板验证。

**1.4 启动服务**
```bash
# 终端1：启动 OpenClaw
cd openclaw-zero-token && ./server.sh start
# 验证：curl http://localhost:3000/health

# 终端2：启动 FreeLLMAPI
cd freellmapi && npm run dev
# 验证：curl http://localhost:3001/health
```

---

#### 阶段 2：Hyperspace 核心重构（2-3天）

重构现有的 `D:\Reasonix\HyperSpace\` 项目，新增以下模块：

**2.1 新增模块结构**
```
hyperspace/
├── hybrid_engine/           # 新：混合推理引擎
│   ├── __init__.py
│   ├── task_analyzer.py     # 任务特征分析
│   ├── health_checker.py    # 服务健康检查
│   ├── hybrid_router.py     # 核心路由决策
│   ├── result_processor.py  # 网页端结果提取
│   └── fallback.py          # 降级与重试管理
├── server.py                # 修改：调用 hybrid_engine
├── config.py                # 修改：新增引擎配置加载
└── ...
config/
└── hybrid_config.yaml       # 新：引擎配置文件
```

**2.2 核心模块设计规格**

**`task_analyzer.py` — 任务特征分析器**
- 输入：原始 `prompt` 字符串 + 可选 `context`（图片、历史等）
- 输出：`TaskProfile` 对象
- 判定维度：
  - `is_long`: 长度 > 5000 字符
  - `needs_search`: 含 "搜索""查找""最新" 等关键词
  - `needs_planning`: 含 "计划""方案""步骤""大纲" 等
  - `needs_coding`: 含 "代码""函数""debug""实现" 等
  - `needs_translation`: 含 "翻译""译成" 等
  - `has_image`: context 中有图片数据
  - `needs_structured_output`: 要求 JSON/表格格式
- 实现方式：先用关键词匹配 + 正则规则，后续可升级分类器

**`health_checker.py` — 服务健康检查**
- 定期探测 OpenClaw (`localhost:3000/health`) 和 FreeLLMAPI (`localhost:3001/health`)
- 探测频率：每 60 秒
- 缓存结果，带过期时间
- 输出 `ServiceStatus`：可用/不可用、延迟、限流状态

**`hybrid_router.py` — 核心路由决策**
- 决策规则（优先级从高到低）：
  1. `has_image` → OpenClaw (DeepSeek Web 原生识图)
  2. `needs_search` → OpenClaw (网页端可开启联网搜索)
  3. `needs_planning` → OpenClaw (长文本规划能力强)
  4. `is_long` → OpenClaw (1M 上下文窗口)
  5. `needs_coding` → FreeLLMAPI (API 输出代码更稳定)
  6. `needs_translation` → FreeLLMAPI
  7. `needs_structured_output` → FreeLLMAPI (支持 JSON 模式)
  8. 默认（简单问答/闲聊）→ OpenClaw（经济优先）
- 降级链：`OpenClaw → FreeLLMAPI → 智谱 API → 错误提示`
- 输出 `RoutingDecision`：执行器、模型、参数、降级链

**`result_processor.py` — 网页端结果提取**
- 处理 OpenClaw 返回的原始内容
- 提取逻辑：
  - 若返回 HTML，查找 `<thinking>` 或 `details` 标签作为思维链
  - 其余内容作为最终答案
  - 若为纯文本，整体作为答案
- 输出 `ProcessedResult`：`plan`（思维链）、`answer`（最终回复）

**`fallback.py` — 降级与重试**
- 异常分类：超时、HTTP 429/500/503、空响应
- 降级策略：按降级链依次尝试
- 重试：临时错误等待指数退避（100ms → 200ms → 400ms）
- 全部失败返回友好错误信息

**2.3 配置文件 `config/hybrid_config.yaml`**
```yaml
routing:
  default_executor: "openclaw"
  fallback_order: ["openclaw", "freellmapi", "zhipu"]
  rules:
    - condition: "has_image"
      executor: "openclaw"
    - condition: "needs_search"
      executor: "openclaw"
    - condition: "needs_planning"
      executor: "openclaw"
    - condition: "is_long"
      executor: "openclaw"
    - condition: "needs_coding"
      executor: "freellmapi"
    - condition: "needs_translation"
      executor: "freellmapi"
    - condition: "needs_structured_output"
      executor: "freellmapi"

executors:
  openclaw:
    base_url: "http://localhost:3000/v1"
    timeout: 120
    model: "deepseek-web/deepseek-chat"
    health_url: "http://localhost:3000/health"
  freellmapi:
    base_url: "http://localhost:3001/v1"
    timeout: 60
    models: ["deepseek-chat", "gemini-2.5-flash"]
    health_url: "http://localhost:3001/health"
  zhipu:
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    timeout: 30
    model: "glm-4.7-flash"

workflow:
  enable_complex_decomposition: true
  max_subtasks: 5
  subtask_timeout: 90

logging:
  level: "INFO"
  output: "data/hybrid_engine.log"
```

---

#### 阶段 3：MCP 服务端适配（1天）

修改 `hyperspace/server.py`，将原有 `executor` 替换为新的 `HybridRouter`：

```python
# server.py 核心逻辑
from hyperspace.hybrid_engine import HybridRouter

router = HybridRouter(config_path="config/hybrid_config.yaml")

@server.call_tool()
async def call_tool(name, arguments):
    prompt = arguments["prompt"]
    images = arguments.get("images")
    context = arguments.get("context")
    
    result = await router.execute(prompt, images=images, context=context)
    
    return [types.TextContent(
        type="text",
        text=result.answer + result.metadata_text
    )]
```

---

#### 阶段 4：集成测试（1天）

**测试用例与预期行为：**

| 测试场景 | 输入 | 预期路由 | 预期行为 |
|----------|------|----------|----------|
| 简单问答 | "今天天气如何？" | OpenClaw | 返回回复 |
| 长文本分析 | 10000 字符论文 | OpenClaw | 利用长上下文分析 |
| 代码生成 | "用 Python 写快速排序" | FreeLLMAPI | 输出可运行代码 |
| 图像识别 | 附图片 + "这是什么？" | OpenClaw | 网页端识图 |
| 代码重构 | "重构这段代码，先给计划" | OpenClaw(规划) + FreeLLMAPI(执行) | 协同流水线 |
| OpenClaw 不可用 | 服务未启动 | FreeLLMAPI | 自动降级 |
| 全不可用 | 所有服务离线 | 智谱 GLM | 兜底成功 |

**运行现有测试确保不回归：**
```bash
pytest tests/ -v
# 应保持 25/25 全部通过
```

---

#### 阶段 5：文档与提交（半天）

- 更新 `README.md`：添加混合引擎架构说明
- 更新 `docs/architecture.md`：补充 OpenClaw / FreeLLMAPI 集成细节
- 提交所有变更

---

### 四、关键接口定义

**`hyperspace_query` 工具签名（保持不变）：**
```json
{
  "name": "hyperspace_query",
  "parameters": {
    "prompt": "string (必填)",
    "images": "string[] (可选)",
    "context": "string (可选)",
    "mode": "auto | force_web | force_api | force_zhipu"
  }
}
```

**返回格式（增强）：**
```json
{
  "answer": "最终回复文本",
  "plan": "思维链/计划（如有）",
  "used_executor": "openclaw | frellmapi | zhipu",
  "used_model": "具体模型名",
  "tokens": { "prompt": 123, "completion": 456 },
  "cost_saved": "等效节省金额"
}
```

---

### 五、与现有代码的关系

| 现有模块 | 处理方式 |
|----------|----------|
| `hyperspace/server.py` | **修改**：调用 HybridRouter 替代原 Executor |
| `hyperspace/router.py` | **重构**：替换为 hybrid_engine/hybrid_router.py |
| `hyperspace/executor.py` | **保留**：作为 HybridRouter 内部调用 OpenClaw/FreeLLMAPI 的底层 |
| `hyperspace/providers/openai_compat.py` | **保留**：OpenClaw 和 FreeLLMAPI 均兼容 OpenAI 接口 |
| `config/providers.yaml` | **保留**：原智谱/DeepSeek API 配置仍用于兜底 |
| `config/routing.yaml` | **重构**：替换为 hybrid_config.yaml |
| `hyperspace/experimental/` | **保留**：完全不动，继续作为独立实验模块 |
| `tests/` | **新增**：hybrid_engine 专项测试；**保留**：现有 25 个测试 |

---

### 六、启动顺序（日常使用）

```bash
# 1. 启动 OpenClaw Zero Token
cd openclaw-zero-token && ./server.sh start

# 2. 启动 FreeLLMAPI
cd frellmapi && npm run dev

# 3. 启动 Hyperspace（已在 .mcp.json 中配置）
# Agent 调用 hyperspace_query 时自动触发
```

---

### 七、交付标准

- [ ] OpenClaw Zero Token 可正常调用 DeepSeek Web
- [ ] FreeLLMAPI 可正常调用 DeepSeek API
- [ ] HybridRouter 正确路由：规划→Web，代码→API，简单→Web
- [ ] 降级链验证：Web 不可用 → API；API 不可用 → 智谱
- [ ] 现有 25 个测试全部通过（不回归）
- [ ] `hyperspace.info` 可显示新增的执行器状态
- [ ] `hyperspace.summary` 正确统计混合引擎成本

---

以上是完整的实施细则。可以直接喂给 Agent，按阶段依次执行。


• OpenClaw Zero Token 克隆 + 安装 + Chrome 调试模式登录 DeepSeek
• FreeLLMAPI 克隆 + 安装 + DEEPSEEK_API_KEY 配置
• 启动两个外部服务后再验证端到端流程