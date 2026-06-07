---
name: ollama-proxy-vscode-response-too-long
title: Ollama Proxy 解决 VS Code 响应过长
description: Ollama Proxy + qwen3.5:copilot 解决 VS Code "Response too long"
metadata:
  type: reference
---

**问题：** qwen3.5:4b 在 VS Code Copilot Chat 报 "Response too long"  
**根因：** Ollama API 返回 `thinking` 字段（~3800 字符思维链）+ `response` 字段，VS Code 总和限制超限  
**方案：** 创建 Ollama 透明代理 `ollama_proxy.py`，监听 11435，转发到 11434，剥离 JSON 中所有 `thinking` 字段

**Two model variants:**
- `qwen3.5:4b` — 原始版，内置 thinking 输出
- `qwen3.5:copilot` — 加 SYSTEM 提示限制长度 + `num_predict 2048`（Modelfile 在 `d:\reasonix\qwen3.5-copilot.Modelfile`）

**VS Code 配置：** `deepseek-copilot.baseUrl` = `http://127.0.0.1:11435/v1`  
**自动启动：** `D:\Reasonix\start-ollama-proxy.bat`  
**验证：** `curl http://127.0.0.1:11435/v1/chat/completions` 响应无 `thinking` 字段

**Why:** VS Code Copilot Chat 内部有固定响应长度限制，Ollama 把 thinking 放在 JSON 响应中一并返回。
