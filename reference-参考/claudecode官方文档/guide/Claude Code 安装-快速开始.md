# 安装 Claude Code

## 一行安装

```bash
source <(curl -fsSL https://claude-zh.cn/scripts/install.sh)
```

安装完成后运行：

```bash
lucky
```

进入交互界面后输入 `/login` 登录即可使用。常用命令见[命令参考](命令参考.md)。

### 兼容性
- macOS 10.15+
- Windows 10+
- Linux / WSL

Windows 没有 Git 时脚本会自动下载安装（国内镜像优先），无需提前准备环境。

---

## 高级：官方手动安装

> **不推荐**。官方安装需要自己准备可用的 Anthropic API key、配置环境变量并处理网络问题。只在你有特殊需要时再走这条路，否则建议直接用上面的一行安装。

### 1. 安装 Node.js

**macOS：**
```bash
brew install node
```

**Windows：**
从 [nodejs.org](https://nodejs.org) 下载安装包。

**Linux/WSL：**
```bash
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 2. 安装官方 Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

国内网络如果 npm 官方源较慢，可临时切换镜像：

```bash
npm config set registry https://registry.npmmirror.com
npm install -g @anthropic-ai/claude-code
npm config set registry https://registry.npmjs.org
```

### 3. 官方 API 配置

| 方式 | 适合谁 | 配置思路 |
|------|--------|---------|
| Anthropic 官方 | 能直连官方 API 的用户 | 设置 `ANTHROPIC_API_KEY` |
| OpenRouter | 想用聚合平台或兼容接口 | 配置 base URL + token |
| 自定义 / cc switch | 已有自有服务商 | 工具/服务商给定的环境变量 |

**官方 Anthropic**（`~/.bashrc` 或 `~/.zshrc`）：
```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxxxx"
```

**Windows PowerShell：**
```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-xxxxxxx", "User")
```

**OpenRouter / 兼容 provider：**
```bash
export ANTHROPIC_BASE_URL="https://openrouter.ai/api/v1"
export ANTHROPIC_AUTH_TOKEN="你的-provider-key"
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL="anthropic/claude-sonnet-4.5"
```

不同 provider 的 URL、鉴权字段和模型名要求不同；使用 cc switch 等切换工具时以工具配置为准。

### 4. Claude Code 设置

创建或编辑 `~/.claude/settings.json`：

```json
{
  "hasCompletedOnboarding": true,
  "env": {
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  },
  "includeCoAuthoredBy": false
}
```

启动：

```bash
claude
```

按 `Shift+Tab` 可切换权限确认模式。

---

## 常见问题

### 一行安装后应该跑 `claude` 还是 `lucky`？
跑 `lucky`。中文站的一行安装入口命令是 `lucky`。

### 怎么登录和充值？
进入 `lucky` 后输入 `/login` 登录、`/recharge` 充值、`/billing` 查看用量。完整命令见[命令参考](命令参考.md)。

### 提示 API key not found？
走一行安装的话，在 `lucky` 里 `/login` 即可；如果你走的是上面的官方手动安装，检查 `ANTHROPIC_API_KEY` 或自有 provider 的 token / base URL 是否配好。

### 连接超时？
检查网络、登录状态、模型是否存在、provider 是否支持当前模型。可加入 QQ 群 `1107096515` 反馈。

---

## Windows 故障排查

PowerShell 一行安装会先检查 Git。如果没有 Git，会自动按系统架构下载 Git for Windows `2.54.0` 并静默安装。

**下载顺序：**
1. npmmirror
2. npmmirror CDN
3. 清华 TUNA
4. GitHub 官方（兜底）

如果脚本执行被策略拦截：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

如果公司/校园网络拦截了上述镜像，可以手动下载 Git 安装后再重跑安装命令：
- x64: `Git-2.54.0-64-bit.exe`
- ARM64: `Git-2.54.0-arm64.exe`

---

## 匿名安装统计

脚本会上报安装阶段（开始、Git 是否存在、镜像下载结果、整体成败），只包含系统、架构和安装阶段，不包含邮箱、用户名、token、项目路径或命令内容。

如需关闭：在运行前设置 `LUCKY_DISABLE_TELEMETRY=1`。
