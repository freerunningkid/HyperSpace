---
name: context-menu-icon-needs-0-suffix
description: 注册表 Icon 值必须加 ,0 后缀指定资源索引
metadata:
  type: feedback
---

Windows 注册表右键菜单的 Icon 值，如果只写 exe 路径（如 `D:\Reasonix\reasonix.exe`），图标可能不会显示。必须加 `,0` 后缀指定图标资源索引（如 `D:\Reasonix\reasonix-cli\reasonix.exe,0`），这是 ClaudeCode 已验证的标准做法。

**Why:** 2026-06-08 修复 Reasonix 右键菜单时发现，不加 `,0` 图标不显示。ClaudeCode 的注册表 Icon 值使用了 `claude.exe,0` 格式。

**How to apply:** 任何右键菜单的 Icon 值都使用 `path\to\exe,0` 格式，即使目标 exe 只有默认图标。用 Python winreg 写入时注意路径中的反斜杠用原始字符串 r"..." 或双反斜杠。
