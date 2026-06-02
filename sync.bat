@echo off
chcp 65001 >nul
cd /d D:\Reasonix

echo ============================
echo   同步到 GitHub
echo ============================

echo [1/3] 添加变更...
git add -A

echo [2/3] 提交...
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set dt=%%I
set ts=%dt:~0,4%-%dt:~4,2%-%dt:~6,2% %dt:~8,2%:%dt:~10,2%:%dt:~12,2%
git commit -m "sync: %ts%"

echo [3/3] 推送...
git push origin master

echo ============================
echo   完成！
echo ============================
pause
