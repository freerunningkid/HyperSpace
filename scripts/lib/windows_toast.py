"""
Windows 原生弹窗 — Python 直接调用 Win32 API
比其他方式更稳定，不受 PowerShell 编码问题影响。

返回: ALLOW | DENY | TIMEOUT
"""
import ctypes
import ctypes.wintypes
import sys
import threading
import time

# Windows API 常量
MB_YESNO = 0x04
MB_ICONQUESTION = 0x20
MB_SYSTEMMODAL = 0x1000
MB_TOPMOST = 0x40000
IDYES = 6
IDNO = 7
IDTIMEOUT = 32000

user32 = ctypes.windll.user32


def show_messagebox(title: str, message: str, timeout_sec: int = 120) -> str:
    """显示 Windows 原生消息框，返回 ALLOW / DENY / TIMEOUT"""

    result = [IDTIMEOUT]
    done = threading.Event()

    def show():
        r = user32.MessageBoxW(0, message, title, MB_YESNO | MB_ICONQUESTION | MB_SYSTEMMODAL | MB_TOPMOST)
        result[0] = r
        done.set()

    t = threading.Thread(target=show, daemon=True)
    t.start()

    if not done.wait(timeout=timeout_sec):
        # 超时，尝试关闭消息框
        try:
            # 查找并关闭消息框窗口
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.SendMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        except Exception:
            pass
        return "TIMEOUT"

    if result[0] == IDYES:
        return "ALLOW"
    elif result[0] == IDNO:
        return "DENY"
    else:
        return "TIMEOUT"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Claude Code")
    parser.add_argument("--message", default="需要您的确认")
    parser.add_argument("--allow", default="允许")
    parser.add_argument("--deny", default="拒绝")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    # MessageBoxW 不支持自定义按钮文字（只能用"是/否"），
    # 把自定义按钮名放在消息里提示
    msg = f"{args.message}\n\n请选择：{args.allow} / {args.deny}"
    result = show_messagebox(args.title, msg, args.timeout)
    print(f"RESULT:{result}")


if __name__ == "__main__":
    main()
