<#
.SYNOPSIS
    配置完整性检查 —— 检测更新后丢失的配置项
.DESCRIPTION
    检查所有关键配置是否存在。如果发现丢失，尝试从最新快照自动恢复。
    适合集成到 reasonix-guard.ps1 中每次启动自动运行。
.PARAMETER Quiet
    安静模式，不输出检查详情
#>

param([switch]$Quiet)

$ScriptDir = Split-Path $PSScriptRoot -Parent
$BackupRoot = "$ScriptDir\backup"
$issues = @()

# ============================================================
# 1. 检查记忆文件
# ============================================================
$MemDir = "$env:APPDATA\reasonix\projects\D--Reasonix\memory"
if (-not (Test-Path $MemDir)) {
    $issues += "记忆目录不存在: $MemDir"
} elseif ((Get-ChildItem $MemDir | Measure-Object).Count -eq 0) {
    $issues += "记忆目录为空: $MemDir"
}

# ============================================================
# 2. 检查 Windows Terminal Ctrl+C 绑定
# ============================================================
$WtFile = "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
$ctrlCFound = $false
if (Test-Path $WtFile) {
    $wtContent = Get-Content $WtFile -Raw -Encoding UTF8
    if ($wtContent -match '"ctrl\+c"' -and $wtContent -match '"copy"') {
        $ctrlCFound = $true
    }
}
if (-not $ctrlCFound) {
    $issues += "Windows Terminal 缺少 Ctrl+C→Copy 绑定"
}

# ============================================================
# 3. 检查右键菜单注册表
# ============================================================
$regBgPath = "Registry::HKEY_CURRENT_USER\Software\Classes\Directory\Background\shell\Reasonix"
if (-not (Test-Path $regBgPath)) {
    $issues += "右键菜单(背景)注册表项缺失"
}

# ============================================================
# 4. 检查 Reasonix config.json
# ============================================================
$CfgFile = "$ScriptDir\config\reasonix\config.json"
if (-not (Test-Path $CfgFile)) {
    $issues += "Reasonix 配置文件缺失: $CfgFile"
}

# ============================================================
# 自动修复
# ============================================================
$fixed = $false
if ($issues.Count -gt 0) {
    $latest = Get-ChildItem "$BackupRoot\snapshot-*" -Directory | Sort-Object Name -Descending | Select-Object -First 1
    if ($latest) {
        Write-Host "  🔧 发现 $($issues.Count) 个配置问题，尝试从快照恢复..." -ForegroundColor Yellow
        # 调用 restore-snapshot.ps1 安静模式
        & "$ScriptDir\scripts\restore-snapshot.ps1" -Snapshot $latest.Name -Quiet
        $fixed = $true
    } else {
        Write-Host "  ⚠ 发现 $($issues.Count) 个配置问题，但无可用快照" -ForegroundColor Yellow
        Write-Host "  💡 运行 backup-snapshot.ps1 创建首个快照" -ForegroundColor Yellow
    }
}

# ============================================================
# 输出结果
# ============================================================
if ($issues.Count -eq 0) {
    Write-Host "  ✅ 配置完整" -ForegroundColor Green
    return $true
} elseif ($fixed) {
    Write-Host "  ✅ 自动修复完成" -ForegroundColor Green
    return $true
} else {
    Write-Host "  ⚠ 发现问题 ($($issues.Count) 项):" -ForegroundColor Yellow
    foreach ($issue in $issues) { Write-Host "    • $issue" -ForegroundColor Yellow }
    return $false
}
