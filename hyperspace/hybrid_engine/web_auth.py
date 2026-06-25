"""Web Auth —— DeepSeek 凭据自动提取与刷新.

核心思路:
  1. 优先尝试 CDP 连接已运行的 Chrome (用户可能已经以调试模式启动)
  2. 如果 Chrome 未运行, 自动以 headless 模式拉起 → 提取 → 关闭
  3. 如果 Chrome 正在运行但无调试端口, 自动重启 Chrome (带 --restore-last-session)

使用方式:
  python -m hyperspace.hybrid_engine.web_auth --extract    # 手动提取
  python -m hyperspace.hybrid_engine.web_auth --auto        # 自动提取
  python -m hyperspace.hybrid_engine.web_auth --status      # 查看凭据状态
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hyperspace.web_auth")

# ── 路径 ──
_PKG_DIR = Path(__file__).resolve().parent.parent.parent  # hyperspace 的父目录的父目录
_DATA_DIR = _PKG_DIR / "data"
_AUTH_FILE = _DATA_DIR / "deepseek_web_auth.json"

# Chrome 候选路径
_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


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
    """检查已保存的凭据是否有效 (检查 bearer 和 cookie)."""
    if auth is None:
        auth = load_saved_auth()
    if not auth:
        return False
    # Bearer token 优先 (新版认证方式)
    bearer = auth.get("bearer", "")
    if bearer and len(bearer) > 20:
        return True
    cookie = auth.get("cookie", "")
    return bool(cookie) and ("d_id=" in cookie or "ds_session_id=" in cookie)


def has_bearer(auth: dict | None = None) -> bool:
    """检查是否有有效的 Bearer Token (新版 API 必需)."""
    if auth is None:
        auth = load_saved_auth()
    if not auth:
        return False
    bearer = auth.get("bearer", "")
    return bool(bearer) and len(bearer) > 20


# ── Chrome 管理 ──

def _find_chrome() -> str | None:
    """找到本机 Chrome 可执行文件路径."""
    for p in _CHROME_PATHS:
        if Path(p).exists():
            return p
    # 尝试 PATH
    import shutil
    found = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium-browser")
    return found


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """检查端口是否被监听."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _is_chrome_running() -> bool:
    """检查 Chrome 进程是否正在运行."""
    import subprocess
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/fi", "imagename eq chrome.exe", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=5
            )
            return "chrome.exe" in result.stdout.lower()
        else:
            result = subprocess.run(
                ["pgrep", "-x", "chrome"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
    except Exception:
        return False


def _start_chrome_for_extraction(cdp_port: int, timeout: float = 30.0) -> subprocess.Popen | None:
    """启动 Chrome 以提取凭据.

    策略:
      - Chrome 未运行: 复制 Default profile → 启动 Chrome → 提取 → 清理
      - Chrome 正在运行: 报告并跳过 (不打扰用户)

    返回 (Chrome 进程, 临时目录路径), 或 (None, None) 如果启动失败.
    """
    import shutil
    import tempfile

    chrome_path = _find_chrome()
    if not chrome_path:
        logger.error("找不到 Chrome 浏览器")
        return None, None

    is_running = _is_chrome_running()

    if is_running:
        logger.warning("Chrome 正在运行中, 无法自动重启. 请以调试模式重启 Chrome 或等待 Chrome 关闭.")
        return None, None

    # 找到用户的 Chrome 默认 profile
    if sys.platform == "win32":
        user_data_parent = Path(os.environ["LOCALAPPDATA"]) / "Google" / "Chrome" / "User Data"
    elif sys.platform == "darwin":
        user_data_parent = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    else:
        user_data_parent = Path.home() / ".config" / "google-chrome"

    default_profile = user_data_parent / "Default"
    if not default_profile.exists():
        logger.error(f"找不到 Chrome Default profile: {default_profile}")
        return None, None

    # 创建临时 user-data-dir 并只复制关键文件
    temp_dir = Path(tempfile.mkdtemp(prefix="hyperspace_chrome_"))
    temp_default = temp_dir / "Default"
    temp_default.mkdir(parents=True, exist_ok=True)

    # 只复制身份验证相关的关键文件 (Cookies, Login Data, Local Storage, Preferences)
    key_files = ["Cookies", "Cookies-journal", "Login Data", "Login Data-journal", "Preferences"]
    key_dirs = ["Local Storage", "Network"]

    for fname in key_files:
        src = default_profile / fname
        if src.exists():
            shutil.copy2(src, temp_default / fname)
            logger.debug(f"已复制 {fname}")

    for dname in key_dirs:
        src_dir = default_profile / dname
        if src_dir.is_dir():
            shutil.copytree(src_dir, temp_default / dname, dirs_exist_ok=True)
            logger.debug(f"已复制 {dname}/")

    # 写入 Local State 文件 (Chrome 需要)
    local_state = user_data_parent / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, temp_dir / "Local State")

    logger.info(f"临时 profile 准备完成: {temp_dir}")

    # 启动 Chrome
    cmd = [
        chrome_path,
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"Chrome 已启动 (PID {proc.pid}), 等待初始化...")
        return proc, temp_dir
    except Exception as e:
        logger.error(f"启动 Chrome 失败: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, None


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
            "d_id=" in cookie_str or "ds_session_id=" in cookie_str
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

        print("\n[HyperSpace] ⚠️ 未检测到登录会话，请在 Chrome 窗口中完成登录/验证码。")
        print("[HyperSpace]    登录成功后凭据自动捕获，浏览器自动关闭。")
        print("[HyperSpace]    等待中 (最多 5 分钟)...\n", flush=True)

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


# ── 自动提取 (零手动) ──

async def _extract_via_playwright_injection() -> dict | None:
    """使用 Playwright 自动提取 Bearer Token.

    有 Cookie → 注入后自动登录捕获
    无 Cookie → 打开浏览器等用户手动登录后捕获
    """
    old_auth = load_saved_auth()
    has_cookies = bool(old_auth and old_auth.get("cookie"))
    cookie_str = old_auth.get("cookie", "") if old_auth else ""

    # 解析为 Playwright 格式
    cookies_to_set = []
    for part in cookie_str.split("; "):
        if "=" in part:
            name, value = part.split("=", 1)
            cookies_to_set.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".deepseek.com",
                "path": "/",
            })

    logger.info(f"Playwright: 注入 {len(cookies_to_set)} 个 Cookie...")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("\n[HyperSpace] ⚠️ Playwright 未安装。运行以下命令后重试：")
        print("  pip install playwright")
        print("  playwright install chromium\n")
        return None

    # 确保 Chromium 已安装 (Playwright 自带, 不依赖系统浏览器)
    import subprocess as _sp
    try:
        async with async_playwright() as _test:
            await _test.chromium.launch(headless=True)
    except Exception:
        print("\n[HyperSpace] ⚠️ Playwright Chromium 未安装，正在自动安装 (~150MB)...")
        try:
            _sp.run([sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True, capture_output=True, timeout=120)
            print("[HyperSpace] ✅ Chromium 安装完成!\n")
        except Exception as e:
            print(f"[HyperSpace] ❌ 自动安装失败: {e}")
            print("  请手动运行: playwright install chromium\n")
            return None

    async with async_playwright() as pw:
        # 使用 Playwright 自带的 Chromium (无需用户装 Chrome)
        browser = await pw.chromium.launch(
            headless=False,
            args=["--no-first-run", "--no-default-browser-check", "--disable-extensions"],
        )

        try:
            context = await browser.new_context()
            if cookies_to_set:
                await context.add_cookies(cookies_to_set)
            page = await context.new_page()

            captured_bearer: list[str] = []

            async def on_request(request):
                if "/api/v0/" in request.url and not captured_bearer:
                    auth = request.headers.get("authorization", "")
                    if auth.startswith("Bearer "):
                        captured_bearer.append(auth[7:])
                        logger.info("Playwright: 捕获 Bearer Token")

            async def on_response(response):
                if "/api/v0/users/current" in response.url and response.ok and not captured_bearer:
                    try:
                        body = await response.json()
                        token = body.get("data", {}).get("biz_data", {}).get("token", "")
                        if token:
                            captured_bearer.append(token)
                            logger.info("Playwright: 从响应提取 Token")
                    except Exception:
                        pass

            page.on("request", on_request)
            page.on("response", on_response)

            await page.goto("https://chat.deepseek.com/", wait_until="domcontentloaded", timeout=30000)

            # 快速检测：是否已登录 (10s 内能抓到 Bearer)
            for _ in range(10):
                if captured_bearer:
                    break
                await asyncio.sleep(1)

            if not captured_bearer:
                # Cookie 过期或无 Cookie (新用户)
                print("\n[HyperSpace] ⚠️ 需要在 DeepSeek 登录。请在打开的浏览器中注册/登录。")
                print("[HyperSpace]    支持手机号/邮箱/Google/GitHub 登录。")
                print("[HyperSpace]    登录成功后凭据自动捕获，浏览器自动关闭。")
                print("[HyperSpace]    等待中 (最多 5 分钟)...\n", flush=True)

                # 轮询等待，每次检查页面 URL (可能跳转到登录页再跳回)
                for i in range(300):  # 5 分钟 = 300 * 1s
                    if captured_bearer:
                        break
                    # 每 10s 打印一次进度
                    if i > 0 and i % 30 == 0:
                        print(f"[HyperSpace]    已等待 {i}s...", flush=True)
                    await asyncio.sleep(1)

            if not captured_bearer:
                print("[HyperSpace] ❌ 登录超时 (5 分钟)，浏览器即将关闭。", flush=True)
                return None

            # 获取最终 cookie
            final_cookies = await context.cookies(["https://chat.deepseek.com"])
            cookie_parts = [f"{c['name']}={c['value']}" for c in final_cookies]
            final_cookie_str = "; ".join(cookie_parts)
            user_agent = await page.evaluate("navigator.userAgent")

            return {
                "cookie": final_cookie_str,
                "bearer": captured_bearer[0],
                "user_agent": user_agent,
            }

        finally:
            await browser.close()


async def auto_extract(
    cdp_port: int = 9222,
    login_timeout: float = 120.0,
) -> dict:
    """自动提取 DeepSeek 凭据, 零手动操作.

    策略:
      1. 尝试 CDP 连接已运行的 Chrome (如果端口开放)
      2. 尝试 Playwright Cookie 注入 (注入已有 Cookie, 拦截 Bearer)
      3. 如果都失败, 尝试启动 Chrome + CDP (需要 Chrome 空闲)

    Returns:
        {cookie, bearer, user_agent}
    """

    # Step 1: 尝试已有 CDP 连接
    if _is_port_open(cdp_port):
        logger.info("检测到 Chrome CDP 端口已开放, 直接连接...")
        try:
            result = await extract_from_browser(cdp_port, timeout=login_timeout)
            if result and result.get("bearer") and result.get("cookie"):
                save_auth(result)
                logger.info("自动提取成功 (已有 CDP)")
                return result
            logger.warning("CDP 连接成功但未获取到完整凭据")
        except Exception as e:
            logger.warning(f"已有 CDP 连接失败: {e}")

    # Step 2: 尝试 Playwright Cookie 注入 (最可靠的方式)
    logger.info("尝试 Playwright Cookie 注入...")
    try:
        result = await _extract_via_playwright_injection()
        if result and result.get("bearer"):
            save_auth(result)
            logger.info("自动提取成功 (Playwright)")
            return result
    except Exception as e:
        logger.warning(f"Playwright 注入失败: {e}")

    # Step 3: 自动启动 Chrome (最后手段)
    logger.info("启动 Chrome 以提取凭据...")
    chrome_proc, temp_dir = _start_chrome_for_extraction(cdp_port, timeout=login_timeout)

    if not chrome_proc:
        raise RuntimeError("无法启动 Chrome 浏览器 (可能正在运行中)")

    import shutil

    try:
        max_wait = 20
        for i in range(max_wait):
            if _is_port_open(cdp_port):
                logger.info(f"Chrome CDP 端口已就绪 (等待 {i}s)")
                break
            await asyncio.sleep(1)
        else:
            raise RuntimeError(f"Chrome 启动超时 (等待 {max_wait}s), CDP 端口未开放")

        await asyncio.sleep(3)
        result = await extract_from_browser(cdp_port, timeout=login_timeout)
        if result and result.get("cookie"):
            save_auth(result)
            logger.info("自动提取成功")
            return result
        raise RuntimeError("凭据提取失败: 返回为空")
    finally:
        if chrome_proc:
            try:
                chrome_proc.terminate()
                chrome_proc.wait(timeout=5)
            except Exception:
                try:
                    chrome_proc.kill()
                except Exception:
                    pass
        if temp_dir:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


def auto_extract_sync(cdp_port: int = 9222, login_timeout: float = 120.0) -> dict | None:
    """同步版自动提取, 返回凭据 dict 或 None."""
    try:
        return asyncio.run(auto_extract(cdp_port, login_timeout))
    except Exception as e:
        logger.error(f"自动提取失败: {e}")
        return None


# ── CLI 入口 ──

def main():
    """CLI 入口."""
    import argparse

    parser = argparse.ArgumentParser(description="DeepSeek Web 凭据管理")
    parser.add_argument("--extract", action="store_true", help="从浏览器提取凭据 (需 Chrome 调试模式)")
    parser.add_argument("--auto", action="store_true", help="自动提取凭据 (自动管理 Chrome 生命周期)")
    parser.add_argument("--status", action="store_true", help="查看凭据状态")
    parser.add_argument("--cdp-port", type=int, default=9222, help="Chrome CDP 端口 (默认 9222)")
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
            print(f"   Bearer: {'已设置' if bearer else '无 (新版 API 需要)'}")
            print(f"   Cookie: {cookie[:80]}...")
            print(f"   保存时间: {time.ctime(auth.get('saved_at', 0))}")
        else:
            print("[!!] 无有效凭据. 请运行 --auto 自动提取.")

    elif args.auto:
        print("自动提取 DeepSeek 凭据中...")
        result = auto_extract_sync(cdp_port=args.cdp_port)
        if result:
            print(f"\n[OK] 凭据已保存:")
            print(f"   Bearer: {result.get('bearer', '')[:30]}...")
            print(f"   Cookie: {result.get('cookie', '')[:80]}...")
            print(f"   User-Agent: {result.get('user_agent', '')[:60]}...")
        else:
            print("\n[!!] 自动提取失败. 请手动运行 --extract 并确保 Chrome 已登录 DeepSeek.")

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
