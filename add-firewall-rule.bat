@echo off
chcp 65001 >nul
title 添加防火墙规则 — 移动端代理 8787
echo 正在添加防火墙规则（允许 TCP 8787 入站）...
echo.
netsh advfirewall firewall add rule name="serve-mobile-proxy-8787" dir=in action=allow protocol=TCP localport=8787
echo.
if %errorlevel% equ 0 (
    echo ✅ 规则添加成功！你现在可以用手机访问了。
) else (
    echo ❌ 失败。请右键本文件 → "以管理员身份运行"。
)
echo.
pause
