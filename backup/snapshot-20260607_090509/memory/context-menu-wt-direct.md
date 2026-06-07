---
name: context-menu-wt-direct
title: 右键菜单命令直接写 wt.exe 即可
description: 右键菜单启动 wt.exe 直接注册表写，不需 start/B 或 VBS
metadata:
  type: feedback
---

Windows 右键菜单注册表 command 值，如果启动的是 App Execution Alias（如 wt.exe 是 0 字节重解析点），**直接在注册表写 wt.exe 命令**就能正常工作——因为 Explorer 通过 ShellExecute 执行注册表命令，能正确解析 0 字节别名。

正确写法：
```
wt.exe -d "%1" cmd /k reasonix chat
```
而不是：
```
cmd /c start /D "%1" /B wt ...   ← CreateProcess 无法解析 0 字节别名
wscript.exe "vbs" "%1"           ← 多一层 VBS，showCmd 写错就隐藏窗口
```

**Why:** 2026-06-08 反复修复 Reasonix 右键菜单。一开始用 `cmd /c start /B wt ...` 报 0x80070002，换 VBS ShellExecute 又写错 showCmd=0 导致窗口隐藏。最后参考 ClaudeCode 直接在注册表写 `wt.exe -d "%1" cmd /k claude`，完美工作。

**How to apply:** 任何需要从右键菜单启动 Windows Terminal + CLI 的场景，注册表 command 直接写 `wt.exe -d "%1" cmd /k <命令>`，不要套 `start /B` 或 VBS 中间层。
