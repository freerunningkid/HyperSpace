@echo off
chcp 65001 >nul
echo ============================================
echo   KID-Reasonix MCP Installer
echo ============================================
echo.

set "MCP_DIR=%~dp0tools-工具\github-mcp-server"
set "ZIP=%TEMP%\gh-mcp.zip"

if not exist "%MCP_DIR%" mkdir "%MCP_DIR%"

echo [1/2] Downloading github-mcp-server v1.1.2 (7MB)...

:: Try direct first, then mirror
curl -L --ssl-no-revoke --connect-timeout 15 -o "%ZIP%" "https://github.com/github/github-mcp-server/releases/download/v1.1.2/github-mcp-server_Windows_x86_64.zip"
if %errorlevel% neq 0 (
    echo Direct slow, trying mirror...
    curl -L -o "%ZIP%" "https://ghproxy.net/https://github.com/github/github-mcp-server/releases/download/v1.1.2/github-mcp-server_Windows_x86_64.zip"
)
if %errorlevel% neq 0 (
    echo [ERROR] Download failed.
    pause
    exit /b 1
)

echo [2/2] Extracting...
tar -xf "%ZIP%" -C "%MCP_DIR%"
del "%ZIP%"

if exist "%MCP_DIR%\github-mcp-server.exe" (
    echo.
    echo ============================================
    echo   Done!
    echo   Restart Reasonix to enable GitHub MCP
    echo ============================================
) else (
    echo [ERROR] github-mcp-server.exe not found!
)
pause
