---
name: session-search
description: 搜索过往对话 JSONL 记录，用 FTS5 风格全文检索查找特定话题、问题、决策。Hermes 式会话记忆
last_used: 2026-06-04
---
# session-search — 会话记忆搜索

> 定位：**inline（主 Agent 上下文内执行）**
> 灵感：Hermes Agent 的 FTS5 会话搜索——搜索过去对话找到有用的上下文

## 原理

会话记录以 JSONL 格式存储在 `archive-归档/claude-legacy/projects/` 下。
每个文件包含多轮对话，每条消息含 role/content/uuid 等字段。

## 用法

```
run_skill("session-search", "<搜索词>")
```

## 工作流程

### Step 1：确定搜索范围

搜索 `archive-归档/claude-legacy/projects/*.jsonl` 和 `archive-归档/claude-legacy/sessions/*.jsonl`
中的 user 和 assistant 消息。

### Step 2：执行搜索

对每个 JSONL 文件：
1. 用 grep 搜索关键词（不区分大小写）
2. 提取匹配的行 + 前后各 2 行作为上下文
3. 去重和排序

### Step 3：汇总结果

```
══════════════════════════
 SESSION-SEARCH REPORT
══════════════════════════
🔍 搜索词: <关键词>
📊 找到 N 条匹配

📝 Top 结果:
  1. [来源文件] → [摘要] → 第 N 行
  2. ...
══════════════════════════
```

## 适用范围

| 场景 | 示例 |
|------|------|
| 找回之前做过的事 | "上次清理垃圾时发生了什么" |
| 查历史决策 | "之前选 TTS 方案时的讨论" |
| 找过去的配置 | "MCP 的端口配置是什么" |
| 回忆对话上下文 | "我之前说过喜欢什么风格" |

## 铁律

- **只读不写** — 不修改任何 JSONL 文件
- **命中过多时截断** — 超过 20 条只展示 Top 20
- **不显示敏感内容** — 只输出对话摘要，不 dump 原始 JSON
- **找不到就说找不到** — 不要编造结果
