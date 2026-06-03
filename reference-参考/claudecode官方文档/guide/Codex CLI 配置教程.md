# Codex CLI 配置教程

Codex CLI 可以在终端中直接与 AI 对话，帮你写代码、调试问题、解释代码。本教程使用 OpenRouter 作为 OpenAI-compatible 示例；你也可以替换成自己的 provider。

## 一键配置

```bash
curl -fsSL https://claude-zh.cn/scripts/codex-config.sh | bash
```

脚本会询问 provider id、base URL、API key 和默认模型，然后写入 `~/.codex/config.toml`。

## 手动配置

```toml
model = "anthropic/claude-sonnet-4.5"
model_provider = "openrouter"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
model_reasoning_effort = "high"

[model_providers.openrouter]
name = "openrouter"
base_url = "https://openrouter.ai/api/v1"
env_key = "OPENROUTER_API_KEY"
wire_api = "chat"
```

设置环境变量：

```bash
export OPENROUTER_API_KEY="你的-provider-key"
```

**使用自定义 Provider**：把 `openrouter`、`https://openrouter.ai/api/v1`、`OPENROUTER_API_KEY` 和模型名替换成你自己的服务商配置即可。

## 启动

```bash
codex
```

## 常见问题

### Q: 模型不可用？
确认 provider 支持该模型名，并且 `model` 字段使用 provider 要求的格式。

### Q: API key 不生效？
确认 `env_key` 与环境变量名称一致，并重启终端。
