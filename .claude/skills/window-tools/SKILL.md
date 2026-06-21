---
name: window-tools
description: 窗口枚举/激活 — PowerShell + pygetwindow，零依赖
last_used: 2026-06-09
---
# window-tools — 窗口管理

> 基于 PowerShell 和 Python 轻量脚本，零 MCP 依赖。

## 用法

### 枚举可见窗口
```powershell
python -c "import pygetwindow as gw; [print(f'{w.left},{w.top} {w.width}x{w.height} {w.title[:60]}') for w in gw.getAllWindows() if w.title.strip() and w.width>0]"
```

### 获取当前焦点窗口
```powershell
python -c "import pygetwindow as gw; w=gw.getActiveWindow(); print(f'{w.title} ({w.left},{w.top} {w.width}x{w.height})')"
```

### PowerShell 原生（简单版）
```powershell
Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object ProcessName, MainWindowTitle
Get-Process | Where-Object { $_.MainWindowHandle -ne 0 } | Format-Table ProcessName, MainWindowTitle -AutoSize
```
