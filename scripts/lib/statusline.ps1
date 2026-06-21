<#
.SYNOPSIS
  Reasonix 中文状态行 — 一行显示模型/费用/缓存/上下文/消息数
  接收 stdin JSON: {"model","contextUsed","contextWindow","cwd"}
  输出一行替换底部状态栏
#>

$ErrorActionPreference = "Stop"
$stdin = $input | Out-String
if ([string]::IsNullOrEmpty($stdin) -or $stdin.Trim() -eq "") {
    Write-Host "💫 等待数据..."
    exit 0
}

# 去除可能的 BOM
if ($stdin[0] -eq 0xFEFF) { $stdin = $stdin.Substring(1) }

try {
    $data = $stdin | ConvertFrom-Json
} catch {
    Write-Host "⚙️ 就绪"
    exit 0
}

$cwd = if ($data.cwd) { $data.cwd } else { "" }
$ctxUsed = [double]($data.contextUsed -as [double] -or 0)
$ctxWin  = [double]($data.contextWindow -as [double] -or 0)

# ---- 模型名简写 ----
$modelRaw = if ($data.model) { $data.model } else { "" }
$modelShort = switch -Wildcard ($modelRaw) {
    "deepseek-v4-flash*"   { "DS V4F" }
    "deepseek-v4-pro*"     { "DS V4P" }
    "agnes*"               { "Agnes" }
    "glm*"                 { "GLM" }
    "qwen*"                { "QWen" }
    default                { if ($modelRaw -match "/([^/]+)$") { $matches[1] } else { $modelRaw } }
}

# ---- 会话 meta ----
$sessionDir = Join-Path $env:USERPROFILE ".reasonix\sessions"
$meta = $null
if (Test-Path $sessionDir) {
    $metas = Get-ChildItem "$sessionDir\*.meta.json" | Sort-Object LastWriteTime -Descending
    $meta = $null
    # 优先匹配当前工作区
    if ($cwd) {
        foreach ($m in $metas) {
            try {
                $content = Get-Content $m.FullName -Raw -Encoding UTF8
                if ($content -match '"workspace"\s*:\s*"([^"]+)"') {
                    $ws = $matches[1]
                    if ($ws -and $cwd.StartsWith($ws)) {
                        $meta = $content | ConvertFrom-Json
                        break
                    }
                }
            } catch { continue }
        }
    }
    if (-not $meta -and $metas.Count -gt 0) {
        try {
            $meta = Get-Content $metas[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch { }
    }
}

# ---- 字段计算 ----
$parts = @()

# 模型
$parts += $modelShort

# 费用 (USD → CNY, 汇率 7.2)
if ($meta -and $meta.totalCostUsd) {
    $costCny = [double]$meta.totalCostUsd * 7.2
    if ($costCny -ge 1) {
        $costStr = "￥{0:N2}" -f $costCny
    } elseif ($costCny -ge 0.01) {
        $costStr = "￥{0:N4}" -f $costCny
    } else {
        $costStr = "￥{0:N6}" -f $costCny
    }
    $parts += "费用 $costStr"
}

# 缓存命中率
if ($meta -and $meta.cacheHitTokens -and $meta.cacheMissTokens) {
    $hit = [double]$meta.cacheHitTokens
    $miss = [double]$meta.cacheMissTokens
    $total = $hit + $miss
    if ($total -gt 0) {
        $pct = [math]::Round($hit / $total * 100)
        $parts += "缓存 $pct%"
    }
}

# 上下文用量 + 进度条
if ($ctxWin -gt 0) {
    $ctxPct = [math]::Round($ctxUsed / $ctxWin * 100)
    $barLen = 5
    $filled = [math]::Floor($ctxPct / 100 * $barLen)
    $empty = $barLen - $filled
    $bar = ("█" * $filled) + ("░" * $empty)
    $parts += "上下文 $ctxPct% $bar"
}

# 消息数
if ($meta -and $meta.turnCount) {
    $parts += "$($meta.turnCount) 条消息"
}

# ---- 输出 ----
$line = $parts -join " │ "
Write-Host $line
