#!/usr/bin/env python3
"""用 Playwright 提取 DeepSeek Web 凭据（无需手动开调试模式）"""

import asyncio, json, time, sys
from pathlib import Path
from playwright.async_api import async_playwright

AUTH_FILE = Path(__file__).parent.parent / "data" / "deepseek_web_auth.json"
captured_bearer = ""


async def extract():
    global captured_bearer

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context()
        page = await ctx.new_page()

        # 拦截网络请求，捕获 Bearer Token
        async def on_response(response):
            global captured_bearer
            url = response.url
            if "/api/v0/users/current" in url and response.status == 200:
                try:
                    body = await response.json()
                    if "token" in body:
                        captured_bearer = body["token"]
                        print(f"[HyperSpace] 已从 API 捕获 Bearer Token")
                except Exception:
                    pass
            # 也检查 Authorization 请求头
            if not captured_bearer:
                try:
                    auth = response.request.headers.get("authorization", "")
                    if auth.startswith("Bearer ") and len(auth) > 30:
                        captured_bearer = auth[7:]
                        print(f"[HyperSpace] 已从请求头捕获 Bearer Token")
                except Exception:
                    pass

        page.on("response", on_response)

        print("[HyperSpace] 正在打开 chat.deepseek.com ...")
        await page.goto("https://chat.deepseek.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # 检查是否需要登录
        current_url = page.url
        if "auth" in current_url or "login" in current_url or "signin" in current_url:
            print("[HyperSpace] 请在浏览器窗口中登录 DeepSeek")
            print("   登录后页面会自动跳转，然后按 Enter 继续...")
            input()
        else:
            print("[HyperSpace] 检测到已登录状态")
            # 触发一次 API 请求来捕获 token
            await page.goto("https://chat.deepseek.com", wait_until="networkidle")
            await page.wait_for_timeout(2000)

        # 主动调用 API 获取 Token
        print("[HyperSpace] 正在获取 Token...")
        try:
            token_result = await page.evaluate("""async () => {
                try {
                    const resp = await fetch('/api/v0/users/current', {
                        credentials: 'include',
                        headers: { 'Accept': 'application/json' }
                    });
                    if (resp.ok) {
                        const data = await resp.json();
                        // 尝试从多个可能的位置取 token
                        return data.token || data.data?.token || data.accessToken || '';
                    }
                    return '';
                } catch(e) { return ''; }
            }""")
            if token_result and len(token_result) > 20:
                captured_bearer = token_result
                print(f"[HyperSpace] 已获取 Token (长度: {len(token_result)})")
        except Exception as e:
            print(f"[HyperSpace] API 获取 Token 失败: {e}")

        # 如果上面的方法没拿到，尝试从 JS 上下文取
        if not captured_bearer:
            try:
                local_token = await page.evaluate("""() => {
                    try {
                        // 尝试各种可能的存储位置
                        for (const key of ['auth_token', 'token', 'accessToken', 'user_token']) {
                            const v = localStorage.getItem(key);
                            if (v && v.length > 20) return v;
                        }
                        // 尝试全局变量
                        const win = window;
                        return win.__NUXT__?.state?.user?.token
                            || win.__INITIAL_STATE__?.user?.token
                            || win.__NEXT_DATA__?.props?.pageProps?.token
                            || '';
                    } catch(e) { return ''; }
                }""")
                if local_token and len(local_token) > 20:
                    captured_bearer = local_token
                    print(f"[HyperSpace] 从 JS 上下文获取 Token (长度: {len(local_token)})")
            except Exception as e:
                print(f"[HyperSpace] JS 获取 Token 失败: {e}")

        # 提取 Cookie
        cookies = await ctx.cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

        user_agent = await page.evaluate("navigator.userAgent")

        auth_data = {
            "cookie": cookie_str,
            "bearer": captured_bearer,
            "user_agent": user_agent,
            "saved_at": time.time(),
        }

        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(auth_data, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] 凭据已保存到 {AUTH_FILE}")
        print(f"   Cookie: {cookie_str[:60]}...")
        print(f"   Bearer: {captured_bearer[:30]}..." if captured_bearer else "   [WARN] 未捕获到 Bearer Token")
        print(f"   Token 长度: {len(captured_bearer)}" if captured_bearer else "")

        input("\n按 Enter 关闭浏览器...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(extract())
