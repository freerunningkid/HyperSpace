#!/usr/bin/env python3
"""轻量 TTS — 本地晓晓 Natural 优先，edge-tts 网络降级，弹零窗口。"""
import re, sys, os, subprocess, tempfile, time, asyncio, traceback

TTS_MODE = os.environ.get("TALKITO_TTS", "edge").lower()


def _run_async(coro):
    """Run a coroutine safely — handles the case where we're already inside an event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside an event loop (e.g. MCP server) — run in a side thread
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def filter_text(text: str) -> str:
    text = re.sub(r'```[\s\S]*?```', '', text)  # 代码块
    def _inline_code(m):
        c = m.group(1)
        if re.match(r'^[a-zA-Z0-9_.\-/~:#]+$', c) or re.search(r'[一-鿿]', c):
            return c
        return ''
    text = re.sub(r'`([^`]+)`', _inline_code, text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[A-Za-z]:\\[^\s,;)]+', '', text)
    text = re.sub(r'(?<![@\w])/[^\s,;)]{5,}', '', text)
    text = re.sub(r'\b[0-9a-f]{7,40}\b', '', text)
    text = re.sub(r'\[[\w]+:.*?\]', '', text)
    text = re.sub(r'\S+\.\w+:\d+(?::\d+)?', '', text)
    text = re.sub(r'^\s*[\$>]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[=*\-_]{3,}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = text.strip()
    if not text:
        text = re.sub(r'[\r\n]+', ' ', text)
        text = re.sub(r'[#*`>\[\]|\\{}()]', '', text).strip()
    return text


def speak_edge(text: str) -> bool:
    try:
        import edge_tts
        mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        mp3_path = mp3.name; mp3.close()
        _run_async(edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural").save(mp3_path))
        for player in ["ffplay", "ffplay.exe"]:
            try:
                subprocess.run([player, "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
                               capture_output=True, timeout=60)
                return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"(New-Object Media.SoundPlayer('{mp3_path}')).PlaySync()"],
                       capture_output=True, timeout=30)
        return True
    except BaseException:
        print(f"[speak] edge-tts 失败:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return False
    finally:
        try: os.unlink(mp3_path)
        except: pass


def speak_sapi5(text: str) -> bool:
    try:
        import win32com.client
        sp = win32com.client.Dispatch("SAPI.SpVoice")
        for i in range(sp.GetVoices().Count):
            d = sp.GetVoices().Item(i).GetDescription().lower()
            if "xiaoxiao" in d:
                sp.Voice = sp.GetVoices().Item(i)
                break
        sp.Speak(text, 1)
        while sp.Status.RunningState == 1:
            time.sleep(0.1)
        return True
    except BaseException:
        print(f"[speak] SAPI5 失败:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return False


def speak(text: str) -> bool:
    if not text.strip():
        return False
    text = filter_text(text)
    if not text:
        return False
    return speak_edge(text) or speak_sapi5(text) if TTS_MODE == "edge" else speak_sapi5(text) or speak_edge(text)


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    if text.strip():
        sys.exit(0 if speak(text) else 1)
