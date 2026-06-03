# OpenCode 配置教程

[OpenCode](https://opencode.ai/) 是一个开源终端 AI 编程助手，支持 OpenAI-compatible API。你可以使用 OpenRouter，也可以接入自己的 provider。

## 一键配置

```bash
curl -fsSL https://claude-zh.cn/scripts/opencode-config.sh | bash
```

脚本会安装 OpenCode，询问 provider id、base URL、API key 和默认模型，并生成 `~/.config/opencode/opencode.json`。

## 手动配置

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openrouter": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "openrouter",
      "options": {
        "baseURL": "https://openrouter.ai/api/v1",
        "apiKey": "你的-provider-key"
      },
      "models": {
        "anthropic/claude-sonnet-4.5": {},
        "anthropic/claude-opus-4.5": {}
      }
    }
  },
  "model": "openrouter/anthropic/claude-sonnet-4.5"
}
```

**使用自己的 Provider**：把 provider id、`baseURL`、`apiKey` 和模型名替换成你选择的服务商配置即可。

## 启动

```bash
opencode
```
