---
name: context-menu-no-flash-pattern
description: 右键菜单无闪烁启动模式：cmd /c start /B
metadata:
  type: feedback
---

Windows 右键菜单的正确无闪烁启动模式是 `cmd /c start /D "%1" /B <程序>`，这与 ClaudeCode 使用的模式一致。不要直接用 `powershell.exe` 或 `python.exe` 作为 command 值，这会导致控制台窗口闪烁。

当需要启动 Windows Terminal 时，完整命令为：
```
cmd /c start /D "%1" /B wt -d "%1" powershell -NoExit -Command "reasonix chat"
```

参数区别：
- `%1` — 文件夹/文件右键（Directory/* 和 */*）
- `%V` — 空白处右键（Background/*）

**Why:** 2026-06-08 修复 Reasonix 右键菜单。旧命令用了 `powershell.exe -WindowStyle Normal` 启动，先闪 cmd 窗口再启动 wt。改成 `cmd /c start /B` 后完全无声无闪烁。

**How to apply:** 所有右键菜单 command 值都用 `cmd /c start /D "%%1" /B ...` 模式包裹，不直接调用 powershell/python。
