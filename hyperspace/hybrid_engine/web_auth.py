"""Web Auth —— 从 Chrome 浏览器提取 DeepSeek Web 登录凭据.

通过 Playwright 连接到 Chrome DevTools Protocol (CDP),
提取 chat.deepseek.com 的 Cookie + Bearer Token,
保存到本地供 DeepSeekWebClient 使用.

使用方式:
  python -m hyperspace.hybrid_engine.web_auth --extract    # 交互式提取
  python -m hyperspace.hybrid_engine.web_auth --status    # 查看凭据状态
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hyperspace.web_auth")

# ── 路径 ──
_PKG_DIR = Path(__file__).resolve().parent.parent.parent  # hyperpace 的父目录的父目录
_DATA_DIR = _PKG_DIR / "data"
_AUTH_FILE = _DATA_DIR / "deepseek_web_auth.json"


def _get_auth_path() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _AUTH_FILE


# ── 从文件加载/保存凭据 ──

def load_saved_auth() -> dict | None:
    """从 data/deepseek_web_auth.json 加载已保存的凭据."""
    path = _get_auth_path()
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"读取凭据文件失败: {e}")
        return None


def _cookie_str(cookies: list) -> str:
    """将 cookies 列表转为 header 字符串 (兼容 Python 3.10)."""
    parts = []
    for c in cookies:
        if isinstance(c, dict):
            name = c.get("name", "")
            value = c.get("value", "")
        else:
            name = c.name
            value = c.value
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def save_auth(auth: dict) -> None:
    """保存凭据到 data/deepseek_web_auth.json."""
    path = _get_auth_path()
    auth["saved_at"] = time.time()
    with path.open("w", encoding="utf-8") as f:
        json.dump(auth, f, ensure_ascii=False, indent=2)
    logger.info(f"凭据已保存到 {path}")


def is_auth_valid(auth: dict | None = None) -> bool:
    """检查已保存的凭据是否有效."""
    if auth is None:
        auth = load_saved_auth()
    if not auth:
        return False
    # Bearer token 优先 (新版认证方式)
    bearer = auth.get("bearer", "")
    if bearer and len(bearer) > 20:
        return True
    # 旧版 d_id Cookie
    cookie = auth.get("cookie", "")
    return bool(cookie) and "d_id=" in cookie


# ── Playwright CDP 凭据提取 ──

async def extract_from_browser(
    cdp_port: int = 9222,
    timeout: float = 300.0,
) -> dict:
    """连接到 Chrome CDP, 提取 DeepSeek 凭据.

    流程:
      1. 通过 CDP 连接到已存在的 Chrome
      2. 查找 chat.deepseek.com 页面或打开新页面
      3. 检查是否已登录 (Cookie)
      4. 拦截 API 请求以获取 Bearer Token
      5. 等待用户登录 (如未登录)

    Args:
        cdp_port: Chrome DevTools Protocol 端口
        timeout: 等待登录的超时时间 (秒)

    Returns:
        {cookie, bearer, user_agent}
    """
    import playwright.async_api as pw

    cdp_url = f"http://127.0.0.1:{cdp_port}"

    logger.info(f"正在连接到 Chrome CDP: {cdp_url}")

    # 等待 CDP 就绪
    ws_url = None
    for i in range(10):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{cdp_url}/json/version")
                if resp.status_code == 200:
                    ws_url = resp.json().get("webSocketDebuggerUrl")
                    if ws_url:
                        break
        except Exception:
            pass
        await asyncio.sleep(0.5)

    if not ws_url:
        raise RuntimeError(
            f"无法连接到 Chrome CDP (端口 {cdp_port}). "
            f"请先以调试模式启动 Chrome:\n"
            f'  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
            f'--remote-debugging-port=9222'
        )

    # ── 连接 Playwright ──
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(ws_url)
        context = browser.contexts[0] or await browser.new_context()

            # 查找已有 DeepSeek 页面
        page = None
        for p in context.pages:
            if "deepseek.com" in p.url:
                page = p
                await p.bring_to_front()
                break

        if not page:
            # CDP 模式下不能 new_page(), 需要导航已存在的页面或报错
            if context.pages:
                page = context.pages[0]
                await page.goto("https://chat.deepseek.com")
            else:
                raise RuntimeError(
                    "Chrome 调试窗口没有打开的页面。请确保 Chrome 窗口中至少有一个标签页。"
                )

        # 检查是否已登录 (Cookie)
        existing_cookies = await context.cookies([
            "https://chat.deepseek.com",
            "https://deepseek.com",
        ])
        cookie_str = _cookie_str(existing_cookies) if existing_cookies else ""
        has_session = (
            "d_id=" in cookie_str
        ) and len(cookie_str) > 10

        bearer = ""
        user_agent = ""

        if has_session:
            logger.info("发现已有 DeepSeek 会话 Cookie")
            user_agent = await page.evaluate("navigator.userAgent")

            # 尝试通过 API 获取 Bearer token
            try:
                response = await page.request.get(
                    "https://chat.deepseek.com/api/v0/users/current",
                    headers={"Cookie": cookie_str},
                )
                if response.ok:
                    data = await response.json()
                    bearer = (
                        data.get("data", {})
                        .get("biz_data", {})
                        .get("token", "")
                    )
            except Exception:
                pass

            # 尝试从 localStorage 提取 token
            if not bearer:
                try:
                    local_data = await page.evaluate("""() => {
                        const result = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            if (key) result[key] = localStorage.getItem(key);
                        }
                        return result;
                    }""")
                    for key, value in local_data.items():
                        kl = key.lower()
                        if "token" in kl or "auth" in kl:
                            try:
                                parsed = json.loads(value)
                                if isinstance(parsed, dict) and parsed.get("token"):
                                    bearer = parsed["token"]
                                elif isinstance(parsed, str) and len(parsed) > 20:
                                    bearer = parsed
                            except (json.JSONDecodeError, TypeError):
                                if isinstance(value, str) and len(value) > 20:
                                    bearer = value
                except Exception:
                    pass

            return {
                "cookie": cookie_str,
                "bearer": bearer,
                "user_agent": user_agent,
            }

        # ── 未登录, 导航到 DeepSeek 等待登录 ──
        logger.info("未检测到登录会话. 正在打开 chat.deepseek.com 等待登录...")
        await page.goto("https://chat.deepseek.com")
        user_agent = await page.evaluate("navigator.userAgent")

        print("\n[web_auth] [...] 请在打开的 Chrome 窗口中登录 DeepSeek 账号")
        print("[web_auth]    登录后凭据会自动捕获 (最长等待 5 分钟)\n", flush=True)

        # ── 等待登录 (拦截 API 请求) ──
        captured_bearer: list[str] = []
        resolved = asyncio.Event()

        async def on_request(request):
            url = request.url
            if "/api/v0/" in url:
                headers = request.headers
                auth = headers.get("authorization", "")
                if auth.startswith("Bearer ") and not captured_bearer:
                    captured_bearer.append(auth[7:])
                    logger.info("已捕获 Bearer Token")
                    resolved.set()

        async def on_response(response):
            url = response.url
            if "/api/v0/users/current" in url and response.ok:
                try:
                    body = await response.json()
                    token = (
                        body.get("data", {})
                        .get("biz_data", {})
                        .get("token", "")
                    )
                    if token and not captured_bearer:
                        captured_bearer.append(token)
                        resolved.set()
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # 同时轮询 cookies
        async def poll_cookies():
            while not resolved.is_set():
                await asyncio.sleep(2)
                cookies = await context.cookies([
                    "https://chat.deepseek.com",
                    "https://deepseek.com",
                ])
                cs = _cookie_str(cookies) if cookies else ""
                if (captured_bearer or has_session) and cs and ("d_id=" in cs or "ds_session_id=" in cs):
                    resolved.set()

        poll_task = asyncio.create_task(poll_cookies())

        try:
            await asyncio.wait_for(resolved.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError("登录等待超时 (5 分钟)")

        poll_task.cancel()

        # 提取最新 Cookie
        final_cookies = await context.cookies([
            "https://chat.deepseek.com",
            "https://deepseek.com",
        ])
        final_cookie_str = _cookie_str(final_cookies) if final_cookies else ""
        final_bearer = captured_bearer[0] if captured_bearer else bearer

        return {
            "cookie": final_cookie_str,
            "bearer": final_bearer,
            "user_agent": user_agent,
        }


# ── CLI 入口 ──

def main():
    """CLI 入口."""
    import argparse

    parser = argparse.ArgumentParser(description="DeepSeek Web 凭据管理")
    parser.add_argument("--extract", action="store_true", help="从浏览器提取凭据")
    parser.add_argument("--status", action="store_true", help="查看凭据状态")
    parser.add_argument("--cdp-port", type=int, default=9222, help="Chrome CDP 端口")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if args.status:
        auth = load_saved_auth()
        if auth and is_auth_valid(auth):
            cookie = auth.get("cookie", "")
            bearer = auth.get("bearer", "")
            print(f"[OK] 凭据状态: 有效")
            print(f"   Cookie:       {cookie[:80]}...")
            print(f"   Bearer Token: {bearer[:20]}..." if bearer else "   无 Bearer Token")
            print(f"   保存时间:     {time.ctime(auth.get('saved_at', 0))}")
        else:
            print("[!!] 无有效凭据. 请运行 --extract 提取.")

    elif args.extract:
        print(f"正在连接 Chrome CDP (端口 {args.cdp_port})...")
        auth = asyncio.run(extract_from_browser(cdp_port=args.cdp_port))
        if auth and auth.get("cookie"):
            save_auth(auth)
            print(f"\n[OK] 凭据已保存:")
            print(f"   Cookie: {auth['cookie'][:80]}...")
            print(f"   Bearer: {auth.get('bearer', '')[:30]}...")
            print(f"   User-Agent: {auth.get('user_agent', '')[:60]}...")
        else:
            print("\n[!!] 凭据提取失败")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
