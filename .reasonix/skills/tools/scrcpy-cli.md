---
name: scrcpy-cli
description: Android 手机投屏+操控 — 通过 ADB 无线/USB 连接
last_used: 2026-06-11
---
# scrcpy-cli — Android 手机投屏 CLI

> 基于 scrcpy v3.3.4 + ADB 1.0.41，免费开源手机投屏。

## 常用命令

```powershell
# 查看已连接的设备
D:\软件\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe devices

# USB 投屏
D:\软件\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\scrcpy.exe

# 无线投屏（先 USB 连接，然后）
D:\软件\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe tcpip 5555
D:\软件\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe connect <手机IP>:5555
D:\软件\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\scrcpy.exe

# 截图
D:\软件\scrcpy-win64-v3.3.4\scrcpy-win64-v3.3.4\adb.exe exec-out screencap -p > phone_screen.png
```

## 注意事项
- USB 连接需开启开发者模式 + USB 调试
- 无线投屏需手机和电脑在同一 WiFi
