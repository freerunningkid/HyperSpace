#!/usr/bin/env python3
import ctypes
_ESC_KEY = 0x1B

def _is_esc():
    try:
        return ctypes.windll.user32.GetAsyncKeyState(_ESC_KEY) & 0x8000 != 0
    except Exception:
        return False

"""TTS 引擎 — Edge TTS streaming 优先，SAPI5 本地兜底。

降级链: Edge streaming (ffplay 管道) → Edge save (powershell/ffplay) → SAPI5 Xiaoxiao → SAPI5 default

社区金标准方案 (edge-tts 11.2k stars):
  stream_sync() 逐块获取 → ffplay stdin 管道边下边播，首音延迟 < 500ms
  无 ffplay 时自动降级为 save 模式（完整下载后播放）
"""
import re, sys, os, subprocess, tempfile, time, asyncio, traceback, shutil

VOICE = "zh-CN-XiaoxiaoNeural"


def _has_ffplay() -> bool:
    """检测 ffplay 是否在 PATH 中可用。"""
    return shutil.which("ffplay") is not None or shutil.which("ffplay.exe") is not None


def _run_async(coro):
    """安全执行协程 — 处理已存在 event loop 的边缘情况 (MCP server)。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def filter_text(text: str) -> str:
    """过滤掉代码块、URL、路径等技术噪声，保留人声朗读内容。"""
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


def speak_edge_streaming(text: str) -> bool:
    """🥇 Edge TTS 流式 — ffplay 管道边下边播，首音延迟 < 500ms。
    无 ffplay 或 stream_sync 失败时返回 False，调用方自动降级。
    """
    if not _has_ffplay():
        return False
    proc = None
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, VOICE)

        proc = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            for chunk in communicate.stream_sync():
                if chunk["type"] == "audio":
                    proc.stdin.write(chunk["data"])
        except BrokenPipeError:
            pass
        except RuntimeError:
            # stream_sync 在现有 event loop 下可能失败 → 降级到 save 模式
            proc.stdin.close()
            proc.wait(timeout=3)
            return False

        proc.stdin.close()
        # 等待播放完成，但可 ESC 中断
        deadline = time.time() + 15
        while proc.poll() is None and time.time() < deadline:
            if _is_esc():
                proc.kill()
                break
            time.sleep(0.1)
        return True
    except BaseException:
        print(f"[speak] edge-tts streaming 失败:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        if proc is not None:
            try:
                proc.stdin.close()
                proc.wait(timeout=3)
            except Exception:
                pass
        return False


def speak_edge(text: str) -> bool:
    """🥈 Edge TTS save 模式 — 先下载完整 mp3 → ffplay 或 powershell 播放。
    通常作为 streaming 的降级路径，也可独立调用。
    """
    mp3_path = None
    try:
        import edge_tts
        mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        mp3_path = mp3.name
        mp3.close()

        _run_async(edge_tts.Communicate(text, VOICE).save(mp3_path))

        # ffplay 优先（可能检测漏了）
        for player in ["ffplay", "ffplay.exe"]:
            try:
                proc = subprocess.Popen(
                    [player, "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                deadline = time.time() + 15
                while proc.poll() is None and time.time() < deadline:
                    if _is_esc():
                        proc.kill()
                        break
                    time.sleep(0.1)
                return True
            except FileNotFoundError:
                continue

        # Windows — 尝试用 Windows Media Player 播放 mp3
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command",
             f"$wm = New-Object -ComObject 'WMPlayer.OCX'; $wm.URL = '{mp3_path}'; $wm.controls.play(); Start-Sleep -Seconds 10; [Runtime.InteropServices.Marshal]::ReleaseComObject($wm) | Out-Null"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000)
        deadline = time.time() + 15
        while proc.poll() is None and time.time() < deadline:
            if _is_esc():
                proc.kill()
                break
            time.sleep(0.1)
        return True
    except BaseException:
        print(f"[speak] edge-tts 失败:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return False
    finally:
        if mp3_path:
            try:
                os.unlink(mp3_path)
            except Exception:
                pass


def speak_sapi5(text: str) -> bool:
    """🥉 SAPI5 本地 TTS — Xiaoxiao Natural 优先，Huihui Desktop 兜底。
    零网络依赖，纯本地合成。同步模式，不走 async/RunningState 轮询。
    """
    try:
        import win32com.client
        sp = win32com.client.Dispatch("SAPI.SpVoice")
        for i in range(sp.GetVoices().Count):
            d = sp.GetVoices().Item(i).GetDescription().lower()
            if "xiaoxiao" in d and "natural" in d and "online" not in d:
                sp.Voice = sp.GetVoices().Item(i)
                break
        else:
            for i in range(sp.GetVoices().Count):
                d = sp.GetVoices().Item(i).GetDescription().lower()
                if "huihui" in d and "desktop" in d:
                    sp.Voice = sp.GetVoices().Item(i)
                    break
        sp.Speak(text, 0)
        return True
    except BaseException:
        print(f"[speak] SAPI5 失败:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return False


def speak(text: str) -> bool:
    """主入口 — Edge streaming → Edge save → SAPI5 自动降级链。

    Returns True if any engine succeeded, False if all failed.
    """
    if not text or not text.strip():
        return False
    text = filter_text(text)
    if not text:
        return False

    if os.name == "nt":
        return speak_sapi5(text) or speak_edge_streaming(text) or speak_edge(text)
    return speak_edge_streaming(text) or speak_edge(text) or speak_sapi5(text)


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    if text.strip():
        sys.exit(0 if speak(text) else 1)
