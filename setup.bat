@echo off
echo ============================================
echo   KID-Reasonix 配置同步部署
echo ============================================
echo.

set "SRC=%~dp0"
set "REASONIX_DIR=%USERPROFILE%\.reasonix"
set "CLAUDE_DIR=%USERPROFILE%\.claude"

echo [1/2] 部署 Reasonix 配置...
if not exist "%REASONIX_DIR%" mkdir "%REASONIX_DIR%"
REM 不覆盖 config.json（含 apiKey），其他文件正常同步
if exist "%REASONIX_DIR%\config.json" (
    xcopy "%SRC%config\reasonix\sessions\*" "%REASONIX_DIR%\sessions\" /E /H /Y >nul 2>&1
    echo   跳过 config.json（保留现有 apiKey）
) else (
    echo   首次部署，请编辑 %REASONIX_DIR%\config.json 添加 apiKey
    xcopy "%SRC%config\reasonix\*" "%REASONIX_DIR%\" /E /H /Y >nul
)
echo   完成: %REASONIX_DIR%

echo [2/2] 部署 Claude Code 配置...
if not exist "%CLAUDE_DIR%" mkdir "%CLAUDE_DIR%"
xcopy "%SRC%config\claude\*" "%CLAUDE_DIR%\" /E /H /Y >nul
echo   完成: %CLAUDE_DIR%

echo.
echo ============================================
echo   部署完成！
echo   重新启动 Reasonix 即可使用最新配置
echo ============================================
pause
