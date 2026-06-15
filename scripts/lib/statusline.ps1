#!/usr/bin/env pwsh
# statusline.ps1 — Reasonix 自定义状态行
# 从 stdin 接收 JSON: {"model","contextUsed","contextWindow","cwd"}
# 输出紧凑单行，优先保证信息完整

$ErrorActionPreference = "Stop"

try {
    # 读 stdin — 优先管道输入，次选 console stdin
    if ($MyInvocation.ExpectingInput) {
        $json = $input | Out-String
    } else {
        [Console]::InputEncoding = [System.Text.Encoding]::UTF8
        $json = [Console]::In.ReadToEnd()
    }

    if ([string]::IsNullOrWhiteSpace($json)) {
        exit 0
    }

    $data = $json | ConvertFrom-Json

    $model   = $data.model
    $ctxUsed = [long]$data.contextUsed
    $ctxWin  = [long]$data.contextWindow
    $cwd     = $data.cwd

    # 格式化 token 数：>= 1M 显示为 M，>= 1K 显示为 K
    function Format-Tokens { param([long]$n)
        if    ($n -ge 1000000) { return "$([math]::Round($n / 1e6, 1))M" }
        elseif ($n -ge 1000)   { return "$([math]::Round($n / 1e3, 1))K" }
        else                   { return "$n" }
    }

    $usedStr  = Format-Tokens $ctxUsed
    $winStr   = Format-Tokens $ctxWin
    $pct      = if ($ctxWin -gt 0) { [math]::Round($ctxUsed / $ctxWin * 100, 1) } else { 0 }
    $dirLabel = Split-Path $cwd -Leaf

    # 从 D:\Reasonix\reasonix.toml 读取 effort（CLI 配置来源）
    $effort = ""
    $tomlPath = "D:\Reasonix\reasonix.toml"
    if (Test-Path $tomlPath) {
        try {
            $toml = Get-Content $tomlPath -Raw
            if ($toml -match '(?m)^\s*effort\s*=\s*"([^"]+)"') {
                $effort = " ($($matches[1]))"
            }
        } catch {
            # 静默失败，不影响状态行
        }
    }

    # 输出单行 — 尽可能短但包含完整信息
    Write-Output "$model$effort | $usedStr/$winStr ($pct%) | $dirLabel"

} catch {
    # 静默失败，让 Reasonix 回退到默认 statusline
    exit 0
}
