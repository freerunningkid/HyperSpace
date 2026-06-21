---
name: context-menu-ps1
description: 在 Windows 注册表中创建/修复右键菜单条目（文件夹/空白处），正确设置 Icon 和编码
---

# context-menu-ps1 — Windows 右键菜单创建/修复

> 自动提取自 Reasonix 右键菜单修复经验

## 使用场景

- 需要给文件/文件夹/桌面添加自定义右键菜单
- 现有右键菜单显示乱码（UTF-8/GBK 编码问题）
- 右键菜单图标不显示
- 右键菜单启动时控制台闪烁

## 已知问题模式

| 症状 | 根因 | 修复 |
|------|------|------|
| 菜单名乱码（如 `瀵硅瘽`） | UTF-8 字符串被当作 GBK 写入注册表 | 用 Python winreg 或 PowerShell 显式编码写入 |
| 启动时控制台闪烁 | 直接用 `powershell.exe` 或 `python.exe` 启动 | 改用 `cmd /c start /B` 模式（无窗口），或 VBScript ShellExecute |
| 菜单前无图标 | `Icon` 值未加 `,0` 资源索引后缀 | 值改为 `路径\to\exe,0` |
| 点击后报 0x80070002 文件找不到 | `wt.exe` 等 0 字节 App Execution Alias 不能被 `start /B CreateProcess` 解析 | 改用 VBScript `Shell.Application.ShellExecute` 启动 |
| 点击后执行不正确 | 路径参数用了错误变量 | 文件夹右键用 `%1`，空白处右键用 `%V` |

## 步骤

### 1. 确定注册表路径

右键菜单注册在两个位置：
- `HKCU\Software\Classes\Directory\shell\菜单名` — **文件夹上**右键
- `HKCU\Software\Classes\Directory\Background\shell\菜单名` — **文件夹空白处**右键
- `HKCU\Software\Classes\*\shell\菜单名` — **任意文件**右键

### 2. 每个位置需要 4 个键值

| 键名 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `(Default)` | REG_SZ | 菜单显示名 | `Reasonix 对话` |
| `Icon` | REG_SZ | 图标路径+资源索引 | `D:\Reasonix\reasonix-cli\reasonix.exe,0` |
| `Position` | REG_SZ | 菜单位置 | `Top` 或 `Bottom` |
| `command\(Default)` | REG_SZ | 执行命令 | `cmd /c start /D "%1" /B wt -d "%1" powershell ...` |

### 3. 命令格式

**方案 A：标准无闪烁模式**（适用于普通 exe，借鉴 ClaudeCode）：
```cmd
cmd /c start /D "%1" /B wt -d "%1" powershell -NoExit -Command "your command"
```

**方案 B：VBScript 启动器**（适用于 App Execution Alias——0 字节重解析点如 wt.exe）：
创建 `launch-app.vbs`：
```vbscript
Dim targetDir, shell, wtArgs
targetDir = WScript.Arguments(0)
wtArgs = "-d """ & targetDir & """ powershell -NoExit -Command ""your command"""
Set shell = CreateObject("Shell.Application")
shell.ShellExecute "wt", wtArgs, targetDir, "", 0
```
注册表 command 值：
```
wscript.exe "D:\path\to\launch-app.vbs" "%1"
```
`ShellExecute` 能正确解析 App Execution Alias，且 showCmd=0 完全无窗口闪烁。

参数区别：
- 文件夹右键：`%1`
- 空白处右键：`%V`
- 文件右键：`%1`（VBS 脚本中自动取父目录）

### 4. 使用 Python winreg 写入（避免编码问题）

```python
import winreg as wr

def set_reg(key, name, value):
    k = wr.CreateKey(wr.HKEY_CURRENT_USER, key)
    wr.SetValueEx(k, name, 0, wr.REG_SZ, value)
    wr.CloseKey(k)

set_reg(r"Software\Classes\Directory\shell\菜单名", "", "菜单显示名")
set_reg(r"Software\Classes\Directory\shell\菜单名", "Icon", r"D:\path\to\exe,0")
set_reg(r"Software\Classes\Directory\shell\菜单名\command", "", 'cmd /c start /D "%1" /B ...')
```

## 验证方法

```powershell
reg query "HKCU\Software\Classes\Directory\shell\菜单名" /s
```
检查菜单名是否正常显示、Icon 路径末尾有 `,0`、command 不打开额外控制台窗口。
