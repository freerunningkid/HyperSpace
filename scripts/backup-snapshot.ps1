<#
.SYNOPSIS
    Reasonix 配置快照备份 —— 保护所有设置免于更新覆盖
.DESCRIPTION
    备份以下内容到 backup/ 目录（git-tracked，安全持久）：
    - %APPDATA% 下的记忆文件（最高风险，不在 git）
    - Windows Terminal settings.json（Ctrl+C 键绑定）
    - 注册表右键菜单项
    - Reasonix config.json
.PARAMETER Quiet
    安静模式，只输出关键信息
#>

param([switch]$Quiet)

$ScriptDir = Split-Path $PSScriptRoot -Parent
$BackupRoot = "$ScriptDir\backup"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Snapshot   = "$BackupRoot\snapshot-$Timestamp"

if (-not $Quiet) {
    Write-Host ""
    Write-Host "  📸 配置快照备份" -ForegroundColor Cyan
    Write-Host "  ────────────────────────" -ForegroundColor DarkGray
    Write-Host "  时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
}

# 1. 记忆文件（最高风险）
$MemSrc = "$env:APPDATA\reasonix\projects\D--Reasonix\memory"
$MemDst = "$Snapshot\memory"
if (Test-Path $MemSrc) {
    New-Item -Path $MemDst -ItemType Directory -Force | Out-Null
    Copy-Item "$MemSrc\*" $MemDst -Recurse -Force
    $count = (Get-ChildItem $MemDst | Measure-Object).Count
    if (-not $Quiet) { Write-Host "  📁 记忆文件: $count 个已备份" -ForegroundColor Green }
}

# 2. Windows Terminal 设置
$WtSrc = "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
if (Test-Path $WtSrc) {
    Copy-Item $WtSrc "$Snapshot\windows-terminal-settings.json" -Force
    if (-not $Quiet) { Write-Host "  🪟 Windows Terminal 设置: 已备份" -ForegroundColor Green }
}

# 3. 注册表右键菜单
$RegDst = "$Snapshot\reasonix-contextmenu.reg"
try {
    # 导出 Background 右键
    $null = Start-Process reg -ArgumentList @(
        "export", "HKCU\Software\Classes\Directory\Background\shell\Reasonix", "`"$RegDst`"", "/y"
    ) -Wait -WindowStyle Hidden
    if (Test-Path $RegDst) {
        if (-not $Quiet) { Write-Host "  📋 右键菜单(背景): 已备份" -ForegroundColor Green }
    }
    # 追加 Directory 右键
    $RegDst2 = "$Snapshot\reasonix-contextmenu-dir.reg"
    $null = Start-Process reg -ArgumentList @(
        "export", "HKCU\Software\Classes\Directory\shell\Reasonix", "`"$RegDst2`"", "/y"
    ) -Wait -WindowStyle Hidden
    if (Test-Path $RegDst2) {
        if (-not $Quiet) { Write-Host "  📋 右键菜单(文件夹): 已备份" -ForegroundColor Green }
    }
} catch {
    if (-not $Quiet) { Write-Host "  ⚠ 注册表备份失败: $_" -ForegroundColor Yellow }
}

# 4. Reasonix config.json
$CfgSrc = "$ScriptDir\config\reasonix\config.json"
if (Test-Path $CfgSrc) {
    Copy-Item $CfgSrc "$Snapshot\reasonix-config.json" -Force
    if (-not $Quiet) { Write-Host "  ⚙  Reasonix 配置: 已备份" -ForegroundColor Green }
}

if (-not $Quiet) {
    Write-Host "  ────────────────────────" -ForegroundColor DarkGray
    Write-Host "  ✅ 快照已保存至: $Snapshot" -ForegroundColor Cyan
    Write-Host "  💡 运行 restore-snapshot.ps1 -Snapshot $(Split-Path $Snapshot -Leaf) 可恢复" -ForegroundColor DarkGray
    Write-Host ""
}

# 清理旧快照：保留最近 10 个
$Snapshots = Get-ChildItem "$BackupRoot\snapshot-*" -Directory | Sort-Object Name -Descending
if ($Snapshots.Count -gt 10) {
    $Snapshots | Select-Object -Skip 10 | Remove-Item -Recurse -Force
    if (-not $Quiet) { Write-Host "  🧹 已清理旧快照，保留最近 10 个" -ForegroundColor DarkGray }
}

# 返回快照路径
return $Snapshot
