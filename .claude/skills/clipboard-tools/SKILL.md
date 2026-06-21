---
name: clipboard-tools
description: 剪贴板读写 — PowerShell 原生工具，零依赖
last_used: 2026-06-09
---
# clipboard-tools — 剪贴板操作

> 基于 PowerShell 原生命令，零依赖、零延迟。

## 用法

### 读剪贴板
```powershell
Get-Clipboard
```

### 写剪贴板
```powershell
Set-Clipboard -Value "要写入的文本"
```

### 写文件内容到剪贴板
```powershell
Get-Content file.txt | Set-Clipboard
```

## 注意事项

- PowerShell 5.1+ 内置，无需安装任何包
- 支持文本、图片（通过 `-Format` 参数）
- 比 Python pyperclip 更快（原生 API）
