#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agnes AI 全能推理脚本 — 聊天 / 视觉 / 图像生成 / 流式

Agnes AI (apihub.agnes-ai.com) 是免费的 AI API 网关，提供自研模型。
Key 从同目录 agnes_token.json 读取，不硬编码。

用法:
  python agnes_chat.py "你好"                              # 聊天（默认 agnes-2.0-flash）
  python agnes_chat.py "你好" --model agnes-1.5-flash      # 指定模型
  python agnes_chat.py "你好" --system "你是猫娘"           # 系统提示
  python agnes_chat.py "描述这张图" --image D:/图片/1.jpg   # 视觉识别
  python agnes_chat.py "你好" --stream                      # 流式输出
  python agnes_chat.py "一只猫" --gen-image                 # 生成图片
  python agnes_chat.py --check                              # 检查可用性
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

# ── Windows GBK 控制台兼容 ──
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agnes_token.json")
CHAT_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
IMAGE_URL = "https://apihub.agnes-ai.com/v1/images/generations"
DEFAULT_MODEL = "agnes-2.0-flash"  # 可选: agnes-1.5-flash
TIMEOUT = 60


def _load_key():
    try:
        with open(KEY_FILE, "r") as f:
            return json.load(f).get("token", "")
    except Exception:
        return ""


def _request(url, payload, timeout=TIMEOUT):
    """通用 HTTP POST 请求"""
    api_key = _load_key()
    if not api_key:
        return {"error": "Agnes token 未配置 — 检查 agnes_token.json"}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:500]
        return {"error": f"HTTP {e.code}: {err}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _encode_image(image_path):
    """读取图片文件并返回 base64 data URL"""
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        if ext in ("jpg", "jpeg"):
            mime = "image/jpeg"
        elif ext == "png":
            mime = "image/png"
        elif ext == "gif":
            mime = "image/gif"
        elif ext == "webp":
            mime = "image/webp"
        else:
            mime = "image/png"
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        return None


# ═══════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════

def check():
    """检查 Agnes API 可用性"""
    api_key = _load_key()
    if not api_key:
        return {"available": False, "error": "Token 未配置"}
    # 用简单请求验证
    result = _request(CHAT_URL, {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }, timeout=10)
    if "error" in result:
        return {"available": False, "error": result["error"]}
    return {
        "available": True,
        "error": None,
        "models": ["agnes-2.0-flash", "agnes-1.5-flash"],
        "image_models": ["agnes-image-2.1-flash", "agnes-image-2.0-flash"],
    }


def chat(prompt, system=None, model=None, stream=False, timeout=TIMEOUT):
    """纯文本聊天"""
    model = model or DEFAULT_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.7,
        "stream": stream,
    }

    if stream:
        return _chat_stream(payload, model, timeout)
    result = _request(CHAT_URL, payload, timeout=timeout)
    if "error" in result:
        return result
    if "choices" in result and result["choices"]:
        return {
            "text": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}),
            "done": True,
        }
    return {"error": "空响应"}


def _chat_stream(payload, model, timeout):
    """流式聊天"""
    api_key = _load_key()
    if not api_key:
        return {"error": "Token 未配置"}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CHAT_URL, data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            full_text = []
            for line in resp:
                line = line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            full_text.append(delta["content"])
                            print(delta["content"], end="", flush=True)
                    except json.JSONDecodeError:
                        pass
            print()
            return {"text": "".join(full_text), "done": True, "stream": True}
    except Exception as e:
        return {"error": f"流式请求失败: {e}"}


def vision(prompt, image_path, model=None, timeout=TIMEOUT):
    """视觉识别 — 传入图片文件路径"""
    model = model or DEFAULT_MODEL
    img_data = _encode_image(image_path)
    if img_data is None:
        return {"error": f"无法读取图片: {image_path}"}

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or "请描述这张图片"},
                {"type": "image_url", "image_url": {"url": img_data}},
            ],
        }],
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    result = _request(CHAT_URL, payload, timeout=timeout)
    if "error" in result:
        return result
    if "choices" in result and result["choices"]:
        return {
            "text": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}),
            "done": True,
        }
    return {"error": "空响应"}


def generate_image(prompt, model="agnes-image-2.1-flash", size="1024x1024",
                   n=1, output_dir=None, timeout=120):
    """生成图片并下载到本地"""
    payload = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
    }
    result = _request(IMAGE_URL, payload, timeout=timeout)
    if "error" in result:
        return result

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "generated")
    os.makedirs(output_dir, exist_ok=True)

    saved = []
    for i, item in enumerate(result.get("data", [])):
        url = item.get("url", "")
        if not url:
            continue
        name = f"agnes_{model.replace('/', '_')}_{i}.png"
        path = os.path.join(output_dir, name)
        try:
            urllib.request.urlretrieve(url, path)
            saved.append(path)
            print(f"[OK] 已保存: {path}")
        except Exception as e:
            print(f"[ERR] 下载失败: {e}")
    return saved or {"error": "无图片返回"}


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Agnes AI 全能推理")
    parser.add_argument("prompt", nargs="?", help="提示词")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL,
                        help=f"模型 (默认: {DEFAULT_MODEL})")
    parser.add_argument("--system", "-s", help="系统提示")
    parser.add_argument("--image", "-i", help="图片路径（视觉识别）")
    parser.add_argument("--gen-image", "-g", action="store_true",
                        help="生成图片（prompt 作为提示词）")
    parser.add_argument("--size", default="1024x1024",
                        help="图片尺寸 (默认: 1024x1024)")
    parser.add_argument("--stream", action="store_true", help="流式输出")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--check", action="store_true", help="检查可用性")
    parser.add_argument("--timeout", type=int, default=TIMEOUT,
                        help=f"超时秒数 (默认: {TIMEOUT})")
    args = parser.parse_args()

    if args.check:
        info = check()
        if info["available"]:
            print(f"[OK] Agnes AI 可用")
            print(f"     聊天: {', '.join(info['models'])}")
            print(f"     图片: {', '.join(info['image_models'])}")
        else:
            print(f"[ERR] Agnes AI 不可用: {info['error']}")
        return

    if not args.prompt:
        parser.print_help()
        return

    if args.gen_image:
        result = generate_image(args.prompt, model=args.model, size=args.size,
                                 timeout=args.timeout)
        if isinstance(result, dict) and "error" in result:
            print(f"\n[ERR] {result['error']}")
        return

    if args.image:
        result = vision(args.prompt, args.image, model=args.model,
                         timeout=args.timeout)
    else:
        result = chat(args.prompt, system=args.system, model=args.model,
                       stream=args.stream, timeout=args.timeout)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif "error" in result:
        print(f"\n[ERR] {result['error']}")
    elif not args.stream and not args.image:
        print(result.get("text", ""))


if __name__ == "__main__":
    main()
