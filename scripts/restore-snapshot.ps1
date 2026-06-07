<#
.SYNOPSIS
    Reasonix 配置恢复 —— 从快照还原所有设置
.DESCRIPTION
    从 backup/snapshot-*/ 中恢复：
    - 记忆文件 → %APPDATA%/reasonix/projects/D--Reasonix/memory/
    - Windows Terminal 设置 → AppData 对应位置
    - 注册表右键菜单
    - Reasonix config.json
.PARAMETER Snapshot
    指定快照目录名（如 snapshot-20260607_091500），不指定则用最新的
.PARAMETER Quiet
    安静模式
#>

param(
    [string]$Snapshot = "",
    [switch]$Quiet
)

$ScriptDir = Split-Path $PSScriptRoot -Parent
$BackupRoot = "$ScriptDir\backup"

# 查找快照目录
if (-not $Snapshot) {
    $latest = Get-ChildItem "$BackupRoot\snapshot-*" -Directory | Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) {
        Write-Host "  ❌ 未找到任何快照" -ForegroundColor Red
        exit 1
    }
    $Snapshot = $latest.Name
}

$SnapDir = "$BackupRoot\$Snapshot"
if (-not (Test-Path $SnapDir)) {
    Write-Host "  ❌ 快照目录不存在: $SnapDir" -ForegroundColor Red
    exit 1
}

if (-not $Quiet) {
    Write-Host ""
    Write-Host "  🔄 配置恢复" -ForegroundColor Cyan
    Write-Host "  ────────────────────────" -ForegroundColor DarkGray
    Write-Host "  快照: $SnapDir" -ForegroundColor White
}

# 1. 恢复记忆文件
$MemBak = "$SnapDir\memory"
$MemDst = "$env:APPDATA\reasonix\projects\D--Reasonix\memory"
if (Test-Path $MemBak) {
    New-Item -Path $MemDst -ItemType Directory -Force | Out-Null
    Copy-Item "$MemBak\*" $MemDst -Recurse -Force
    $count = (Get-ChildItem $MemDst | Measure-Object).Count
    if (-not $Quiet) { Write-Host "  📁 记忆文件: $count 个已恢复" -ForegroundColor Green }
}

# 2. 恢复 Windows Terminal 设置
$WtBak = "$SnapDir\windows-terminal-settings.json"
$WtDst = "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
if (Test-Path $WtBak) {
    # 先备份当前设置（防止误操作）
    $WtCurBak = "$WtDst.replaced-by-restore"
    if (Test-Path $WtDst -and -not (Test-Path $WtCurBak)) {
        Copy-Item $WtDst $WtCurBak -Force
    }
    Copy-Item $WtBak $WtDst -Force
    if (-not $Quiet) { Write-Host "  🪟 Windows Terminal 设置: 已恢复" -ForegroundColor Green }
}

# 3. 恢复注册表右键菜单
$RegFiles = @(
    "$SnapDir\reasonix-contextmenu.reg",
    "$SnapDir\reasonix-contextmenu-dir.reg"
)
foreach ($reg in $RegFiles) {
    if (Test-Path $reg) {
        try {
            $null = Start-Process reg -ArgumentList @("import", "`"$reg`"") -Wait -WindowStyle Hidden -NoNewWindow
            if (-not $Quiet) { Write-Host "  📋 右键菜单: 已恢复 ($(Split-Path $reg -Leaf))" -ForegroundColor Green }
        } catch {
            if (-not $Quiet) { Write-Host "  ⚠ 右键菜单恢复失败: $_" -ForegroundColor Yellow }
        }
    }
}

# 4. 恢复 Reasonix config.json
$CfgBak = "$SnapDir\reasonix-config.json"
$CfgDst = "$ScriptDir\config\reasonix\config.json"
if (Test-Path $CfgBak) {
    Copy-Item $CfgBak $CfgDst -Force
    if (-not $Quiet) { Write-Host "  ⚙  Reasonix 配置: 已恢复" -ForegroundColor Green }
}

if (-not $Quiet) {
    Write-Host "  ────────────────────────" -ForegroundColor DarkGray
    Write-Host "  ✅ 配置已从快照恢复" -ForegroundColor Cyan
    Write-Host ""
}
