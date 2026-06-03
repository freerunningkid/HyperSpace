"""
语音转文字（ASR）— 硅基流动 SenseVoiceSmall

用法:
  python asr.py <音频文件路径>

示例:
  python asr.py D:/录音/meeting.wav
  python asr.py D:/语音/note.m4a
"""

import json
import os
import sys
import urllib.request

API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siliconflow_token.json")

def _load_token():
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("token", "")
    except Exception:
        return ""

API_KEY = _load_token()
MODEL = "FunAudioLLM/SenseVoiceSmall"
MAX_FILE_SIZE_MB = 50


def transcribe(audio_path: str) -> str:
    if not os.path.exists(audio_path):
        return f"[错误] 文件不存在: {audio_path}"

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return f"[错误] 文件 {size_mb:.1f}MB 超过 50MB 限制"

    print(f"[asr] 音频 {size_mb:.1f}MB，转写中...", flush=True)

    # multipart/form-data
    boundary = os.urandom(16).hex()
    filename = os.path.basename(audio_path)

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    parts = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'
    ).encode() + audio_data + (
        f'\r\n--{boundary}\r\n'
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f'{MODEL}\r\n'
        f'--{boundary}--\r\n'
    ).encode()

    req = urllib.request.Request(
        API_URL,
        data=parts,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return f"[错误] HTTP {e.code}: {body[:500]}"
    except urllib.error.URLError as e:
        return f"[错误] 网络连接失败: {e.reason}"
    except Exception as e:
        return f"[错误] {e}"

    text = result.get("text", "")
    if text:
        print(f"[asr] 完成（{len(text)} 字）", flush=True)
        return text.strip()
    return f"[错误] 返回格式异常: {json.dumps(result, ensure_ascii=False)[:500]}"


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.upper() in ("GBK", "GB2312"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    result = transcribe(sys.argv[1])
    print(result, flush=True)
