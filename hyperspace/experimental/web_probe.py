# -*- coding: utf-8 -*-
"""
web_probe —— DeepSeek 网页端通用对话 CLI (实验/个人用, 违 ToS).

CLI: 传入文本 prompt → 用 Playwright 自动化 DeepSeek 网页端对话 → 打印回复.

用法:
    python -m hyperspace.experimental.web_probe "你好，介绍一下你自己"
    python -m hyperspace.experimental.web_probe --prompt "写一段Python冒泡排序"
    echo "复杂问题" | python -m hyperspace.experimental.web_probe --stdin

首次运行会打开浏览器窗口, 请手动扫码登录; 之后自动复用登录态.
与 web_vision.py 共享 session.py 的登录态和等待逻辑.
本模块严格隔离: 不接入 MCP, 不被 server.py import.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .session import close_session, get_session, send_and_wait


def main():
    parser = argparse.ArgumentParser(
        description="DeepSeek 网页端通用对话 (个人实验)",
        epilog="首次运行会弹出浏览器, 请手动扫码登录.",
    )
    parser.add_argument(
        "prompt", nargs="?",
        help="提问文字 (省略时与 --stdin 配合使用)",
    )
    parser.add_argument(
        "--prompt", "-p", dest="prompt_flag",
        help="交替指定 prompt 的方式",
    )
    parser.add_argument(
        "--stdin", action="store_true",
        help="从 stdin 读取 prompt (支持管道)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="无头模式 (默认 False, 首次需 headed 登录)",
    )

    args = parser.parse_args()

    # 确定 prompt: --prompt > position arg > --stdin
    prompt = args.prompt_flag or args.prompt
    if args.stdin or not prompt:
        prompt = sys.stdin.read().strip()
    if not prompt:
        parser.print_help()
        print("\n[web_probe] ⛔ 请提供 prompt (参数或 --stdin)", file=sys.stderr)
        sys.exit(1)

    print(f"[web_probe] 💬 prompt: {prompt[:80]}...", file=sys.stderr, flush=True)

    # 启动 session
    page, context, pw = get_session(headless=args.headless)

    try:
        # 发送 + 等待回复
        result = send_and_wait(page, prompt)

        # 打印结果 (stdout, 纯文本)
        print("\n" + "=" * 50)
        print(result)
        print("=" * 50)

    finally:
        close_session(page, context, pw)


if __name__ == "__main__":
    main()
