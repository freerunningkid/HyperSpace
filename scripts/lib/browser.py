#!/usr/bin/env python3
"""
Browser CLI — Playwright 浏览器自动化，替代 MCP browser tools
不依赖 MCP，直接 CLI 调用，Cookie/登录态持久化。

用法:
  python scripts/lib/browser.py open <url>            打开网页 → 返回文本+截图
  python scripts/lib/browser.py click <selector>      点击元素 → 返回快照
  python scripts/lib/browser.py type <text> [sel]     输入文本
  python scripts/lib/browser.py screenshot [path]     截图保存
  python scripts/lib/browser.py snap                  获取页面文本快照
  python scripts/lib/browser.py js <code>             执行 JS
  python scripts/lib/browser.py close                 清理状态（删除 Cookie/缓存）

状态管理:
  - D:/tmp/browser_state/ 下的 user_data 目录持久化 Cookie/localStorage
  - 每次命令启动即用，用完关闭，登录态自动保持
  - browser.py close 清理状态（退出登录）
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

STATE_DIR = Path("D:/tmp/browser_state")
PROFILE_DIR = STATE_DIR / "profile"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# ── 浏览器引擎 ──────────────────────────────────────────────


def _ensure_playwright():
    """确保 playwright 可用"""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        print("[ERROR] Playwright 未安装。运行: pip install playwright && python -m playwright install chromium")
        sys.exit(1)


def _context_kwargs():
    """构造持久化上下文参数"""
    kwargs = {
        "user_data_dir": str(PROFILE_DIR),
        "headless": True,
        "args": ["--no-sandbox", "--disable-gpu"],
        "viewport": {"width": 1280, "height": 900},
        "locale": "zh-CN",
    }
    return kwargs


def _open_page(p, url: str) -> dict:
    """打开页面，返回文本快照 + 截图路径"""
    context = p.chromium.launch_persistent_context(**_context_kwargs())
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    title = page.title()
    text = page.locator("body").inner_text()
    if len(text) > 5000:
        text = text[:5000] + f"\n\n... (truncated, total {len(text)} chars)"

    ts = int(time.time() * 1000)
    ss_path = str(STATE_DIR / f"screenshot_{ts}.png")
    page.screenshot(path=ss_path, full_page=False)

    context.close()
    return {"title": title, "url": url, "text": text, "screenshot": ss_path}


def _click(p, selector: str) -> dict:
    """点击元素，返回更新后的快照"""
    context = p.chromium.launch_persistent_context(**_context_kwargs())
    page = context.pages[0] if context.pages else context.new_page()
    try:
        page.click(selector, timeout=10000)
        page.wait_for_timeout(500)
        text = page.locator("body").inner_text()
        if len(text) > 4000:
            text = text[:4000] + f"\n\n... (truncated, total {len(text)} chars)"
        title = page.title()
        ts = int(time.time() * 1000)
        ss_path = str(STATE_DIR / f"screenshot_{ts}.png")
        page.screenshot(path=ss_path, full_page=False)
        result = {"title": title, "url": page.url, "text": text, "screenshot": ss_path, "clicked": selector}
    except Exception as e:
        result = {"error": str(e), "clicked": selector}
    context.close()
    return result


def _type_text(p, text: str, selector: str = "") -> dict:
    """输入文本"""
    context = p.chromium.launch_persistent_context(**_context_kwargs())
    page = context.pages[0] if context.pages else context.new_page()
    try:
        if selector:
            page.fill(selector, text, timeout=10000)
        else:
            page.keyboard.type(text)
        result = {"typed": text[:100], "selector": selector or "(focused)"}
    except Exception as e:
        result = {"error": str(e)}
    context.close()
    return result


def _screenshot(p, path: str = "") -> dict:
    """截图"""
    context = p.chromium.launch_persistent_context(**_context_kwargs())
    page = context.pages[0] if context.pages else context.new_page()
    ts = int(time.time() * 1000)
    spath = path or str(STATE_DIR / f"screenshot_{ts}.png")
    try:
        page.screenshot(path=spath, full_page=False)
        result = {"screenshot": spath}
    except Exception as e:
        result = {"error": str(e)}
    context.close()
    return result


def _snapshot(p) -> dict:
    """获取页面文本快照"""
    context = p.chromium.launch_persistent_context(**_context_kwargs())
    page = context.pages[0] if context.pages else context.new_page()
    try:
        text = page.locator("body").inner_text()
        if len(text) > 5000:
            text = text[:5000] + f"\n\n... (truncated, total {len(text)} chars)"
        result = {"title": page.title(), "url": page.url, "text": text}
    except Exception as e:
        result = {"error": str(e)}
    context.close()
    return result


def _execute_js(p, code: str) -> dict:
    """执行 JavaScript"""
    context = p.chromium.launch_persistent_context(**_context_kwargs())
    page = context.pages[0] if context.pages else context.new_page()
    try:
        js_result = page.evaluate(code)
        result_str = json.dumps(js_result, ensure_ascii=False, indent=2)
        if len(result_str) > 5000:
            result_str = result_str[:5000] + "\n... (truncated)"
        result = {"result": result_str}
    except Exception as e:
        result = {"error": str(e)}
    context.close()
    return result


def _close():
    """清理浏览器状态目录"""
    import shutil
    if PROFILE_DIR.exists():
        shutil.rmtree(str(PROFILE_DIR))
    # 清理旧截图
    for f in STATE_DIR.glob("screenshot_*.png"):
        f.unlink()
    return {"status": "cleaned", "dir": str(STATE_DIR)}


# ── CLI ─────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="浏览器自动化 CLI（替代 MCP）")
    sub = parser.add_subparsers(dest="command")

    p_open = sub.add_parser("open", help="打开网页")
    p_open.add_argument("url", help="完整 URL")

    p_click = sub.add_parser("click", help="点击元素")
    p_click.add_argument("selector", help="元素选择器 (text=, #id, .class, CSS)")

    p_type = sub.add_parser("type", help="输入文本")
    p_type.add_argument("text", help="要输入的文本")
    p_type.add_argument("selector", nargs="?", default="", help="目标输入框选择器")

    p_ss = sub.add_parser("screenshot", help="截图")
    p_ss.add_argument("path", nargs="?", default="", help="保存路径")

    sub.add_parser("snap", help="获取页面文本快照")
    sub.add_parser("close", help="清理所有浏览器状态")

    p_js = sub.add_parser("js", help="执行 JavaScript")
    p_js.add_argument("code", help="JS 代码")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "close":
        result = _close()
        print(json.dumps(result, ensure_ascii=False))
        return

    sp = _ensure_playwright()
    with sp() as p:
        if args.command == "open":
            result = _open_page(p, args.url)
        elif args.command == "click":
            result = _click(p, args.selector)
        elif args.command == "type":
            result = _type_text(p, args.text, args.selector)
        elif args.command == "screenshot":
            result = _screenshot(p, args.path)
        elif args.command == "snap":
            result = _snapshot(p)
        elif args.command == "js":
            result = _execute_js(p, args.code)
        else:
            result = {"error": f"unknown command: {args.command}"}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
