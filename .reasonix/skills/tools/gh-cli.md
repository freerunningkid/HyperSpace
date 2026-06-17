---
name: gh-cli
description: GitHub CLI — 仓库/issue/PR/搜索，替代 22MB MCP binary
last_used: 2026-06-09
---
# gh-cli — GitHub 官方命令行

> 基于 `gh`（GitHub CLI v2.93+），替代旧的 github MCP Server。
> 安装: `winget install --id GitHub.cli`
> 首次使用需 `gh auth login`

## 常用命令

| 命令 | 用途 |
|------|------|
| `gh repo view <owner/repo>` | 查看仓库详情 |
| `gh repo list <owner>` | 列出用户仓库 |
| `gh issue list` | 列出 Issue |
| `gh issue view <number>` | 查看 Issue 详情 |
| `gh pr list` | 列出 PR |
| `gh pr view <number>` | 查看 PR 详情 |
| `gh pr diff <number>` | 查看 PR diff |
| `gh search code "<pattern>" --repo <owner/repo>` | 搜索代码 |
| `gh search repos "<query>"` | 搜索仓库 |
| `gh auth status` | 检查登录状态 |

## 典型场景

| 场景 | 命令 |
|------|------|
| 看仓库信息 | `gh repo view freerunningkid/KID-Reasonix202606020008` |
| 搜代码 | `gh search code "evolve" --repo freerunningkid/KID-Reasonix202606020008` |
| 看 Issue | `gh issue list -R freerunningkid/KID-Reasonix202606020008` |
| 仓库搜索 | `gh search repos "topic:mcp"` |

## 注意事项

- 首次使用需登录: `gh auth login --web`（或 `gh auth login -p https -w`）
- API 不限速：已 GitHub App 认证时 5000 req/h
- 输出支持 `--json` 格式，配合 `jq` 可做结构化处理
