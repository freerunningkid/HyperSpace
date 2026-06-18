"""
serve-mobile-proxy.py — Reasonix 移动端反向代理
===============================================
功能：
  1. 在内部端口 127.0.0.1:3000 启动 reasonix serve（避开 Hyper-V 预留 8450-9050）
  2. 在 0.0.0.0:8300 启动反向代理，转发请求到内部端口
  3. 对 HTML 响应注入移动端适配修复（safe-area + keyboard）

用法：
  python D:/Reasonix/scripts/lib/serve-mobile-proxy.py

依赖：
  aiohttp (已安装)
"""

import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import time
import datetime

# 确保 stdout 支持 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import aiohttp
from aiohttp import web

# ── 日志 ──────────────────────────────────────────────────
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "proxy.log")


def log(msg: str):
    """写日志到文件和控制台"""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
PUBLIC_PORT = 8300          # 外部访问端口（避开了 Hyper-V 预留范围 8450-9050）
INTERNAL_PORT = 3000        # 内部 reasonix serve 端口
BACKEND_URL = f"http://127.0.0.1:{INTERNAL_PORT}"

# ── 注入的 CSS ─────────────────────────────────────────────
INJECT_CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=no">
<style id="rx-mobile-fix">
/* ── 移动端适配 ── */
@media (max-width: 768px) {
  html, body { height: 100%; overflow: hidden; }
  .app {
    height: 100dvh !important;
    grid-template-columns: 1fr !important;
  }
  .sidebar { display: none !important; }
  .footer {
    padding-bottom: max(env(safe-area-inset-bottom, 0px), 8px) !important;
    background: var(--bg) !important;
  }
  .composer { margin-bottom: 0 !important; }
  /* 让输入框区域在键盘弹出时仍然可见 */
  .transcript { padding-bottom: 8px !important; }
}
</style>
"""

# ── 注入的 JS ──────────────────────────────────────────────
INJECT_JS = """
<script id="rx-mobile-fix">
(function(){
  'use strict';
  /* 等待 DOM 就绪 */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    /* 如果 visualViewport 不可用，跳过 JS 修复 */
    if (!window.visualViewport) return;

    var app = document.querySelector('.app');
    var footer = document.querySelector('.footer');
    if (!app || !footer) return;

    function adjust() {
      var vv = window.visualViewport;
      /* 键盘弹出时 innerHeight 不变，visualViewport.height 缩小 */
      var hiddenByKeyboard = Math.max(0, window.innerHeight - vv.height);
      /* 页面被推上去的距离 */
      var offsetTop = vv.offsetTop;

      if (hiddenByKeyboard > 80) {
        /* 键盘弹出：固定 app 高度为可见区域 */
        app.style.height = vv.height + 'px';
        app.style.position = 'fixed';
        app.style.top = vv.offsetTop + 'px';
        app.style.left = vv.offsetLeft + 'px';
        app.style.width = vv.width + 'px';
        app.style.zIndex = '1';
        footer.style.paddingBottom = '8px';
      } else {
        /* 键盘关闭：恢复默认，信任 safe-area-inset-bottom */
        app.style.position = '';
        app.style.top = '';
        app.style.left = '';
        app.style.width = '';
        app.style.height = '';
        app.style.zIndex = '';
        footer.style.paddingBottom = '';
      }
    }

    window.visualViewport.addEventListener('resize', adjust);
    window.addEventListener('orientationchange', function() {
      setTimeout(adjust, 300);
    });

    /* 初始调整 */
    adjust();
  }
})();
</script>
"""


# ── 后端进程管理 ──────────────────────────────────────────
backend_proc = None


def start_reasonix_serve():
    """启动内部 reasonix serve 进程"""
    global backend_proc
    # 使用 shell=True 以支持 .cmd 文件
    cmd = f"reasonix serve --addr 127.0.0.1:{INTERNAL_PORT}"
    kwargs = {
        "args": cmd,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "shell": True,
        "creationflags": subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    }
    backend_proc = subprocess.Popen(**kwargs)
    return backend_proc


def stop_backend():
    """停止后端进程"""
    global backend_proc
    if backend_proc and backend_proc.poll() is None:
        try:
            backend_proc.terminate()
            backend_proc.wait(timeout=5)
        except Exception:
            try:
                backend_proc.kill()
            except Exception:
                pass
    backend_proc = None


# ── 反向代理核心 ──────────────────────────────────────────
async def proxy_handler(request):
    """通用反向代理处理器"""
    path = request.rel_url
    url = f"{BACKEND_URL}{path}"
    is_sse = str(path).endswith('/events')

    # 转发 headers
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ('host', 'content-length')}

    try:
        async with aiohttp.ClientSession(auto_decompress=False) as session:
            data = await request.read()
            async with session.request(
                method=request.method,
                url=url,
                headers=headers,
                data=data,
                params=request.query,
                allow_redirects=False,
            ) as resp:
                content_type = resp.headers.get('Content-Type', '')

                # ── SSE 事件流（直接透传，不注入） ──
                if is_sse or 'text/event-stream' in content_type:
                    sr = web.StreamResponse(
                        status=resp.status,
                        headers={k: v for k, v in resp.headers.items() if k.lower() not in ('content-length', 'transfer-encoding')},
                    )
                    await sr.prepare(request)
                    async for chunk in resp.content.iter_any():
                        await sr.write(chunk)
                    return sr

                # ── 普通响应：读取完整 body ──
                body = await resp.read()

                # ── HTML 注入 ──
                if 'text/html' in content_type and body:
                    # 注入 CSS（</head> 之前）
                    if b'</head>' in body:
                        body = body.replace(b'</head>', INJECT_CSS.encode('utf-8') + b'</head>')
                    # 注入 JS（</body> 之前）
                    if b'</body>' in body:
                        body = body.replace(b'</body>', INJECT_JS.encode('utf-8') + b'</body>')

                # 构建响应
                resp_headers = {k: v for k, v in resp.headers.items()
                                if k.lower() not in ('content-length', 'transfer-encoding', 'content-encoding')}
                return web.Response(
                    body=body,
                    status=resp.status,
                    headers=resp_headers,
                )
    except aiohttp.ClientConnectorError as e:
        return web.Response(
            text=f"<html><body><h1>后端未就绪</h1><p>{e}</p></body></html>",
            status=502,
            content_type='text/html',
        )
    except Exception as e:
        return web.Response(
            text=f"<html><body><h1>代理错误</h1><p>{e}</p></body></html>",
            status=500,
            content_type='text/html',
        )


# ── 主入口 ──────────────────────────────────────────────────
async def main():
    global backend_proc

    log(f"启动 reasonix serve (127.0.0.1:{INTERNAL_PORT})...")
    try:
        start_reasonix_serve()
    except FileNotFoundError:
        log("错误：找不到 reasonix 命令，请确认已安装")
        sys.exit(1)

    # 等待后端就绪
    log("等待后端就绪...")
    max_wait = 15
    for i in range(max_wait):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"http://127.0.0.1:{INTERNAL_PORT}/") as r:
                    if r.status == 200:
                        log(f"后端就绪 (尝试 {i+1}/{max_wait})")
                        break
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        log(f"后端未能在 {max_wait} 秒内启动")
        stop_backend()
        sys.exit(1)

    # 启动反向代理
    app = web.Application()
    app.router.add_route('*', '/{tail:.*}', proxy_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PUBLIC_PORT)
    await site.start()
    log(f">> Mobile proxy running on http://0.0.0.0:{PUBLIC_PORT}")
    log(f"   -> forwarding to internal http://127.0.0.1:{INTERNAL_PORT}")
    log(f"   -> log: {LOG_FILE}")

    # ── 健康检查循环（自动恢复后端） ──
    health_interval = 10  # 秒
    consecutive_failures = 0

    try:
        while True:
            await asyncio.sleep(health_interval)

            # 检查后端进程是否存活
            backend_alive = backend_proc is not None and backend_proc.poll() is None

            # 检查后端 HTTP 是否可达
            http_ok = False
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(f"http://127.0.0.1:{INTERNAL_PORT}/", timeout=3) as r:
                        http_ok = r.status == 200
            except Exception:
                pass

            if not backend_alive or not http_ok:
                consecutive_failures += 1
                log(f"[health] 后端异常 (进程={'alive' if backend_alive else 'dead'}, HTTP={'ok' if http_ok else 'fail'}), 尝试 #{consecutive_failures}")

                # 清理旧进程
                stop_backend()
                await asyncio.sleep(1)

                # 重启
                try:
                    start_reasonix_serve()
                    # 等待就绪
                    for wait_i in range(15):
                        try:
                            async with aiohttp.ClientSession() as s2:
                                async with s2.get(f"http://127.0.0.1:{INTERNAL_PORT}/", timeout=2) as r2:
                                    if r2.status == 200:
                                        log(f"[health] 后端已自动恢复 (尝试 #{consecutive_failures} 后成功)")
                                        consecutive_failures = 0
                                        break
                        except Exception:
                            pass
                        await asyncio.sleep(1)
                    else:
                        log(f"[health] 后端重启失败，15秒内未就绪")
                except Exception as e:
                    log(f"[health] 启动后端时出错: {e}")
            else:
                # 正常，重置计数
                if consecutive_failures > 0:
                    log("[health] 后端已稳定运行，重置计数")
                    consecutive_failures = 0

    except (asyncio.CancelledError, KeyboardInterrupt):
        log("收到终止信号，清理中...")
    except BaseException as e:
        log(f"异常退出: {e}")
    finally:
        # 清理
        log("停止后端...")
        stop_backend()
        await runner.cleanup()
        log("已退出")


if __name__ == '__main__':
    asyncio.run(main())
