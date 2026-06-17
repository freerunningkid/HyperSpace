$ErrorActionPreference = "Stop"

Write-Host "正在移除右键菜单 Reasonix 对话..." -ForegroundColor Cyan

# 要移除的注册表路径
$paths = @(
    "HKCU:\Software\Classes\Directory\Background\shell\Reasonix",
    "HKCU:\Software\Classes\Directory\shell\Reasonix",
    "HKCU:\Software\Classes\Drive\shell\Reasonix"
)

foreach ($path in $paths) {
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force
        Write-Host "  + 已移除：$path" -ForegroundColor Green
    } else {
        Write-Host "  - 不存在：$path" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "<< 卸载完成！>>" -ForegroundColor Green
Write-Host "提示：可能需要按 F5 刷新 Explorer。" -ForegroundColor Yellow
