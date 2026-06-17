---
name: git-cli
description: Git 版本控制 — 提交/分支/日志/对比。比 sync skill 更通用，不自动 push。
last_used: 2026-06-11
---
# git-cli — Git 版本控制 CLI

> 基于 git v2.54，仓库在 D:\Reasonix。

## 常用命令

```powershell
git status                    # 查看当前状态
git log --oneline -10         # 最近 10 条提交
git diff                      # 未暂存的差异
git add -A && git commit -m "msg"  # 提交
git push                      # 推送
git pull                      # 拉取
git checkout -b <branch>      # 创建并切换分支
git branch                    # 查看分支
```

## 典型场景

| 场景 | 命令 |
|------|------|
| 查看变更 | `git status && git diff --stat` |
| 快速提交 | `git add -A && git commit -m "摘要" && git push` |
| 查看历史 | `git log --oneline --graph -20` |
