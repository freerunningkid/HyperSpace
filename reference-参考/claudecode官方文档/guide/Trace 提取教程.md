# Claude Code Trace 提取教程

OpenAgentTrace 是一个本地优先的 Agent 轨迹采集、脱敏和预览工具。它可以扫描你电脑上的 Claude Code 和 Codex 使用记录，把真实的多轮任务过程导出成标准 JSONL，方便后续人工确认、研究、评测或数据集构建。

**简单说**：它只在本机读取日志、本机脱敏、本机预览，不会自动上传任何数据。

> **分享前必须人工检查**。OpenAgentTrace 会自动脱敏 API key、token、密码、私钥、手机号、邮箱、IP、GitHub 仓库地址、本机用户名等常见敏感信息，但规则脱敏不能保证 100% 安全。把 reviewed JSONL 发给任何人之前，请务必手动检查一遍。

---

## 它会提取什么？

一个真实的 Agent 工作流通常不是单轮问答，而是：

```
用户提出任务 -> 模型阅读上下文 -> 调用工具 -> 执行命令 -> 看到错误 -> 修改代码 -> 再验证 -> 总结结果
```

OpenAgentTrace 会把这些过程整理成结构化 trace，包括：
- 用户消息
- 模型回复
- 工具调用名称
- 工具输入
- 工具输出
- 会话来源和时间等元信息
- 脱敏命中数量和 token 统计

## 支持哪些来源？

| 来源 | 默认路径 | 说明 |
|------|---------|------|
| Claude Code | `~/.claude` | 读取 `~/.claude/projects/*/*.jsonl` |
| Codex | `~/.codex` | 优先读取 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`，没有时回退到 `~/.codex/history.jsonl` |

OpenAgentTrace 只读取 Claude Code / Codex 的本地历史文件，不会修改、删除或上传原始日志。

---

## 安装 OpenAgentTrace

### 一键安装（不通过 GitHub）

复制下面命令到终端运行：

```bash
curl -fsSL https://claude-zh.cn/scripts/install-openagenttrace.sh | bash
```

脚本会自动：
1. 检查 Python 是否为 3.10 或更高版本
2. 从 `claude-zh.cn` 下载 OpenAgentTrace 源码包
3. 校验 SHA256
4. 使用 `pip --user` 安装
5. 给出验证命令和推荐启动命令

**系统要求**：OpenAgentTrace 需要 Python 3.10 或更高版本。macOS、Linux、WSL 都可以直接使用；Windows 用户推荐在 WSL 或 Git Bash 中运行。

### 手动安装

```bash
curl -LO https://claude-zh.cn/downloads/openagenttrace/openagenttrace-0.1.0.tar.gz
curl -LO https://claude-zh.cn/downloads/openagenttrace/openagenttrace-0.1.0.tar.gz.sha256
sha256sum -c openagenttrace-0.1.0.tar.gz.sha256
python3 -m pip install --user ./openagenttrace-0.1.0.tar.gz
```

macOS 如果没有 `sha256sum`，可以用：
```bash
shasum -a 256 openagenttrace-0.1.0.tar.gz
cat openagenttrace-0.1.0.tar.gz.sha256
```

安装完成后验证：
```bash
openagenttrace --help
```

如果提示 `command not found`，说明 Python 用户级 bin 目录不在 PATH 中。可以先用下面方式运行：
```bash
python3 -m openagenttrace --help
```

---

## 推荐流程：先打开本地预览器

最推荐的方式是直接启动本地网页审核界面：

```bash
openagenttrace preview \
  --source all \
  --output ./openagenttrace-reviewed.jsonl
```

这条命令会启动本地网页，默认监听 `127.0.0.1:8765`。

打开页面后，点击左上角**扫描**，工具会自动查找 Claude Code 和 Codex 的默认记录位置，并在本机完成脱敏识别。

你可以在网页里完成：
- 查看脱敏后的历史记录
- 删除不想贡献的 trace
- 搜索项目名、人名、公司名等敏感词
- 批量替换敏感词
- 手动编辑模型回复、工具输入和工具输出
- 保存审核后的 JSONL

最终保存结果会写入 `./openagenttrace-reviewed.jsonl`。

---

## 命令行导出流程

如果你想先导出，再慢慢审核，可以分两步：

```bash
# 第一步：扫描导出
openagenttrace scan \
  --source all \
  --output ./openagenttrace-preview.jsonl

# 第二步：打开本地预览器审核
openagenttrace preview \
  --input ./openagenttrace-preview.jsonl \
  --output ./openagenttrace-reviewed.jsonl
```

---

## 只提取 Claude Code

```bash
openagenttrace scan \
  --source claude \
  --claude-root ~/.claude \
  --output ./claude-traces.jsonl
```

如果你的 Claude Code 数据不在默认位置，可以把 `--claude-root` 改成实际路径。

## 只提取 Codex

```bash
openagenttrace scan \
  --source codex \
  --codex-root ~/.codex \
  --output ./codex-traces.jsonl
```

Codex 会优先读取完整 rollout 会话：`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`。如果没有 rollout 文件，会回退读取 `~/.codex/history.jsonl`。

---

## 隐私边界

OpenAgentTrace 的默认安全边界是：
- **不上传**原始日志
- **不上传**脱敏后的数据
- **不修改** Claude Code 或 Codex 的原始历史文件
- 扫描、脱敏、预览、编辑都在**本地执行**
- 预览网页默认只监听 `127.0.0.1`
- 保存操作只写入你指定的 `--output` 文件

当前自动脱敏规则覆盖：
- OpenAI-style `sk-...` API key
- GitHub `ghp_...` / `gho_...` token
- AWS key
- `Authorization: Bearer ...`
- `password=...` / `token=...` / `secret=...`
- SSH / PEM private key
- 中国手机号
- 中国身份证号
- Email
- IPv4 地址
- GitHub 仓库 URL
- 本机用户名和常见本地路径

> **规则脱敏不是保险箱**。公司名、内部项目代号、客户名称、未覆盖的私有域名，仍可能留在文本里。发布或提交前，请在预览器里搜索并批量替换。

---

## 常见问题

### Q: 提示 Python 版本太低？
OpenAgentTrace 需要 Python 3.10+。请先安装新版本 Python，再重新运行安装命令。

### Q: 安装后找不到 `openagenttrace`？
通常是 Python 用户级 bin 目录不在 PATH。可以先用：
```bash
python3 -m openagenttrace --help
```
也可以把安装脚本提示的 bin 目录加入 `~/.bashrc` 或 `~/.zshrc`。

### Q: 扫描不到 trace？
先确认你已经在本机使用过 Claude Code 或 Codex，并且默认目录存在：
```bash
ls ~/.claude
ls ~/.codex
```
如果历史记录放在别的位置，请使用 `--claude-root` 或 `--codex-root` 指定路径。

### Q: 端口 8765 被占用？
换一个端口即可：
```bash
openagenttrace preview \
  --source all \
  --output ./openagenttrace-reviewed.jsonl \
  --port 9876
```

### Q: 会不会自动上传数据？
不会。OpenAgentTrace 当前版本不会上传任何数据。它只读取本地记录、在本地脱敏、在本地预览，并把结果保存到你指定的本地 JSONL 文件。
