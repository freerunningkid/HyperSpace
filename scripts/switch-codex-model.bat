@echo off
chcp 65001 >nul
title Codex Model Switcher
echo ========================================
echo   Codex 模型切换工具
echo ========================================
echo.
echo 可用模型：
echo   1) deepseek-v4
echo   2) agnes (agnes-2.0-flash)
echo.
set /p choice="请输入选择 (1/2): "

if "%choice%"=="1" (
    echo.
    echo 切换到 deepseek-v4...
    setx CODEX_MODEL "deepseek-v4" >nul 2>&1
    echo ✓ 已设置 CODEX_MODEL=deepseek-v4
) else if "%choice%"=="2" (
    echo.
    echo 切换到 agnes...
    setx CODEX_MODEL "agnes-2.0-flash" >nul 2>&1
    echo ✓ 已设置 CODEX_MODEL=agnes-2.0-flash
) else (
    echo ✗ 无效选择
    goto :end
)

echo.
echo 重启 Codex CLI 后生效
echo.
:end
pause >nul
