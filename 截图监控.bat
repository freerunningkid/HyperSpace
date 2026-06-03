@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "LOCK=%cd%\.screenshot_monitor.lock"
set "VBS=%cd%\截图监控.vbs"

if /i "%~1"=="install" goto :install
if /i "%~1"=="uninstall" goto :uninstall
if /i "%~1"=="stop" goto :stop
if /i "%~1"=="status" goto :status

:start
echo 启动截图监视器（后台静默）...
cscript //nologo "%VBS%"
echo 已启动！监视器在后台运行中。
echo.
echo 其他命令: %~nx0 install  ^|  uninstall  ^|  stop  ^|  status
goto :end

:install
echo 设置开机自启...
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if not exist "%STARTUP%" mkdir "%STARTUP%"
echo Set ws = CreateObject("Wscript.Shell") > "%STARTUP%\截图监控.vbs"
echo ws.CurrentDirectory = "%~dp0" >> "%STARTUP%\截图监控.vbs"
echo ws.Run "pythonw ""%~dp0scripts\lib\clipboard_monitor.py""", 0, False >> "%STARTUP%\截图监控.vbs"
echo ✓ 已添加到启动文件夹
echo   下次开机自动运行
goto :end

:uninstall
echo 移除开机自启...
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP%\截图监控.vbs" del /q "%STARTUP%\截图监控.vbs"
if exist "%STARTUP%\截图监控.vbs" (
    echo ✗ 删除失败，请手动删除: %STARTUP%\截图监控.vbs
) else (
    echo ✓ 已移除开机自启
)
goto :end

:stop
if not exist "%LOCK%" (
    echo 监视器未运行（无锁文件）
    goto :end
)
for /f "tokens=*" %%i in ('type "%LOCK%" ^| python -c "import sys,json; print(json.load(sys.stdin).get('pid',0))" 2^>nul') do set PID=%%i
if "%PID%"=="" (
    echo 无法读取 PID，直接删除锁文件
    del /q "%LOCK%"
    goto :end
)
echo 停止 PID %PID% ...
taskkill /pid %PID% /f >nul 2>&1
if exist "%LOCK%" del /q "%LOCK%"
echo ✓ 已停止
goto :end

:status
if exist "%LOCK%" (
    for /f "tokens=*" %%i in ('type "%LOCK%" ^| python -c "import sys,json; d=json.load(sys.stdin); print(f'PID={d[\"pid\"]}  启动={d[\"started\"][:19]}')" 2^>nul') do echo 运行中 · %%i
    tasklist /fi "PID eq %PID%" 2>nul | findstr /c:"python" >nul 2>&1
    if errorlevel 1 echo ⚠️ 锁文件存在但进程可能已退出
) else (
    echo 未运行
)
goto :end

:end
