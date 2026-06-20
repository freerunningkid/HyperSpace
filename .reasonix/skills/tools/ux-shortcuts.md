---
name: ux-shortcuts
description: 用户交互体验优化：托盘菜单/AHK热键/TTS快捷命令。
last_used: never
---
# ux-shortcuts — 用户交互体验优化

> 一键启动 Reasonix / 截屏 / TTS 测试，无需打开终端。

## 快捷菜单

### 安装

```powershell
# 1. 安装 AutoHotkey v2
winget install AutoHotkey.AutoHotkey

# 2. 启动托盘菜单
python scripts\start-reasonix-menu.ps1

# 3. 设置开机自启
New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\reasonix-menu.ahk" -Target "D:\Reasonix\scripts\reasonix-quick-menu.ahk"
```

### 托盘菜单功能

| 菜单项 | 功能 | 热键 |
|--------|------|------|
| 💬 启动 Reasonix | 打开终端启动 Reasonix | Ctrl+Shift+R |
| 📸 截屏 + OCR | 截屏并保存到截图目录 | Ctrl+Shift+S |
| 📂 打开工作区 | 打开 D:\Reasonix | - |
| 🔊 测试 TTS | 播放晓晓语音 | - |
| ❓ 帮助 | 显示使用说明 | - |

### 全局热键

| 热键 | 功能 |
|------|------|
| **Ctrl+Shift+S** | 快速截屏 |
| **Ctrl+Shift+R** | 启动 Reasonix |
| **Esc** | 退出托盘菜单 |

## TTS 快捷命令

```powershell
# 一句话语音播报
python D:\Reasonix\scripts\lib\speak.py "小金东，该休息啦～"

# 批量播报
python D:\Reasonix\scripts\lib\speak.py "任务完成，干得漂亮！"
```

## 注意事项

- 需要安装 AutoHotkey v2（`winget install AutoHotkey.AutoHotkey`）
- 托盘菜单默认隐藏窗口，不干扰工作
- 热键全局生效，任何窗口下可用
- 开机自启通过符号链接到 Startup 文件夹
