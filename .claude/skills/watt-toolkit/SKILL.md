---
name: watt-toolkit
description: 管理 Watt Toolkit（Steam++）的启动、加速开关、状态检查，纯命令行无 GUI 操作
last_used: 2026-06-04
---
# Watt Toolkit 命令行管理 Skill

## 基本信息

| 项目 | 值 |
|------|-----|
| 安装路径 | `D:\软件\steam++\` |
| 主程序 | `Steam++.exe` |
| 加速模块 | `modules\Accelerator\Steam++.Accelerator.exe` |
| 配置目录 | `%LOCALAPPDATA%\Steam++\` |
| 自启方式 | 计划任务 `Steam++_{SID}` |
| 进程名 | `Steam++.exe` |

## 配置文件

| 文件 | 关键字段 |
|------|----------|
| `Settings\GeneralSettings.json` | `AutoRunOnStartup` — 开机自启开关 |
| `Settings\GeneralSettings.json` | `MinimizeOnStartup` — 启动后最小化到托盘 |
| `Plugins\Accelerator\Settings\ProxySettings.json` | `ProgramStartupRunProxy` — **启动时自动开启加速** |
| `Plugins\Accelerator\Settings\ProxySettings.json` | `IsEnableScript` — 加速脚本总开关 |
| `Plugins\Accelerator\Settings\ProxySettings.json` | `ProxyMode` — 代理模式 (`Hosts` / `Proxy`) |

## 常用操作

### 1. 检查运行状态
```cmd
tasklist /fi "imagename eq Steam++.exe" 2>nul | findstr Steam++
```

### 2. 重启 Watt Toolkit（推荐方式 — 通过计划任务，处理管理员权限问题）
```cmd
# 停止
schtasks /end /tn "\Steam++_{SID}"
# 启动
schtasks /run /tn "\Steam++_{SID}"
```
> 先通过 `schtasks /query /fo list | findstr Steam++` 获取精确任务名。

### 3. 查看计划任务名
```cmd
schtasks /query /fo list 2>nul | findstr /i "steam++"
```

### 4. 开启"启动时自动加速"
修改 `ProxySettings.json`：`"ProgramStartupRunProxy": true`
然后通过计划任务重启生效。

### 5. 关闭"启动时自动加速"
修改 `ProxySettings.json`：`"ProgramStartupRunProxy": false`

### 6. 启用/禁用开机自启
修改 `GeneralSettings.json`：`"AutoRunOnStartup": true/false`

### 7. 修改 JSON 配置的标准流程
1. `read_file` 读取目标 JSON
2. `edit_file` 只改目标字段（保持格式、其他字段不变）
3. 通过计划任务重启 `Steam++.exe`（`schtasks /end` → `schtasks /run`）

## 执行原则
- **绝不使用键鼠模拟** — 一切通过 JSON 配置 + 计划任务管理完成
- 修改 JSON 前先读当前内容，只改目标字段
- Watt Toolkit 以管理员权限运行，`taskkill` 会失败 → 必须用 `schtasks /end /tn` 停止
