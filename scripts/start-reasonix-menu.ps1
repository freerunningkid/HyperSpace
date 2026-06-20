# ============================================================================
# Reasonix 开机自启动脚本
# 功能：启动托盘菜单 + 注册热键
# 作者：2B小姐姐 for 小金东
# ============================================================================

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ahkScript = Join-Path $scriptDir "reasonix-quick-menu.ahk"

# 检查 AHK 是否安装
$ahkPath = Join-Path $env:ProgramFiles "AutoHotkey\AutoHotkey.exe"
if (-not (Test-Path $ahkPath)) {
    Write-Host "[!] AutoHotkey 未安装，跳过托盘菜单" -ForegroundColor Yellow
    exit
}

# 静默启动托盘菜单
Start-Process $ahkPath -ArgumentList $ahkScript -WindowStyle Hidden

Write-Host "[✓] Reasonix 快捷菜单已启动" -ForegroundColor Green
