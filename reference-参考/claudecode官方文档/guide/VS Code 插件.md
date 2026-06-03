# VS Code 插件

Claude Code 的 VS Code 插件把 Claude 的能力集成到编辑器中，适合习惯 Copilot、Cursor 或 Antigravity 的用户。

## 安装方式

在 VS Code 扩展市场搜索 `Claude Code`，找到 Anthropic 发布的官方插件并安装。也可以使用命令行：

```bash
code --install-extension anthropic.claude-code
```

## 配置 API

插件读取 Claude Code 的环境变量。你可以使用官方 Anthropic、OpenRouter 或自己的 provider。

### 官方 Anthropic

在 VS Code 设置中配置：

```json
{
  "claudeCode.environmentVariables": {
    "ANTHROPIC_API_KEY": "sk-ant-xxxxxxx"
  }
}
```

### OpenRouter / 自定义 Provider

```json
{
  "claudeCode.environmentVariables": {
    "ANTHROPIC_BASE_URL": "https://openrouter.ai/api/v1",
    "ANTHROPIC_AUTH_TOKEN": "你的-provider-key",
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_MODEL": "anthropic/claude-sonnet-4.5"
  }
}
```

> **注意**：不同 provider 的模型名和接口兼容性不同。如果你使用 cc switch 类工具，请以工具生成的环境变量为准。

---

## 常见问题

### Q: 插件提示 API key not found？
检查 `claudeCode.environmentVariables` 是否写在正确的 VS Code settings 文件里，并确认重启了 VS Code 窗口。

### Q: 连接超时或模型不存在？
检查 base URL、token、模型名是否与你选择的 provider 匹配。
