#!/usr/bin/env python3
"""
relay_15721.py - (已弃用) Claude 汉化版桌面端端口中继
不再需要 — model_proxy.py 已在端口 15721 直接处理 /claude-desktop/ 前缀。
保留仅作参考。
"""

import http.server
import json
import requests
import sys
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("relay")

UPSTREAM = "http://127.0.0.1:8030"
HOST = "127.0.0.1"
PORT = 15721


def _strip_prefix(path):
    """去掉 /claude-desktop 前缀"""
    if path.startswith("/claude-desktop"):
        return path[len("/claude-desktop"):] or "/"
    return path


def _proxy_request(method, path, body=None, headers=None):
    """转发请求到上游 model_proxy"""
    upstream_path = _strip_prefix(path)
    url = f"{UPSTREAM}{upstream_path}"

    # 透传关键 header
    upstream_headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    # 透传 auth token
    if headers and "x-api-key" in headers:
        upstream_headers["x-api-key"] = headers["x-api-key"]
    if headers and "Authorization" in headers:
        upstream_headers["Authorization"] = headers["Authorization"]

    log.info(f"  relay: {path} -> {upstream_path}")

    try:
        resp = requests.request(
            method, url,
            headers=upstream_headers,
            json=body,
            timeout=120,
        )
        return resp.status_code, resp.json() if resp.text else {}, resp.headers
    except requests.exceptions.ConnectionError:
        return 502, {"error": "model_proxy not running on " + UPSTREAM}, {}
    except Exception as e:
        return 500, {"error": str(e)}, {}


class RelayHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_len)
        body = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}

        status, data, resp_headers = _proxy_request("POST", self.path, body, self.headers)
        self._send_json(data, status)

    def do_GET(self):
        # /health 和 /v1/models 直接本地处理或转发
        if self.path == "/health":
            # 检查上游是否活着
            try:
                r = requests.get(f"{UPSTREAM}/health", timeout=3)
                data = r.json()
                data["relay"] = "active"
                self._send_json(data, 200)
            except Exception:
                self._send_json({"relay": "active", "upstream": "unreachable"}, 502)
            return

        status, data, _ = _proxy_request("GET", self.path)
        self._send_json(data, status)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    server = http.server.HTTPServer((HOST, PORT), RelayHandler)
    print(f"=== Claude Desktop Relay ===")
    print(f"Listening: http://{HOST}:{PORT}")
    print(f"Upstream: {UPSTREAM} (model_proxy)")
    print(f"Handles: /claude-desktop/v1/messages -> /v1/messages")
    print()
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
