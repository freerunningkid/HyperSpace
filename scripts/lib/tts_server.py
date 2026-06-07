"""TTS HTTP Server — 监听 127.0.0.1:9877，委托 speak.py 走完整降级链。

架构:
  HTTP GET /?text=xxx → speak.py (Edge streaming → Edge save → SAPI5)

用法:
  python tts_server.py              # 前台运行
  pythonw tts_server.py             # 后台静默（不弹窗口）

调用:
  curl "http://127.0.0.1:9877/?text=你好小金东"
  curl "http://127.0.0.1:9877/?你好小金东"
"""
import sys
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Path setup: scripts/lib/ ← speak.py ──
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
sys.path.insert(0, LIB)
from speak import speak as _speak_tts

HOST = "127.0.0.1"
PORT = 9877


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            text = params.get("text", [""])[0]
            if not text:
                text = urllib.parse.unquote(parsed.path.strip("/?"))

            if not text:
                self.send_error(400, "no text")
                return

            ok = _speak_tts(text)

            if ok:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                preview = text[:50].replace("\n", " ")
                self.wfile.write(f"ok: {preview}".encode("utf-8"))
            else:
                self.send_error(500, "所有 TTS 引擎均失败")
        except Exception as e:
            self.send_error(500, str(e))


def main():
    srv = HTTPServer((HOST, PORT), Handler)
    print(f"[tts-server] TTS (Edge streaming → Edge save → SAPI5) @ http://{HOST}:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
