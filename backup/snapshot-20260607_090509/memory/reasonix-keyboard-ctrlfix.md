---
name: reasonix-keyboard-ctrlfix
title: Ctrl+C 复制 / Esc 打断键盘修改
description: Ctrl+C always copies in Reasonix, Esc interrupts
metadata:
  type: project
---

**Reasonix 键盘修改：Ctrl+C = 复制，Esc = 打断**

**改动内容：**
- Windows Terminal settings.json 里 Ctrl+C 硬绑定为 copy 动作，不传递 SIGINT
- 新建 `scripts/reasonix-guard.ps1`：PowerShell 层 CancelKeyPress 拦截 + C# EscMonitor 后台线程
- 链路：右键 → launch-reasonix.ps1 → reasonix-guard.ps1 → reasonix chat
- launch-reasonix.ps1 指向 guard 脚本

**按键行为：**
- Ctrl+C → 复制（选中的文本，绝不打断）
- Esc（单击）→ 打断当前思考/输出
- Esc（双击 <400ms）→ 打断并触发回退记录
- Ctrl+Break 仍然可以作为底层中断备用

**Why:** 小金东想在 Reasonix 思考时选中文本按 Ctrl+C 复制而不打断工作流，类似 Claude Code 的行为。

**文件位置：**
- `D:\Reasonix\scripts\reasonix-guard.ps1` — 主守卫脚本
- `D:\Reasonix\scripts\launch-reasonix.ps1` — 右键入口（已更新指向 guard）
- `C:\Users\KID\AppData\Local\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json` — WT 设置（有 .bak.before-ctrlfix 备份）
