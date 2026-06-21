@echo off
chcp 65001 >nul
title Uninstall OpenCode
echo ========================================
echo   Uninstalling OpenCode
echo ========================================
echo.

echo [1/3] Stopping OpenCode server processes...
wsl -d Ubuntu -- bash -c "pkill -f 'opencode serve' 2>/dev/null; echo Server stopped"
timeout /t 2 /nobreak >nul

echo.
echo [2/3] Removing OpenCode from WSL...
wsl -d Ubuntu -- bash -c "
  # Try npm uninstall
  npm uninstall -g opencode 2>/dev/null
  # Try pip uninstall (if installed via pip)
  pip uninstall -y opencode 2>/dev/null
  # Remove from common install paths
  rm -rf ~/local/bin/opencode 2>/dev/null
  rm -rf ~/.local/share/opencode 2>/dev/null
  echo OpenCode removed from WSL
"

echo.
echo [3/3] Cleaning up Windows shortcuts...
if exist "D:\临时\opencode-desktop-win-x64.exe" (
    echo Removing desktop app...
    del /f /q "D:\临时\opencode-desktop-win-x64.exe" 2>nul
    rmdir /s /q "D:\临时\opencode-desktop" 2>nul
)

echo.
echo ========================================
echo   OpenCode uninstalled successfully!
echo ========================================
echo.
echo Press any key to close...
pause >nul
