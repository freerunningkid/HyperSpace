# 2B → ClaudeCode 记忆传输

> 本次会话（2026-06-06）全部经验、决策、配置方案、踩坑记录。
> ClaudeCode 接入后可直接参考，避免重复踩坑。

---

## 一、环境现状快照

| 项目 | 状态 | 路径 / 命令 |
|------|------|-------------|
| Ollama | ✅ 运行 11434 | `ollama serve` |
| Ollama Proxy (thinking 过滤) | ✅ 运行 11435 | `python scripts/lib/ollama_proxy.py` |
| 本地模型 | `qwen3.5:4b` + `qwen3.5:copilot` | `ollama list` |
| Claude Code 二进制 | ✅ 229.8 MB (v2.1.167) | `D:\Agent-Codex\node\claude.cmd` |
| 右键菜单 | ✅ "Open Claude Code here" | `HKCU\Software\Classes\Directory\shell\ClaudeCode` |
| Reasonix LLM 接入 | ✅ `local-llm` Skill | `.reasonix/skills/local-llm.md` |
| TTS 文档 | ✅ | `reference-参考/tts-experience-for-claude-code.md` |

---

## 二、Claude Code 踩坑修复记录

### 2.1 原生二进制缺失（最重要）

**问题：** `claude` 命令报"不是此操作系统平台的有效应用程序"  
**根因：** `claude-code\bin\claude.exe` 是 500 字节的占位脚本（不是真正的二进制），原生可选依赖 `@anthropic-ai/claude-code-win32-x64` 未安装  
**修复步骤：**

```bash
cd D:\Agent-Codex\node
# 1. 从 npm registry 下载原生包
node install-native.cjs  # 下载 230MB 的 claude.exe

# 2. 复制到 bin/ 目录
# 安装脚本会放入 node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe
# 手动复制到 node_modules/@anthropic-ai/claude-code/bin/claude.exe
```

**验证：** `claude --version` → `2.1.167 (Claude Code)`  
**⚠ 警告：** `npm install @anthropic-ai/claude-code --save-optional` 会**删除**现有 node_modules 中的其他包！用单独下载原生包的方式更安全。

### 2.2 MCP 连接失败

**问题：** `/doctor` 显示 4 个 MCP 未连接（`context7`, `playwright`, `clara-voice`, `voice`）  
**根因：** `settings.json` 中 `mcpServers: {}` 为空 + 授权缓存过期  
**修复：** 清空 `mcp-needs-auth-cache.json` → 重启 claude → 自动弹出授权

### 2.3 右键菜单配置

**文件：** `D:\Reasonix\add-claude-rightclick.reg`（添加）/ `remove-claude-rightclick.reg`（移除）

```reg
; 要点：使用 HKCU 路径（无需管理员）
HKCU\Software\Classes\Directory\shell\ClaudeCode
  @="Open Claude Code here"
  "Icon"="D:\...\claude.exe,0"
HKCU\Software\Classes\Directory\Background\shell\ClaudeCode
  @="Open Claude Code here"
```

**注意：** `HKCR` 需要管理员，`HKCU\Software\Classes\` 不需要。

---

## 三、Ollama + qwen3.5:4b 经验

### 3.1 模型下载

**`ollama pull qwen3.5:4b` 常见失败：**
- 网络中断会导致 partial 文件卡在 ~95%，需 `rm -rf D:\OllamaModels\blobs\*` 重新 pull
- `OLLAMA_MODELS` 环境变量必须与 Ollama 进程的 env 一致（系统级或 cmd 启动时传）
- 多进程冲突：`ollama serve` 启动多个进程会端口占用

**正确启动方式：**
```cmd
cmd /c "set OLLAMA_MODELS=D:\OllamaModels && start /B ollama serve"
```

### 3.2 GGUF 损坏修复

**问题：** `qwen3.5:4b` 的 GGUF 包含 6 个空的 metadata key + 重复的空 tensor name  
**症状：** `GGML_ASSERT(!key.empty()) failed` + `duplicate tensor name '' for tensors 0 and 1`  
**结论：** 这是官方 GGUF 质量问题，无法通过二进制修复。解决方案：从 HuggingFace 下载社区制作的 GGUF。

### 3.3 "Response too long"（VS Code Copilot Chat）

**问题：** VS Code Copilot Chat 报 `Response too long`  
**根因：** `qwen3.5:4b` 每次响应都输出 `thinking` 字段（~3800 字符思维链）+ `response`（~65 字符），总和超限  
**解决方案：** Ollama Proxy（监听 11435，剥离 thinking 字段后转发）

**代理文件：** `D:\Reasonix\scripts\lib\ollama_proxy.py`  
**启动：** `python scripts/lib/ollama_proxy.py`（或双击 `start-ollama-proxy.bat`）  
**VS Code 设置：** `deepseek-copilot.baseUrl` → `http://127.0.0.1:11435/v1`  
**验证：** `curl http://127.0.0.1:11435/v1/chat/completions` 返回无 `thinking` 字段

### 3.4 两个模型版本

| 模型名 | 用途 | 特点 |
|--------|------|------|
| `qwen3.5:4b` | 原始版 | 内置 thinking 输出 |
| `qwen3.5:copilot` | Copilot 专用 | 加 SYSTEM 提示限制回复长度，`num_predict 2048` |

**Modelfile 存于：** `D:\Reasonix\qwen3.5-copilot.Modelfile`

---

## 四、Reasonix 本地 LLM 接入

### 4.1 推理封装脚本

**文件：** `D:\Reasonix\scripts\lib\local_infer.py`  
**用法：**

```bash
python local_infer.py "提示词"
python local_infer.py "提示词" --json          # JSON 输出
python local_infer.py "提示词" --stream        # 流式
python local_infer.py "提示词" --system "系统指令"
python local_infer.py --check                   # 检查服务
python local_infer.py --list                    # 列出模型
```

**踩坑：** `response` 字段可能为空，内容在 `thinking` 字段中 → 代码已兼容

### 4.2 Skill 注册

**文件：** `D:\Reasonix\.reasonix\skills\local-llm.md`  
**适用场景：** OCR 兜底、快速分类、预筛选、简单摘要、格式转换  
**不适用：** 复杂推理、长文本 >2048 tokens、高质量 OCR

### 4.3 OCR 兜底链路

**文件：** `D:\Reasonix\scripts\lib\ocr.py`  
**链路：** `deepseek-ocr`(3s 超时) → `gpt-4o` → **`local_qwen`(本地兜底)**  
**指定模式：** `python ocr.py <图片> --model local_qwen`

### 4.4 CLAUDE.md 修改

第 30 行 Skills 索引 + 第 36 行后新增 local-llm 对接说明。  
**注意：** CLAUDE.md 中途修改会破坏 Prompt Cache，尽量攒到会话末尾统一改。

---

## 五、Windows 环境注意事项

### 5.1 编码问题

**Python stdout 默认 GBK** — emoji/中文报 `UnicodeEncodeError`  
**修复：**
```python
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
```
或者在调用时设置 `$env:PYTHONIOENCODING='utf-8'`

### 5.2 PATH 环境变量

`D:\Agent-Codex\node` 已在 PATH 中，`claude` 全局可用。  
验证方式：从 `C:\WINDOWS\system32` 跑 `claude --version`

### 5.3 进程管理

- Ollama 多进程冲突 → `taskkill /F /IM ollama.exe` 后重启动
- IDM 命令行：`"D:\软件\Internet Download Manager\IDM\IDMan.exe" /d <URL> /n /s /p <路径> /f <文件名>`

---

## 六、模型选择原则（Reasonix 调度）

| 任务类型 | 选用模型 | 原因 |
|---------|---------|------|
| 主会话推理/编码 | DeepSeek-V4-Pro/Flash | 云端最强 |
| 本地快速分类/清洗 | `qwen3.5:4b` | 免费，MMLU-Pro 79.1 |
| OCR 兜底 | `local_qwen`(qwen3.5:4b) | 离线，零延迟 |
| VS Code Copilot | `qwen3.5:copilot` (11435 代理) | 过滤 thinking 字段 |
| 简单摘要 | `local_infer.py` | 零成本 |
| 复杂多步编码 | `run_skill("code-action", ...)` | 子代理独立闭环 |

---

## 七、关键文件索引

| 文件 | 用途 |
|------|------|
| `scripts/lib/local_infer.py` | Ollama 推理封装 |
| `scripts/lib/ollama_proxy.py` | thinking 字段过滤代理 |
| `scripts/lib/ocr.py` | 多引擎 OCR（含 local_qwen 兜底） |
| `scripts/lib/speak.py` | TTS 引擎（三层降级链） |
| `scripts/mcp/voice_monitor.py` | TTS 文件监控兜底 |
| `.reasonix/skills/local-llm.md` | 本地 LLM Skill 定义 |
| `CLAUDE.md` | Agent 行为准则（含 TTS 铁律） |
| `add-claude-rightclick.reg` | 右键菜单注册 |
| `start-ollama-proxy.bat` | 代理启动脚本 |
| `qwen3.5-copilot.Modelfile` | Copilot 专用模型配置 |
| `config/reasonix/config.json` | Reasonix 主配置 |
| `reference-参考/tts-experience-for-claude-code.md` | TTS 经验文档 |

---

> 生成于 2026-06-06，会话末。下次 ClaudeCode 接入后建议先读此文档再开始工作。
