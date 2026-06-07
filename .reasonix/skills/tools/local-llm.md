---
name: local-llm
description: 本地 Ollama 模型推理（qwen3.5:4b）— 快速/廉价/离线，用作云端 API 的兜底和预筛
last_used: 2026-06-06
---

# Skill: local-llm

调用本地 Ollama 模型（qwen3.5:4b）执行推理任务。需 Ollama 运行中。

## 适用场景

| 场景 | 说明 | 优于云端的原因 |
|------|------|---------------|
| OCR 兜底 | 云端 API（deepseek-ocr/gpt-4o）超时或失败时自动 fallback | 零延迟，无需网络 |
| 快速分类 | 对文本/截图进行简单分类（A/B/C） | 3-5 秒出结果，不消耗 API 配额 |
| 预筛选 | 在处理复杂任务前快速判断是否需要走昂贵的云模型 | 成本几乎为零 |
| 简单摘要 | 对短文本做摘要、提取关键词 | 本地响应，无隐私顾虑 |
| 格式转换 | Markdown/JSON 格式转换、数据清洗 | 稳定，不受 API 限速影响 |

## 不适用的场景

- 复杂推理 / 多步编码 → 用主会话强的模型
- 长文本分析（>2048 tokens）→ qwen3.5:4b 上下文有限
- 高质量 OCR → 优先用 deepseek-ocr / gpt-4o
- 需要最新知识的问答 → 用云端模型

## 调用方式

### 1. 直接从 Agent 调用

```
python D:\Reasonix\scripts\lib\local_infer.py "提示词"
python D:\Reasonix\scripts\lib\local_infer.py "提示词" --stream
python D:\Reasonix\scripts\lib\local_infer.py "提示词" --system "系统指令"
python D:\Reasonix\scripts\lib\local_infer.py --check     # 检查服务
python D:\Reasonix\scripts\lib\local_infer.py --list      # 列出模型
python D:\Reasonix\scripts\lib\local_infer.py "文本" --json  # JSON 输出
```

### 2. OCR 场景（集成进 ocr.py）

```
python D:\Reasonix\scripts\lib\ocr.py <图片> --model local_qwen
# 竞速模式中自动作为最后兜底（云端全失败后触发）
```

### 3. 分类任务

```
python D:\Reasonix\scripts\lib\local_infer.py "将这段文字归类为 技术/业务/闲聊 之一：<文本>"
```

## 对接主 Agent 的规则

在 CLAUDE.md 中已注册本 Skill，主 Agent 在以下情况自动调此 Skill：

1. 云端 OCR（screenshot-ocr）返回错误时 → 调 `local-llm` 兜底
2. 需要快速分类/判断，且任务简单（1-2 句回应）→ 直接调 `local_infer.py`
3. 用户明确要求"用本地模型/离线跑" → 调 `local-llm`

## 前提条件

- Ollama 运行中（`ollama serve`）
- 模型已拉取（`ollama pull qwen3.5:4b`）
- 环境变量 `OLLAMA_MODELS` 指向模型存储目录

## 错误处理

| 错误 | 处理方式 |
|------|---------|
| 连接被拒绝 | Ollama 未运行 → 启动后重试 |
| 超时 | 降低 `num_predict` 或 `timeout` |
| 模型不存在 | 先运行 `ollama pull qwen3.5:4b` |
| 空回复 | 重试 1 次，仍空则切换到云端模型 |
