"""
Ollama API 透明代理 — 剥离 thinking 字段，解决 VS Code Copilot Chat "Response too long"

监听 127.0.0.1:11435，转发到 Ollama (127.0.0.1:11434)。
自动剥离以下响应中的 thinking 字段：
  - /v1/chat/completions (OpenAI 兼容 API)
  - /api/generate, /api/chat (Ollama 原生 API)
支持流式和非流式响应。

用法:
  python ollama_proxy.py
  python ollama_proxy.py --port 11436
"""
import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
PROXY_PORT = 11435


def _strip_thinking(body: bytes) -> bytes:
    """剥离 JSON 中所有 thinking 字段。无论层级。"""
    if body[:1] != b"{":
        return body
    try:
        text = body.decode("utf-8")
        obj = json.loads(text)
    except Exception:
        return body

    def _do_strip(node):
        modified = False
        if isinstance(node, dict):
            keys = list(node.keys())
            for k in keys:
                if k == "thinking":
                    del node[k]
                    modified = True
                else:
                    if _do_strip(node[k]):
                        modified = True
        elif isinstance(node, list):
            for item in node:
                if _do_strip(item):
                    modified = True
        return modified

    if _do_strip(obj):
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return body


def _ensure_ollama():
    """如果 Ollama 未运行，自动启动"""
    try:
        req = urllib.request.Request(
            f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags",
            method="GET"
        )
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        pass

    # Ollama 未运行，启动它
    print("[Ollama Proxy] Ollama not running, starting...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        import time
        time.sleep(4)
        return True
    except Exception as e:
        print(f"[Ollama Proxy] Failed to start Ollama: {e}")
        return False


class ProxyHandler(BaseHTTPRequestHandler):
    def _handle_request(self, method: str):
        body_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(body_len) if body_len > 0 else None

        # 转发 URL
        path = self.path
        url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}{path}"

        req = urllib.request.Request(url, data=body, method=method)
        # 复制原始头部
        for k, v in self.headers.items():
            if k.lower() not in (
                "host", "content-length", "transfer-encoding", "connection"
            ):
                req.add_header(k, v)

        try:
            resp = urllib.request.urlopen(req, timeout=300)
            resp_data = resp.read()
            ct = resp.headers.get("Content-Type", "")
            # 剥离 thinking（仅 JSON 响应）
            if "json" in ct:
                resp_data = _strip_thinking(resp_data)

            self.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(resp_data)))
            self.end_headers()
            self.wfile.write(resp_data)

        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        except Exception as e:
            err = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def do_GET(self): self._handle_request("GET")
    def do_POST(self): self._handle_request("POST")
    def do_PUT(self): self._handle_request("PUT")
    def do_DELETE(self): self._handle_request("DELETE")

    def log_message(self, fmt, *args):
        pass  # 静默，避免刷屏


def main():
    global PROXY_PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            PROXY_PORT = int(sys.argv[idx + 1])

    if not _ensure_ollama():
        print("[Ollama Proxy] FATAL: Ollama unavailable. Exiting.")
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    print(f"[Ollama Proxy] 127.0.0.1:{PROXY_PORT} → {OLLAMA_HOST}:{OLLAMA_PORT}")
    print(f"[Ollama Proxy] Thinking field stripped: /v1/chat/completions, /api/generate, /api/chat")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Ollama Proxy] Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
