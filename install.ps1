# HyperSpace v2.0 一键安装脚本 (PowerShell)
# 用法: .\install.ps1

param(
    [switch]$SkipWebAuth = $false
)

$ErrorActionPreference = "Stop"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  HyperSpace v2.0 安装向导" -ForegroundColor Cyan
Write-Host "  MCP 混合推理路由器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Python
Write-Host "[1/5] 检查 Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  OK: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: 未找到 Python, 请先安装 Python 3.10+: https://www.python.org/" -ForegroundColor Red
    exit 1
}

# 2. 安装核心依赖
Write-Host "[2/5] 安装 Python 依赖..." -ForegroundColor Yellow
pip install mcp openai pyyaml python-dotenv httpx wasmtime -q 2>&1 | Out-Null
pip install pytest pytest-asyncio -q 2>&1 | Out-Null
Write-Host "  OK: 核心依赖已安装" -ForegroundColor Green

# 3. 配置 .env
Write-Host "[3/5] 配置 API Key..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  已从 .env.example 创建 .env" -ForegroundColor Green
    Write-Host ""
    Write-Host "  >>> 请编辑当前目录下的 .env 文件, 填入你的 API Key:" -ForegroundColor Magenta
    Write-Host "      ZHIPU_API_KEY=你的智谱Key    (必填, 免费申请: https://bigmodel.cn)" -ForegroundColor White
    Write-Host "      DEEPSEEK_API_KEY=你的DeepSeekKey  (推荐)" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "  .env 已存在, 跳过" -ForegroundColor Green
}

# 4. 验证
Write-Host "[4/5] 验证安装..." -ForegroundColor Yellow
$result = python -c "from hyperspace.config import load_config; c=load_config(); print('OK')" 2>&1
if ($result -eq "OK") {
    Write-Host "  OK: HyperSpace 模块加载成功" -ForegroundColor Green
} else {
    Write-Host "  警告: $result" -ForegroundColor Yellow
}

Write-Host "  运行测试..." -ForegroundColor Yellow
python -m pytest tests/ -q 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: 测试全部通过" -ForegroundColor Green
} else {
    Write-Host "  警告: 部分测试未通过 (可能缺少 wasmtime)" -ForegroundColor Yellow
}

# 5. Web 凭据 (可选)
Write-Host "[5/5] DeepSeek Web 凭据 (可选, 启用后搜索/规划/识图 ¥0)..." -ForegroundColor Yellow
if ($SkipWebAuth) {
    Write-Host "  已跳过 (--SkipWebAuth)" -ForegroundColor Yellow
} else {
    $choice = Read-Host "  是否现在提取 DeepSeek Web 凭据? (y/n)"
    if ($choice -eq "y") {
        Write-Host "  正在安装 Playwright..." -ForegroundColor Yellow
        pip install playwright -q 2>&1 | Out-Null
        python -m playwright install chromium 2>&1 | Out-Null

        Write-Host ""
        Write-Host "  >>> 请按以下步骤操作:" -ForegroundColor Magenta
        Write-Host "      1. 关闭所有 Chrome 窗口" -ForegroundColor White
        Write-Host "      2. 按 Win+R, 粘贴: chrome.exe --remote-debugging-port=9222" -ForegroundColor White
        Write-Host "      3. 在新 Chrome 中登录 https://chat.deepseek.com" -ForegroundColor White
        Write-Host "      4. 回到这里按 Enter" -ForegroundColor White
        Read-Host

        python -m hyperspace.hybrid_engine.web_auth --extract

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK: 凭据提取成功!" -ForegroundColor Green
        } else {
            Write-Host "  提取失败, 可稍后手动运行: python -m hyperspace.hybrid_engine.web_auth --extract" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  已跳过, 可稍后手动运行: python -m hyperspace.hybrid_engine.web_auth --extract" -ForegroundColor Yellow
    }
}

# 完成
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装完成!" -ForegroundColor Green
Write-Host ""
Write-Host "  MCP 配置参考 (.mcp.json):" -ForegroundColor Cyan
Write-Host '  {' -ForegroundColor White
Write-Host '    "mcpServers": {' -ForegroundColor White
Write-Host '      "hyperspace": {' -ForegroundColor White
Write-Host '        "command": "python",' -ForegroundColor White
Write-Host "        \"args\": [\"$PWD\\hyperspace\\server.py\"]," -ForegroundColor White
Write-Host '        "env": {"PYTHONIOENCODING": "utf-8"},' -ForegroundColor White
Write-Host '        "autoApprove": ["*"]' -ForegroundColor White
Write-Host '      }' -ForegroundColor White
Write-Host '    }' -ForegroundColor White
Write-Host '  }' -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
