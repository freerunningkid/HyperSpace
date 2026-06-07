---
name: app-execution-alias-vbs-launcher
title: App Execution Alias 必须用 VBScript ShellExecute
description: App Execution Alias (0字节 wt.exe) 需用 VBScript ShellExecute 启动
metadata:
  type: feedback
---

Windows 的 App Execution Alias（如 wt.exe 在 C:\Users\KID\AppData\Local\Microsoft\WindowsApps\wt.exe 是 0 字节重解析点）不能通过 `cmd /c start /B wt ...` 的方式启动。`CreateProcess` 无法解析这类特殊文件，会报 `0x80070002` 文件找不到。

正确的启动方式是 VBScript 启动器，通过 `Shell.Application.ShellExecute` 来启动：
```vbscript
Set shell = CreateObject("Shell.Application")
shell.ShellExecute "wt", args, workingDir, "", 0
```
`ShellExecute` 遵循与资源管理器相同的解析链路，能正确处理 App Execution Alias。

**Why:** 2026-06-08 修复 Reasonix 右键菜单时遇到的坑。`wt -d "%1" powershell -NoExit -Command "reasonix chat"` 在 cmd start /B 下报 0x80070002，换成 VBS ShellExecute 后完美工作。

**How to apply:** 凡是要从右键菜单启动 Windows Terminal、Calculator、Photos 等 UWP/AppX 应用的，都用 VBScript 启动器，不要用 cmd start /B。
