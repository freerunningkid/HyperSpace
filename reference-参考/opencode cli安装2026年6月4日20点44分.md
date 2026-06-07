推荐使用 OpenCode tap 以获取最新版本。
为了在 Windows 上获得最佳体验，我们推荐使用 [Windows Subsystem for Linux (WSL)](https://opencode.ai/docs/windows-wsl)。它提供更好的性能，并完全兼容 OpenCode 的所有功能。
1. **安装 WSL**
    
    如果尚未安装，请参照 Microsoft 官方指南[安装 WSL](https://learn.microsoft.com/en-us/windows/wsl/install)。
    
2. **在 WSL 中安装 OpenCode**
    
    WSL 设置完成后，打开 WSL 终端，使用任一[安装方式](https://opencode.ai/docs/)安装 OpenCode。
    
    Terminal window
    
    ```
    curl -fsSL https://opencode.ai/install | bash
    ```
    
3. **从 WSL 中使用 OpenCode**
    
    导航到你的项目目录（通过 `/mnt/c/`、`/mnt/d/` 等路径访问 Windows 文件），然后运行 OpenCode。
    
    Terminal window
    
    ```
    cd /mnt/c/Users/YourName/projectopencode
    ```
    

---

## [桌面应用 + WSL 服务器](https://opencode.ai/docs/windows-wsl#%E6%A1%8C%E9%9D%A2%E5%BA%94%E7%94%A8--wsl-%E6%9C%8D%E5%8A%A1%E5%99%A8)

如果你希望使用 OpenCode 桌面应用，同时在 WSL 中运行服务器：

1. **在 WSL 中启动服务器**，添加 `--hostname 0.0.0.0` 以允许外部连接：
    
    Terminal window
    
    ```
    opencode serve --hostname 0.0.0.0 --port 4096
    ```
    
2. **在桌面应用中连接到** `http://localhost:4096`
    

注意

如果 `localhost` 在你的环境中无法使用，请改用 WSL 的 IP 地址进行连接（在 WSL 中运行：`hostname -I`），使用 `http://<wsl-ip>:4096`。

警告

使用 `--hostname 0.0.0.0` 时，请设置 `OPENCODE_SERVER_PASSWORD` 以保护服务器安全。

Terminal window

```
OPENCODE_SERVER_PASSWORD=your-password opencode serve --hostname 0.0.0.0
```

---

## [Web 客户端 + WSL](https://opencode.ai/docs/windows-wsl#web-%E5%AE%A2%E6%88%B7%E7%AB%AF--wsl)

要在 Windows 上获得最佳的 Web 体验：

1. **在 WSL 终端中运行 `opencode web`**，而非在 PowerShell 中运行：
    
    Terminal window
    
    ```
    opencode web --hostname 0.0.0.0
    ```
    
2. **在 Windows 浏览器中访问** `http://localhost:<port>`（OpenCode 会输出该 URL）
    

从 WSL 中运行 `opencode web` 可确保正确的文件系统访问和终端集成，同时仍可通过 Windows 浏览器进行访问。

---

## [访问 Windows 文件](https://opencode.ai/docs/windows-wsl#%E8%AE%BF%E9%97%AE-windows-%E6%96%87%E4%BB%B6)

WSL 可以通过 `/mnt/` 目录访问你的所有 Windows 文件：

- `C:` 盘 → `/mnt/c/`
- `D:` 盘 → `/mnt/d/`
- 其他盘符以此类推…

示例：

Terminal window

```
cd /mnt/c/Users/YourName/Documents/projectopencode
```

提示

为了获得更流畅的体验，建议将仓库克隆或复制到 WSL 文件系统中（例如 `~/code/` 目录下），然后在该位置运行 OpenCode。

---

## [使用技巧](https://opencode.ai/docs/windows-wsl#%E4%BD%BF%E7%94%A8%E6%8A%80%E5%B7%A7)

- 对于存储在 Windows 驱动器上的项目，在 WSL 中运行 OpenCode 即可无缝访问文件
- 搭配 VS Code 的 [WSL 扩展](https://code.visualstudio.com/docs/remote/wsl) 使用 OpenCode，打造一体化的开发工作流
- OpenCode 的配置和会话数据存储在 WSL 环境中的 `~/.local/share/opencode/`
  
  
  ② **桌面应用内按 `Ctrl+K`** 打开命令面板

③ 搜索输入 **`切换服务器`** 或 **`server`**

④ 选 `切换服务器`，填入：

```
http://172.24.44.23:4096
```

密码：`opencode-kid2025`




# CLI

OpenCode CLI 选项和命令。

OpenCode CLI 在不带任何参数运行时，默认启动 [TUI](https://opencode.ai/docs/tui)。

Terminal window

```
opencode
```

但它也接受本页面中记录的命令，使您可以通过编程方式与 OpenCode 进行交互。

Terminal window

```
opencode run "Explain how closures work in JavaScript"
```

---

### [tui](https://opencode.ai/docs/zh-cn/cli/#tui)

启动 OpenCode 终端用户界面。

Terminal window

```
opencode [project]
```

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97)

|标志|简写|描述|
|---|---|---|
|`--continue`|`-c`|继续上一个会话|
|`--session`|`-s`|要继续的会话 ID|
|`--fork`||继续时分叉会话（与 `--continue` 或 `--session` 配合使用）|
|`--prompt`||要使用的提示词|
|`--model`|`-m`|要使用的模型，格式为 provider/model|
|`--agent`||要使用的代理|
|`--port`||监听端口|
|`--hostname`||监听主机名|

---

## [命令](https://opencode.ai/docs/zh-cn/cli/#%E5%91%BD%E4%BB%A4)

OpenCode CLI 还提供以下命令。

---

### [agent](https://opencode.ai/docs/zh-cn/cli/#agent)

管理 OpenCode 的代理。

Terminal window

```
opencode agent [command]
```

---

### [attach](https://opencode.ai/docs/zh-cn/cli/#attach)

将终端连接到已通过 `serve` 或 `web` 命令启动的 OpenCode 后端服务器。

Terminal window

```
opencode attach [url]
```

这允许将 TUI 与远程 OpenCode 后端配合使用。例如：

Terminal window

```
# Start the backend server for web/mobile accessopencode web --port 4096 --hostname 0.0.0.0
# In another terminal, attach the TUI to the running backendopencode attach http://10.20.30.40:4096
```

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-1)

|标志|简写|描述|
|---|---|---|
|`--dir`||启动 TUI 的工作目录|
|`--continue`|`-c`|继续上一个会话|
|`--session`|`-s`|要继续的会话 ID|
|`--fork`||继续时派生会话（与 `--continue` 或 `--session` 一起使用）|
|`--password`|`-p`|基本认证密码（默认使用 `OPENCODE_SERVER_PASSWORD`）|
|`--username`|`-u`|基本认证用户名（默认使用 `OPENCODE_SERVER_USERNAME` 或 `opencode`）|

---

#### [create](https://opencode.ai/docs/zh-cn/cli/#create)

使用自定义配置创建新的代理。

Terminal window

```
opencode agent create
```

此命令将引导您使用自定义系统提示词和工具配置来创建新的代理。

---

#### [list](https://opencode.ai/docs/zh-cn/cli/#list)

列出所有可用的代理。

Terminal window

```
opencode agent list
```

---

### [auth](https://opencode.ai/docs/zh-cn/cli/#auth)

管理提供商的凭据和登录信息的命令。

Terminal window

```
opencode auth [command]
```

---

#### [login](https://opencode.ai/docs/zh-cn/cli/#login)

OpenCode 基于 [Models.dev](https://models.dev/) 的提供商列表运行，因此您可以使用 `opencode auth login` 为任何想要使用的提供商配置 API 密钥。密钥存储在 `~/.local/share/opencode/auth.json` 中。

Terminal window

```
opencode auth login
```

OpenCode 启动时会从凭据文件加载提供商信息，同时也会加载环境变量或项目中 `.env` 文件中定义的密钥。

---

#### [list](https://opencode.ai/docs/zh-cn/cli/#list-1)

列出凭据文件中存储的所有已认证提供商。

Terminal window

```
opencode auth list
```

或使用简写版本。

Terminal window

```
opencode auth ls
```

---

#### [logout](https://opencode.ai/docs/zh-cn/cli/#logout)

从凭据文件中清除提供商信息以完成登出。

Terminal window

```
opencode auth logout
```

---

### [github](https://opencode.ai/docs/zh-cn/cli/#github)

管理用于仓库自动化的 GitHub 代理。

Terminal window

```
opencode github [command]
```

---

#### [install](https://opencode.ai/docs/zh-cn/cli/#install)

在您的仓库中安装 GitHub 代理。

Terminal window

```
opencode github install
```

此命令会设置必要的 GitHub Actions 工作流并引导您完成配置过程。[了解更多](https://opencode.ai/docs/github)。

---

#### [run](https://opencode.ai/docs/zh-cn/cli/#run)

运行 GitHub 代理。通常在 GitHub Actions 中使用。

Terminal window

```
opencode github run
```

##### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-2)

|标志|描述|
|---|---|
|`--event`|用于运行代理的 GitHub 模拟事件|
|`--token`|GitHub 个人访问令牌|

---

### [mcp](https://opencode.ai/docs/zh-cn/cli/#mcp)

管理 Model Context Protocol 服务器。

Terminal window

```
opencode mcp [command]
```

---

#### [add](https://opencode.ai/docs/zh-cn/cli/#add)

将 MCP 服务器添加到您的配置中。

Terminal window

```
opencode mcp add
```

此命令将引导您添加本地或远程 MCP 服务器。

---

#### [list](https://opencode.ai/docs/zh-cn/cli/#list-2)

列出所有已配置的 MCP 服务器及其连接状态。

Terminal window

```
opencode mcp list
```

或使用简写版本。

Terminal window

```
opencode mcp ls
```

---

#### [auth](https://opencode.ai/docs/zh-cn/cli/#auth-1)

对支持 OAuth 的 MCP 服务器进行认证。

Terminal window

```
opencode mcp auth [name]
```

如果您不提供服务器名称，系统将提示您从可用的支持 OAuth 的服务器中进行选择。

您还可以列出支持 OAuth 的服务器及其认证状态。

Terminal window

```
opencode mcp auth list
```

或使用简写版本。

Terminal window

```
opencode mcp auth ls
```

---

#### [logout](https://opencode.ai/docs/zh-cn/cli/#logout-1)

移除 MCP 服务器的 OAuth 凭据。

Terminal window

```
opencode mcp logout [name]
```

---

#### [debug](https://opencode.ai/docs/zh-cn/cli/#debug)

调试 MCP 服务器的 OAuth 连接问题。

Terminal window

```
opencode mcp debug <name>
```

---

### [models](https://opencode.ai/docs/zh-cn/cli/#models)

列出已配置提供商的所有可用模型。

Terminal window

```
opencode models [provider]
```

此命令以 `provider/model` 的格式显示所有已配置提供商中可用的模型。

这对于确定在[配置文件](https://opencode.ai/docs/config/)中使用的确切模型名称非常有用。

您可以选择传入提供商 ID 来按提供商筛选模型。

Terminal window

```
opencode models anthropic
```

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-3)

|标志|描述|
|---|---|
|`--refresh`|从 models.dev 刷新模型缓存|
|`--verbose`|使用更详细的模型输出（包含费用等元数据）|

使用 `--refresh` 标志可以更新缓存的模型列表。当提供商新增了模型并且您希望在 OpenCode 中看到它们时，此功能非常有用。

Terminal window

```
opencode models --refresh
```

---

### [run](https://opencode.ai/docs/zh-cn/cli/#run-1)

以非交互模式运行 OpenCode，直接传入提示词。

Terminal window

```
opencode run [message..]
```

这对于脚本编写、自动化或无需启动完整 TUI 即可快速获取答案的场景非常有用。例如：

Terminal window

```
opencode run Explain the use of context in Go
```

您还可以连接到正在运行的 `opencode serve` 实例，以避免每次运行时 MCP 服务器的冷启动时间：

Terminal window

```
# Start a headless server in one terminalopencode serve
# In another terminal, run commands that attach to itopencode run --attach http://localhost:4096 "Explain async/await in JavaScript"
```

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-4)

|标志|简写|描述|
|---|---|---|
|`--command`||要运行的命令，使用 message 作为参数|
|`--continue`|`-c`|继续上一个会话|
|`--session`|`-s`|要继续的会话 ID|
|`--fork`||继续时分叉会话（与 `--continue` 或 `--session` 配合使用）|
|`--share`||分享会话|
|`--model`|`-m`|要使用的模型，格式为 provider/model|
|`--agent`||要使用的代理|
|`--file`|`-f`|附加到消息的文件|
|`--format`||格式：default（格式化输出）或 json（原始 JSON 事件）|
|`--title`||会话标题（未提供值时使用截断的提示词）|
|`--attach`||连接到正在运行的 opencode 服务器（例如 [http://localhost:4096）](http://localhost:4096%EF%BC%89/)|
|`--password`|`-p`|基本认证密码（默认使用 `OPENCODE_SERVER_PASSWORD`）|
|`--username`|`-u`|基本认证用户名（默认使用 `OPENCODE_SERVER_USERNAME` 或 `opencode`）|
|`--dir`||运行目录，或附加时远程服务器上的路径|
|`--variant`||模型变体（特定于提供商的推理级别）|
|`--thinking`||显示思考块|
|`--port`||本地服务器端口（默认为随机端口）|

---

### [serve](https://opencode.ai/docs/zh-cn/cli/#serve)

启动无界面的 OpenCode 服务器以提供 API 访问。查看[服务器文档](https://opencode.ai/docs/server)了解完整的 HTTP 接口。

Terminal window

```
opencode serve
```

此命令启动一个 HTTP 服务器，提供对 OpenCode 功能的 API 访问，无需 TUI 界面。设置 `OPENCODE_SERVER_PASSWORD` 可启用 HTTP 基本认证（用户名默认为 `opencode`）。

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-5)

|标志|描述|
|---|---|
|`--port`|监听端口|
|`--hostname`|监听主机名|
|`--mdns`|启用 mDNS 发现|
|`--cors`|允许 CORS 的额外浏览器来源|

---

### [session](https://opencode.ai/docs/zh-cn/cli/#session)

管理 OpenCode 会话。

Terminal window

```
opencode session [command]
```

---

#### [list](https://opencode.ai/docs/zh-cn/cli/#list-3)

列出所有 OpenCode 会话。

Terminal window

```
opencode session list
```

##### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-6)

|标志|简写|描述|
|---|---|---|
|`--max-count`|`-n`|限制为最近 N 个会话|
|`--format`||输出格式：table 或 json（默认 table）|

---

### [stats](https://opencode.ai/docs/zh-cn/cli/#stats)

显示 OpenCode 会话的 Token 用量和费用统计信息。

Terminal window

```
opencode stats
```

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-7)

|标志|描述|
|---|---|
|`--days`|显示最近 N 天的统计信息（默认为所有时间）|
|`--tools`|显示的工具数量（默认为全部）|
|`--models`|显示模型用量明细（默认隐藏）。传入数字可显示前 N 个|
|`--project`|按项目筛选（默认为所有项目，传入空字符串表示当前项目）|

---

### [export](https://opencode.ai/docs/zh-cn/cli/#export)

将会话数据导出为 JSON。

Terminal window

```
opencode export [sessionID]
```

如果您不提供会话 ID，系统将提示您从可用的会话中进行选择。

---

### [import](https://opencode.ai/docs/zh-cn/cli/#import)

从 JSON 文件或 OpenCode 分享链接导入会话数据。

Terminal window

```
opencode import <file>
```

您可以从本地文件或 OpenCode 分享链接导入。

Terminal window

```
opencode import session.jsonopencode import https://opncd.ai/s/abc123
```

---

### [web](https://opencode.ai/docs/zh-cn/cli/#web)

启动带有 Web 界面的无界面 OpenCode 服务器。

Terminal window

```
opencode web
```

此命令启动一个 HTTP 服务器并打开浏览器，通过 Web 界面访问 OpenCode。设置 `OPENCODE_SERVER_PASSWORD` 可启用 HTTP 基本认证（用户名默认为 `opencode`）。

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-8)

|标志|描述|
|---|---|
|`--port`|监听端口|
|`--hostname`|监听主机名|
|`--mdns`|启用 mDNS 发现|
|`--cors`|允许 CORS 的额外浏览器来源|

---

### [acp](https://opencode.ai/docs/zh-cn/cli/#acp)

启动 ACP（Agent Client Protocol）服务器。

Terminal window

```
opencode acp
```

此命令启动一个通过 stdin/stdout 使用 nd-JSON 进行通信的 ACP 服务器。

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-9)

|标志|描述|
|---|---|
|`--cwd`|工作目录|
|`--port`|监听端口|
|`--hostname`|监听主机名|

---

### [uninstall](https://opencode.ai/docs/zh-cn/cli/#uninstall)

卸载 OpenCode 并删除所有相关文件。

Terminal window

```
opencode uninstall
```

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-10)

|标志|简写|描述|
|---|---|---|
|`--keep-config`|`-c`|保留配置文件|
|`--keep-data`|`-d`|保留会话数据和快照|
|`--dry-run`||显示将被删除的内容但不实际删除|
|`--force`|`-f`|跳过确认提示|

---

### [upgrade](https://opencode.ai/docs/zh-cn/cli/#upgrade)

将 OpenCode 更新到最新版本或指定版本。

Terminal window

```
opencode upgrade [target]
```

更新到最新版本。

Terminal window

```
opencode upgrade
```

更新到指定版本。

Terminal window

```
opencode upgrade v0.1.48
```

#### [标志](https://opencode.ai/docs/zh-cn/cli/#%E6%A0%87%E5%BF%97-11)

|标志|简写|描述|
|---|---|---|
|`--method`|`-m`|使用的安装方式：curl、npm、pnpm、bun、brew|

---

## [全局标志](https://opencode.ai/docs/zh-cn/cli/#%E5%85%A8%E5%B1%80%E6%A0%87%E5%BF%97)

OpenCode CLI 接受以下全局标志。

|标志|简写|描述|
|---|---|---|
|`--help`|`-h`|显示帮助信息|
|`--version`|`-v`|打印版本号|
|`--print-logs`||将日志输出到 stderr|
|`--log-level`||日志级别（DEBUG、INFO、WARN、ERROR）|

---

## [环境变量](https://opencode.ai/docs/zh-cn/cli/#%E7%8E%AF%E5%A2%83%E5%8F%98%E9%87%8F)

OpenCode 可以通过环境变量进行配置。

|变量|类型|描述|
|---|---|---|
|`OPENCODE_AUTO_SHARE`|boolean|自动分享会话|
|`OPENCODE_GIT_BASH_PATH`|string|Windows 上 Git Bash 可执行文件的路径|
|`OPENCODE_CONFIG`|string|配置文件路径|
|`OPENCODE_TUI_CONFIG`|string|TUI 配置文件路径|
|`OPENCODE_CONFIG_DIR`|string|配置目录路径|
|`OPENCODE_CONFIG_CONTENT`|string|内联 JSON 配置内容|
|`OPENCODE_DISABLE_AUTOUPDATE`|boolean|禁用自动更新检查|
|`OPENCODE_DISABLE_PRUNE`|boolean|禁用旧数据清理|
|`OPENCODE_DISABLE_TERMINAL_TITLE`|boolean|禁用自动终端标题更新|
|`OPENCODE_PERMISSION`|string|内联 JSON 权限配置|
|`OPENCODE_DISABLE_DEFAULT_PLUGINS`|boolean|禁用默认插件|
|`OPENCODE_DISABLE_LSP_DOWNLOAD`|boolean|禁用 LSP 服务器自动下载|
|`OPENCODE_ENABLE_EXPERIMENTAL_MODELS`|boolean|启用实验性模型|
|`OPENCODE_DISABLE_AUTOCOMPACT`|boolean|禁用自动上下文压缩|
|`OPENCODE_DISABLE_CLAUDE_CODE`|boolean|禁用读取 `.claude`（提示词 + 技能）|
|`OPENCODE_DISABLE_CLAUDE_CODE_PROMPT`|boolean|禁用读取 `~/.claude/CLAUDE.md`|
|`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS`|boolean|禁用加载 `.claude/skills`|
|`OPENCODE_DISABLE_MODELS_FETCH`|boolean|禁用从远程源获取模型|
|`OPENCODE_FAKE_VCS`|string|用于测试目的的模拟 VCS 提供商|
|`OPENCODE_CLIENT`|string|客户端标识符（默认为 `cli`）|
|`OPENCODE_ENABLE_EXA`|boolean|启用 Exa 网络搜索工具|
|`OPENCODE_SERVER_PASSWORD`|string|为 `serve`/`web` 启用基本认证|
|`OPENCODE_SERVER_USERNAME`|string|覆盖基本认证用户名（默认为 `opencode`）|
|`OPENCODE_MODELS_URL`|string|自定义模型配置获取 URL|

---

### [实验性功能](https://opencode.ai/docs/zh-cn/cli/#%E5%AE%9E%E9%AA%8C%E6%80%A7%E5%8A%9F%E8%83%BD)

这些环境变量用于启用可能会更改或移除的实验性功能。

|变量|类型|描述|
|---|---|---|
|`OPENCODE_EXPERIMENTAL`|boolean|启用受总开关控制的实验性功能|
|`OPENCODE_EXPERIMENTAL_ICON_DISCOVERY`|boolean|启用图标发现|
|`OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT`|boolean|禁用 TUI 中的选中即复制|
|`OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS`|number|bash 命令的默认超时时间（毫秒）|
|`OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX`|number|LLM 响应的最大输出 Token 数|
|`OPENCODE_EXPERIMENTAL_FILEWATCHER`|boolean|启用整个目录的文件监听器|
|`OPENCODE_EXPERIMENTAL_OXFMT`|boolean|启用 oxfmt 格式化器|
|`OPENCODE_EXPERIMENTAL_LSP_TOOL`|boolean|启用实验性 LSP 工具|
|`OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER`|boolean|禁用文件监听器|
|`OPENCODE_EXPERIMENTAL_EXA`|boolean|启用实验性 Exa 功能|
|`OPENCODE_EXPERIMENTAL_LSP_TY`|boolean|为 python 文件启用 TY LSP|
|`OPENCODE_EXPERIMENTAL_PLAN_MODE`|boolean|启用计划模式|
|`OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`|boolean|启用后台子代理任务|
|`OPENCODE_EXPERIMENTAL_EVENT_SYSTEM`|boolean|启用实验性事件系统|
|`OPENCODE_EXPERIMENTAL_NATIVE_LLM`|boolean|启用原生 LLM 请求路径|
|`OPENCODE_EXPERIMENTAL_PARALLEL`|boolean|启用并行 Web 搜索执行|
|`OPENCODE_EXPERIMENTAL_SCOUT`|boolean|启用 Scout 子代理|
|`OPENCODE_EXPERIMENTAL_WORKSPACES`|boolean|启用工作区支持|