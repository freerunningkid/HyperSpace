# HyperSpace Web 模式与 Agent 调用指南

本文说明 HyperSpace 如何把 chat.deepseek.com 的免费网页端能力暴露给本地 Agent，并让 Agent 根据任务意图自动选择 Quick / Expert / Vision / Search。

## 目标

HyperSpace 的目标不是简单替代 DeepSeek API，而是让本地 Agent 具备类似人类使用网页端的能力：

- 简单问题走 Quick，关闭 thinking，减少等待和成本。
- 复杂推理走 Expert，开启 thinking。
- 图片、截图、PDF、Office、代码文件走 Vision / ref_file_ids。
- 新闻、实时信息、最新资料开启 search。
- 不确定时使用 auto，让 HyperSpace 自动判断。

## `mode` vs `web_mode`

这是两个不同维度：

| 参数 | 作用 | 可选值 |
|---|---|---|
| `mode` | 选择 HyperSpace 执行器 | `auto`, `force_web`, `force_api`, `force_zhipu`, legacy tiers |
| `web_mode` | 选择 DeepSeek Web 内部产品模式 | `auto`, `quick`, `expert`, `vision` |

推荐 Agent 默认使用：

```json
{
  "mode": "auto",
  "web_mode": "auto"
}
```

只有用户明确要求模式时，才显式指定 `web_mode`。

## `web_mode` 映射

| `web_mode` | `thinking_enabled` | 适合场景 | Agent 判断提示 |
|---|---:|---|---|
| `auto` | 自动 | 默认。由 HyperSpace 根据 prompt、图片、文件和搜索意图判断。 | 不确定时使用。 |
| `quick` | `False` | 闲聊、简单问答、快速回答、短解释。 | 用户说“简单回答 / 快速回答 / 别想太多”。 |
| `expert` | `True` | 数学、复杂推理、规划、深度分析、复杂代码、多步骤任务。 | 用户说“专家模式 / 深度分析 / 认真推理 / 规划”。 |
| `vision` | `True` | 图片、截图、PDF、Word、Excel、PPT、代码文件引用、识图分析。 | 用户提供图片/截图/文件，或说“看图 / 看截图 / 看 PDF”。 |

## `search_enabled` 映射

| 场景 | 建议 |
|---|---|
| 新闻、实时信息、最新资料、需要联网验证的问题 | `search_enabled=true` |
| 本地文件/图片识图、截图 bug 分析 | 不传或 `false` |
| 不确定 | 不传，让 `auto` 自动判断 |

示例：

```json
{
  "prompt": "搜索一下今天的 AI 新闻",
  "web_mode": "auto",
  "search_enabled": true
}
```

## Agent 调用示例

### 简单问答：Quick

```json
{
  "prompt": "简单介绍一下 REST API",
  "web_mode": "quick"
}
```

适合：

- 闲聊
- 简单解释
- 不需要搜索
- 不需要复杂推理

---

### 专家模式：Expert

```json
{
  "prompt": "用专家模式帮我解这道数学题：证明勾股定理",
  "web_mode": "expert"
}
```

适合：

- 数学
- 推理
- 规划
- 深度分析
- 多步骤任务

---

### 识图：Vision

```json
{
  "prompt": "这张截图里的代码有什么 bug？",
  "images": ["screenshot.png"],
  "web_mode": "vision"
}
```

适合：

- 截图
- 图片
- UI 问题
- 图表
- 手写内容
- 图片中的代码

---

### 文件引用：Vision / ref_file_ids

```json
{
  "prompt": "帮我看看这个 PDF 里写了什么",
  "files": ["report.pdf"],
  "web_mode": "vision"
}
```

适合：

- PDF
- Word
- Excel
- PPT
- TXT
- 代码文件
- 本地路径
- http(s) URL
- data URI

当前文件/图片会上传为 DeepSeek Web 的 `ref_file_ids`。PDF/Office/代码文件的文本提取与上下文注入仍在后续增强中。

---

### 搜索：Search

```json
{
  "prompt": "搜索一下最近一周的大模型开源进展",
  "web_mode": "auto",
  "search_enabled": true
}
```

如果任务本身复杂，HyperSpace 会自动倾向 Expert + Search：

```json
{
  "prompt": "分析最近 AI 技术趋势并给出行业报告",
  "web_mode": "auto",
  "search_enabled": true
}
```

---

### 自动判断：Auto

```json
{
  "prompt": "帮我看看这个截图里的代码有什么问题",
  "images": ["screenshot.png"]
}
```

HyperSpace 会推断：

- 有图片 → `vision`
- 有代码 bug 分析 → `expert`
- 图片优先 → `web_mode=vision`
- 搜索默认关闭

---

## TaskAnalyzer 推荐逻辑

当前 `TaskAnalyzer` 会把任务画像转换成 `suggested_web_mode`：

| 任务特征 | 推荐 |
|---|---|
| 有图片、截图、文件引用 | `vision` |
| 用户明确说“快速模式 / 简单回答 / 快速回答” | `quick` |
| 用户明确说“专家模式 / 深度分析 / 认真推理” | `expert` |
| 搜索意图 + 简单新闻查询 | `quick` + `search_enabled=true` |
| 搜索意图 + 复杂分析/报告/趋势 | `expert` + `search_enabled=true` |
| 数学、规划、长文、多步骤 | `expert` |
| 翻译、结构化输出 | 通常走 DeepSeek API；若强制 Web 则倾向 `quick` |

## 多轮对话

使用 `session_id` 固定会话：

```json
{
  "prompt": "继续刚才的计划，再细化一下",
  "session_id": "project-plan-001",
  "web_mode": "auto"
}
```

建议：

- 单次问答可不传 `session_id`。
- 多轮任务使用稳定 `session_id`。
- 模式默认每轮重新判断，避免上一轮的 `expert` 污染下一轮简单问题。
- 如果未来要支持“本会话保持专家模式”，应由用户明确触发。

## 当前能力边界

已支持：

- `web_mode=quick / expert / vision / auto`
- `search_enabled` 显式控制
- 图片/截图上传
- 本地文件、URL、data URI 准备为 `ref_file_ids`
- MIME 类型猜测
- DeepSeek Web 会话窗口管理
- 上下文压缩
- 降级链

后续增强：

- PDF/Office 文本提取后注入上下文
- 搜索结果结构化回显
- V4 SSE 更完整兼容
- 思考链折叠/分隔展示
- 会话模式持久化策略

## 给 Agent 的调用原则

1. 不要默认手动选模式；不确定就用 `auto`。
2. 用户要求搜索、新闻、实时信息时，设置 `search_enabled=true`。
3. 用户提供图片、截图、文件时，优先使用 `vision`。
4. 用户要求专家模式、深度推理、复杂规划时，使用 `expert`。
5. 用户要求快速回答、简单解释、闲聊时，使用 `quick`。
6. 多轮任务使用 `session_id`。
7. 需要稳定 JSON、代码生成、翻译时，可让 HyperSpace 自动路由到 DeepSeek API。
