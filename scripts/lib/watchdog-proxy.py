"""
watchdog-proxy.py — Reasonix 移动端代理的看门狗
=============================================
功能：
  1. 启动 serve-mobile-proxy.py
  2. 如果它意外退出（崩溃/被杀），自动重启
  3. 记录重启事件到日志

用法：
  python D:\Reasonix\scripts\lib\watchdog-proxy.py

建议通过 start-serve.vbs 在开机时自动启动。
"""

import os
import subprocess
import sys
import time
import datetime

# ── 路径配置 ──
PROXY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serve-mobile-proxy.py")
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "watchdog.log")


def log(msg: str):
    """写日志到文件和控制台"""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [watchdog] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    log("看门狗启动")
    consecutive_crashes = 0

    while True:
        log(f"启动代理进程 (尝试 #{consecutive_crashes + 1})...")
        proc = subprocess.Popen(
            [sys.executable, PROXY_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        log(f"代理进程已启动 (PID {proc.pid})")

        # 等待进程结束
        proc.wait()

        exit_code = proc.returncode
        log(f"代理进程已退出 (PID {proc.pid}, exit code {exit_code})")

        if exit_code == 0:
            # 正常退出（用户主动停止），不重启
            log("代理正常退出，看门狗停止")
            break

        # 异常退出，自动重启
        consecutive_crashes += 1
        wait_time = min(consecutive_crashes * 2, 30)  # 退避：2s, 4s, 6s... 最多30秒
        log(f"代理异常退出，{wait_time} 秒后重启...")
        time.sleep(wait_time)

        # 连续崩溃太多次，加倍等待
        if consecutive_crashes >= 10:
            log(f"连续崩溃 {consecutive_crashes} 次，等待 60 秒...")
            time.sleep(60)

        if consecutive_crashes >= 20:
            log(f"连续崩溃 {consecutive_crashes} 次，等待 300 秒后只再试一次...")
            time.sleep(300)

    log("看门狗停止")


if __name__ == "__main__":
    main()
