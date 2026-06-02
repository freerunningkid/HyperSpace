@echo off
cd /d D:\Reasonix

echo === Syncing to GitHub ===
echo.

echo [1/3] git add...
git add -A

echo [2/3] git commit...
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set dt=%%I
set ts=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,2%%dt:~10,2%%dt:~12,2%
git commit -m "sync: %ts%"

echo [3/3] git push...
git push origin master

echo.
echo === Done ===
pause
