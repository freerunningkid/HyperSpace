# OpenClaw 配置教程

[OpenClaw](https://github.com/openclaw/openclaw) 是一个开源 AI 管家框架，可以让 Claude 通过飞书、钉钉、微信等平台与你交互。

本教程分为三步：准备服务器 → 安装 Claude Code → 配置 OpenClaw 与 API Provider。

---

## 准备服务器

OpenClaw 需要一台 Linux 服务器 24 小时运行。可以选择任意云服务商。入门阶段 2 核 2G 足够。

## 安装 Claude Code

```bash
source <(curl -fsSL https://claude-zh.cn/scripts/install.sh)
```

## 配置 API Provider

下面以 OpenRouter 风格的 OpenAI-compatible provider 为例，你可以替换成自己的服务商：

```json
{
  "providers": {
    "openrouter": {
      "type": "openai-compatible",
      "baseURL": "https://openrouter.ai/api/v1",
      "apiKey": "你的-provider-key"
    }
  },
  "agents": {
    "default": {
      "model": "openrouter/anthropic/claude-sonnet-4.5"
    }
  }
}
```

> **注意**：不同 OpenClaw 版本的配置文件结构可能不同。上面是 provider 配置思路示例；实际字段以 OpenClaw 当前文档和你的部署版本为准。

## 连接聊天平台

根据 OpenClaw 文档连接飞书、钉钉、微信等平台。核心流程通常是：
1. 创建机器人
2. 配置回调 URL
3. 写入 token/secret
4. 启动服务并测试消息收发
