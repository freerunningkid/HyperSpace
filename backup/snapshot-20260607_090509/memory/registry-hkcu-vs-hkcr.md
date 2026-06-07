---
name: registry-hkcu-vs-hkcr
title: 注册表：HKCU 无需管理员
description: HKCU 路径无需管理员添加右键菜单注册表项
metadata:
  type: reference
---

**右键菜单注册表路径选择：**
- `HKCU\Software\Classes\Directory\shell\` — **无需管理员权限**，仅对当前用户生效
- `HKCR\Directory\shell\` — 需要管理员权限，对所有用户生效

当 `reg import` 报 "Error accessing the registry" 时，说明需要管理员权限，切换到 HKCU 路径即可。

**Claude Code 右键菜单示例：**
```
HKCU\Software\Classes\Directory\shell\ClaudeCode
  @="Open Claude Code here"
  "Icon"="D:\path\to\claude.exe,0"
HKCU\Software\Classes\Directory\Background\shell\ClaudeCode\command
  @="cmd /c start /D \"%V\" /B claude"
```

**注册表文件保存位置：** `D:\Reasonix\add-claude-rightclick.reg` / `remove-claude-rightclick.reg`

**Why:** 之前在 HKCR 路径下 reg import 失败后才切换到 HKCU 成功的。
