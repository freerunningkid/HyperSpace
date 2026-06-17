@echo off
chcp 65001 >nul
title OpenCode WSL Launcher
echo ========================================
echo   OpenCode Desktop + WSL Server
echo ========================================
echo.

echo [1/3] Getting WSL IP...
for /f "tokens=*" %%i in ('wsl -d Ubuntu -- bash -c "hostname -I"') do set WSL_IP=%%i
echo        WSL IP: %WSL_IP%

wsl -d Ubuntu -- bash -c "echo WSL Ready" >nul 2>&1

echo [2/3] Starting OpenCode WSL Server...
set PWD=opencode-kid2025
start "OpenCode-Server" wsl -d Ubuntu -- bash -c "OPENCODE_SERVER_PASSWORD=%PWD% opencode serve --hostname 0.0.0.0 --port 4096"

echo [3/3] Waiting for server ready...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   Server: http://%WSL_IP%:4096
echo   Password: %PWD%
echo ========================================
echo.

set DESKTOP_APP=D:\ÁÙÊ±\opencode-desktop-win-x64.exe
if exist "%DESKTOP_APP%" (
    echo Starting OpenCode Desktop...
    start "" "%DESKTOP_APP%"
) else (
    echo [Note] Desktop app not found: %DESKTOP_APP%
    echo        Connect manually to http://%WSL_IP%:4096
)

echo.
echo Done! Press any key to close...
pause >nul