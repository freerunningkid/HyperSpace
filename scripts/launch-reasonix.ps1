param(
    [string]$TargetDir = ""
)

# ============================================================
# launch-reasonix.ps1 — 右键菜单启动 Reasonix 对话
# Tier 1: Windows Terminal + PowerShell  (最好)
# Tier 2: 独立 PowerShell 窗口          (次选)
# Tier 3: cmd 兜底                      (最差)
# ============================================================

# 解析目标目录
if (-not $TargetDir) { $TargetDir = Get-Location }
if (Test-Path $TargetDir -PathType Leaf) {
    $TargetDir = Split-Path $TargetDir -Parent
}
if (-not (Test-Path $TargetDir -PathType Container)) {
    Write-Host "错误：找不到目录 '$TargetDir'"
    Start-Sleep 3
    exit 1
}

# 检查 reasonix 命令
if (-not (Get-Command reasonix -ErrorAction SilentlyContinue).Source) {
    Write-Host "错误：未找到 reasonix 命令，请确认已在 PATH 中"
    Start-Sleep 3
    exit 1
}

# 守护启动器脚本路径
$GuardScript = "D:\Reasonix\scripts\reasonix-guard.ps1"

# == Tier 1: Windows Terminal + PowerShell 7（最佳体验）==
if (Get-Command wt.exe -ErrorAction SilentlyContinue) {
    Start-Process wt.exe -ArgumentList @(
        "-d", "`"$TargetDir`"",          # Windows Terminal 工作目录
        "pwsh", "-NoExit", "-File", "`"$GuardScript`"", "-TargetDir", "`"$TargetDir`""
    )
    exit 0
}

# == Tier 2: 独立 PowerShell 窗口 ==
if (Get-Command pwsh.exe -ErrorAction SilentlyContinue) {
    Start-Process pwsh.exe -ArgumentList @(
        "-NoExit",
        "-File", "`"$GuardScript`"", "-TargetDir", "`"$TargetDir`""
    )
    exit 0
}

# == Tier 3: cmd 兜底（无法运行 ps1，保持原样）==
Start-Process cmd.exe -ArgumentList "/k", "cd /d `"$TargetDir`" & echo === Reasonix === & echo 工作目录: $TargetDir & echo. & reasonix chat"