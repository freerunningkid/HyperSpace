# -*- coding: utf-8 -*-
"""
DeepSeek 网页会话管理 (实验/个人用, 违 ToS).

共享登录态持久化逻辑, 供 web_vision.py/web_probe.py 复用.
首次运行打开浏览器 → 手动扫码登录 → 自动保存登录态;
之后免登录, 可直接使用.

用法:
    from hyperspace.experimental.session import get_session
    page, context, playwright = get_session()
    # ... 在 page 上操作 ...
    playwright.stop()

Playwright 延迟导入, 不设模块级依赖——允许 --help 等 CLI 操作无 Playwright 运行.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# ── 路径 ──
_PKG_DIR = Path(__file__).resolve().parent  # experimental/
_PROJECT_ROOT = _PKG_DIR.parent.parent       # HyperSpace/
DATA_DIR = _PROJECT_ROOT / "data"
SESSION_FILE = DATA_DIR / "deepseek_session.json"
DEEPSEEK_URL = "https://chat.deepseek.com/"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _import_playwright():
    """延迟加载 Playwright; 保证 --help 等不需要 playwright 的操作不受影响."""
    try:
        from playwright.sync_api import sync_playwright as _sp
        return _sp
    except ImportError:
        print(
            "[experimental] ⚠ 需要 Playwright 才能运行此命令.\n"
            "   pip install playwright && python -m playwright install chromium",
            file=sys.stderr, flush=True,
        )
        sys.exit(1)


def get_session(
    headless: bool = False,
    login_timeout: int = 120_000,
) -> tuple[Any, Any, Any]:
    """
    返回 (page, context, playwright).

    - 首次: headless=False 弹出浏览器, 请手动扫码登录
    - 之后: 自动复用 `data/deepseek_session.json` 的登录态

    调用方负责在结束后调用 playwright.stop().
    """
    sync_playwright = _import_playwright()
    _ensure_data_dir()

    p = sync_playwright().start()
    context_args: dict = {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    if SESSION_FILE.exists():
        context_args["storage_state"] = str(SESSION_FILE)
        print(f"[session] 📂 加载已有登录态: {SESSION_FILE}", file=sys.stderr, flush=True)
    else:
        print("[session] ⚠ 未找到登录态, 将在浏览器中等待手动登录.", file=sys.stderr, flush=True)

    browser = p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(**context_args)
    page = context.new_page()
    page.goto(DEEPSEEK_URL)

    # 等待输入区出现 (登录成功的标志)
    input_selectors = [
        "textarea",
        "div[contenteditable='true']",
        "#chat-input",
        "[data-testid='chat-input']",
    ]
    found = False
    for sel in input_selectors:
        try:
            page.wait_for_selector(sel, timeout=10_000)
            found = True
            break
        except Exception:
            continue

    if not found:
        print("[session] 🔑 未检测到输入区, 请在弹出的浏览器中扫码登录.", file=sys.stderr, flush=True)
        page.wait_for_timeout(2000)
        page.wait_for_selector(
            "textarea, div[contenteditable='true'], input[type='text']",
            timeout=login_timeout,
        )
        context.storage_state(path=str(SESSION_FILE))
        print(f"[session] ✅ 登录态已保存到 {SESSION_FILE}", file=sys.stderr, flush=True)
    elif not SESSION_FILE.exists():
        context.storage_state(path=str(SESSION_FILE))
        print(f"[session] ✅ 登录态已保存到 {SESSION_FILE}", file=sys.stderr, flush=True)
    else:
        print("[session] ✅ 页面已就绪, 输入区可见.", file=sys.stderr, flush=True)

    return page, context, p


def close_session(page, context, playwright):
    """安全关闭浏览器会话."""
    try:
        context.storage_state(path=str(SESSION_FILE))
    except Exception:
        pass
    try:
        browser = context.browser
        if browser:
            browser.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass
