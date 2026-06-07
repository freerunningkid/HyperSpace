---
name: claude-code-binary-restore
title: Claude Code 原生二进制恢复步骤
description: claude.exe 占位脚本替换为 230MB 原生二进制的完整流程
metadata:
  type: reference
---

**问题：** `claude` 命令报"指定的可执行文件不是此操作系统平台的有效应用程序"  
**根因：** `claude-code\bin\claude.exe` 是 500B 占位脚本，原生可选依赖未安装  
**修复：**
1. 从 npm registry 下载 `@anthropic-ai/claude-code-win32-x64`（~72MB tarball，解压 230MB）
2. 复制到 `node_modules/@anthropic-ai/claude-code/bin/claude.exe`
3. **不要**用 `npm install @anthropic-ai/claude-code --save-optional` — 这会删除现有 node_modules！

**验证：** `claude --version` → `2.1.167 (Claude Code)`  
**文件：** `d:\reasonix\reference-参考\memory-transfer-to-claudecode-20260606.md`

**Why:** 原生二进制是分开分发的可选依赖，npm install 的 `--ignore-scripts` 或 `--omit=optional` 会跳过它。
