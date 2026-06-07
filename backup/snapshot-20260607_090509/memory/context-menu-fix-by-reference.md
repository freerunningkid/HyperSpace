---
name: context-menu-fix-by-reference
title: 右键菜单先查参考再改
description: 右键菜单修复前先查同类参考，照着抄不要发明
metadata:
  type: feedback
---

Windows 右键菜单修复的第一原则：**先看同类方案**。查 ClaudeCode 的注册表条目 `reg query "HKCU\Software\Classes\Directory\shell\ClaudeCode" /s` 获取标准答案。

标准写法：
- Icon: `exe路径,0`（不要单独ico文件，直接用exe自身图标）
- command: 直接写 `wt.exe -d "%1" cmd /k <命令>`，不需要 `start /B`、VBScript 或任何中间层
- Explorer 的 ShellExecute 能正确解析 wt.exe 的 0 字节 App Execution Alias

改动后必须**立即右键测试验证**，不要假设"应该好了"。

为什么要这样做？2026-06-08 修复 Reasonix 右键菜单走了 5-6 轮弯路：从 start /B → VBS → 直接 exe → 最终 wt.exe 直接写。如果第一轮就先查 ClaudeCode 的注册表，5 分钟就能搞定。

**How to apply:** 任何右键菜单相关任务，第一步永远是 `reg query "HKCU\Software\Classes\Directory\shell\其他同类软件" /s` 获取参考。改完立刻右键测试。
