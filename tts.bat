@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "TEXT=%*"
if "%TEXT%"=="" exit /b 0

REM Step 0: Auto-start server if not running
curl.exe -s --max-time 1 "http://127.0.0.1:9877/ping" >nul 2>&1
if !errorlevel! neq 0 (
    start /MIN "" pythonw "%~dp0scripts\lib\tts_server.py"
    timeout /t 2 /nobreak >nul
)

REM Step 1: Use PowerShell for proper URL encoding
powershell -NoProfile -Command ^
  "$t=[System.Web.HttpUtility]::UrlEncode($env:TEXT);" ^
  "try{$r=Invoke-WebRequest -Uri \"http://127.0.0.1:9877/?text=$t\" -TimeoutSec 10 -UseBasicParsing;exit 0}catch{exit 1}" >nul 2>&1
if !errorlevel! equ 0 exit /b 0

REM Step 2: Fallback — speak.py in current process (may be silent in sandbox)
python "%~dp0scripts\lib\speak.py" %TEXT% >nul 2>&1
exit /b 0
