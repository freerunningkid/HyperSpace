@echo off
REM reasonix-voice.bat — 启动 Reasonix + 自动语音朗读
REM 监控会话 JSONL 文件，assistant 回复自动 TTS，永不会忘

echo.
echo 🎤 启动语音监控 + Reasonix Code ...
echo.

REM 启动语音监控（后台）
start /B python D:\Reasonix\scripts\mcp\voice_monitor.py

REM 等监控器就位
timeout /t 1 /nobreak >nul

REM 启动 Reasonix
npx reasonix code

REM Reasonix 退出后，清理监控器
taskkill /F /IM python.exe /FI "WINDOWTITLE eq voice_monitor*" >nul 2>&1
echo.
echo 语音监控已停止。
