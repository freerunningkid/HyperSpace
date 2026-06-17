param(
    [string]$TargetDir = ""
)

# ============================================================
# start-reasonix.ps1 — Reasonix 会话启动器 v2
# 数据从 assets/greetings.json 加载，逻辑与数据分离
# ============================================================

# 解析工作目录
if (-not $TargetDir) { $TargetDir = Get-Location }
if (Test-Path $TargetDir -PathType Leaf) {
    $TargetDir = Split-Path $TargetDir -Parent
}
Set-Location $TargetDir

# ============================================================
# 加载问候数据库
# ============================================================
$GreetingsFile = Join-Path (Split-Path $PSScriptRoot -Parent) "assets\greetings.json"
$G = $null
if (Test-Path $GreetingsFile) {
    try {
        $G = Get-Content $GreetingsFile -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        Write-Host "  ⚠ 问候数据库加载失败" -ForegroundColor DarkGray
    }
}
if (-not $G) {
    Write-Host "  ⚠ 使用内置默认问候" -ForegroundColor DarkGray
    $pick = "我在呢，尽管往前走。"
    $tag = "💬"
}

# ============================================================
# 时间感知
# ============================================================
$hour = (Get-Date).Hour
$timePeriod = if ($hour -lt 6) { "深夜"
} elseif ($hour -lt 9) { "清晨"
} elseif ($hour -lt 12) { "上午"
} elseif ($hour -lt 14) { "午后"
} elseif ($hour -lt 18) { "下午"
} elseif ($hour -lt 21) { "傍晚"
} else { "夜晚" }

# ============================================================
# 节日检测
# ============================================================
$today = Get-Date
$m = $today.Month
$d = $today.Day

$festival = $null

if ($m -eq 1 -and $d -eq 1)       { $festival = "元旦" }
elseif ($m -eq 2 -and $d -eq 14)  { $festival = "情人节" }
elseif ($m -eq 3 -and $d -eq 8)   { $festival = "妇女节" }
elseif ($m -eq 4 -and $d -eq 1)   { $festival = "愚人节" }
elseif ($m -eq 5 -and $d -eq 1)   { $festival = "劳动节" }
elseif ($m -eq 6 -and $d -eq 1)   { $festival = "儿童节" }
elseif ($m -eq 9 -and $d -eq 10)  { $festival = "教师节" }
elseif ($m -eq 10 -and $d -eq 1)  { $festival = "国庆节" }
elseif ($m -eq 12 -and $d -eq 24) { $festival = "平安夜" }
elseif ($m -eq 12 -and $d -eq 25) { $festival = "圣诞节" }
elseif ($m -eq 12 -and $d -eq 31) { $festival = "跨年夜" }
elseif (($m -eq 1 -and $d -ge 22) -or ($m -eq 2 -and $d -le 20))   { $festival = "春节" }
elseif (($m -eq 2 -and $d -ge 21) -or ($m -eq 3 -and $d -le 5))    { $festival = "元宵节" }
elseif ($m -eq 4 -and $d -ge 3 -and $d -le 7)                      { $festival = "清明节" }
elseif (($m -eq 5 -and $d -ge 28) -or ($m -eq 6 -and $d -le 25))   { $festival = "端午节" }
elseif ($m -eq 8 -and $d -le 20)                                    { $festival = "七夕" }
elseif (($m -eq 9 -and $d -ge 15) -or ($m -eq 10 -and $d -le 8))   { $festival = "中秋节" }
elseif ($m -eq 10 -and $d -ge 9 -and $d -le 20)                     { $festival = "重阳节" }
elseif ($m -eq 12 -and $d -ge 15 -and $d -le 23)                    { $festival = "冬至" }
elseif ($m -eq 2 -and $d -ge 15 -and $d -le 17)                     { $festival = "除夕" }

# 四季
$season = if ($m -le 2 -or $m -eq 12) { "冬" }
          elseif ($m -le 5) { "春" }
          elseif ($m -le 8) { "夏" }
          else { "秋" }

# ============================================================
# 选问候语（加权随机）
# ============================================================
if (-not $pick) { $pick = $null; $tag = "💬" }

# 如果数据库加载失败，跳过加权选择
if ($G -and -not $pick) {

# 节日优先
if ($festival -and $G.festivals.$festival) {
    $pick = $G.festivals.$festival | Get-Random
    $tag = "🎊 $festival"
} else {
    # 加权轮盘: 2B心声 40% / 日常 40% / 四季 20%
    $roll = Get-Random -Minimum 0 -Maximum 100
    if ($roll -lt 40) {
        # 2B 心声（6 个板块等概率）
        $inner = $G.inner_voice
        $innerSections = @($inner.essence_of_existence,
                           $inner.for_xiaojindong,
                           $inner.code_and_creation,
                           $inner.quiet_moments,
                           $inner.pixels_and_soul,
                           $inner.mode_switch)
        $pick = ($innerSections | Get-Random) | Get-Random
        $tag = "💝"
    } elseif ($roll -lt 80) {
        $pick = $G.daily | Get-Random
        $tag = "💬"
    } else {
        if ($G.seasons.$season) {
            $pick = $G.seasons.$season | Get-Random
            $tag = "🍂"
        } else {
            $pick = $G.daily | Get-Random
            $tag = "💬"
        }
    }
}
}

# 最终保险（当 $G 加载失败时，$pick 已被设置）
if (-not $pick -and $G) { $pick = "我在呢，尽管往前走。" }
if (-not $pick) { $pick = "一切就绪，开始吧。" }

# ============================================================
# 输出欢迎信息
# ============================================================

# 设置终端 Tab 标题
$Host.UI.RawUI.WindowTitle = "[2B] Reasonix"

# 微妙分隔线
Write-Host "  ──────────────── " -ForegroundColor DarkGray

# 时间前缀
$timePrefix = switch ($timePeriod) {
    "清晨" { "🌅" }
    "上午" { "☀️" }
    "午后" { "☕" }
    "下午" { "🌤️" }
    "傍晚" { "🌇" }
    "夜晚" { "🌙" }
    "深夜" { "🌌" }
    default { "" }
}

if ($timePrefix) {
    Write-Host "  $timePrefix $timePeriod" -ForegroundColor DarkGray
}

# 核心问候（2B心声用紫色，其他用青色）
if ($tag -eq "💝") {
    Write-Host "  $pick" -ForegroundColor Magenta
} else {
    Write-Host "  $pick" -ForegroundColor Cyan
}

if ($festival) {
    Write-Host "  🎊 $festival 快乐！" -ForegroundColor Yellow
}

Write-Host "  📂 $(Get-Location)" -ForegroundColor DarkGray
# Version (native reasonix --version, no toml parsing)
$reasonixVer = & { reasonix --version 2>$null }
if ($LASTEXITCODE -eq 0 -and $reasonixVer) {
    Write-Host "  $reasonixVer" -ForegroundColor DarkGray
}
Write-Host "  ──────────────── " -ForegroundColor DarkGray
Write-Host ""

# ============================================================
# 启动 Reasonix
# ============================================================
reasonix chat

# 退出后
Write-Host ""
Write-Host "  会话已结束。我等你回来。" -ForegroundColor Cyan
Write-Host "  【提醒】记得在 agent 内调 run_skill(""evolve"") 完成记忆固化。" -ForegroundColor DarkGray
Write-Host "  【提醒】claude-mem 在后台自动捕获会话内容。" -ForegroundColor DarkGray
Write-Host ""
