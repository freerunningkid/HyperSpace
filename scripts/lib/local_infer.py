#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地 Ollama 模型推理封装（供 Reasonix Skill 调用）

用法:
  python local_infer.py "提示词"                         # 默认 qwen3.5:4b
  python local_infer.py "提示词" --model qwen3.5:4b      # 指定模型
  python local_infer.py "提示词" --json                  # JSON 输出
  python local_infer.py "提示词" --stream                # 流式输出
  python local_infer.py "提示词" --system "系统指令"      # 系统提示
  python local_infer.py --check                          # 检查模型可用性
  python local_infer.py --list                           # 列出可用模型

依赖: 需要 Ollama 运行中 (ollama serve)
"""
import argparse
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

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen3.5:4b"
TIMEOUT = 30  # 单次推理超时（秒）


def _ollama_request(method, path, data=None, timeout=TIMEOUT):
    """调用 Ollama REST API"""
    url = f"{OLLAMA_HOST}/api/{path.lstrip('/')}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"}
    except urllib.error.URLError as e:
        return {"error": f"无法连接到 Ollama ({url}): {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def check():
    """检查 Ollama 服务和模型可用性"""
    result = _ollama_request("GET", "tags", timeout=5)
    if "error" in result:
        return {"available": False, "error": result["error"], "models": []}
    models = [m["name"] for m in result.get("models", [])]
    return {
        "available": len(models) > 0,
        "error": None,
        "models": models,
        "has_qwen35": any("qwen3.5" in m for m in models),
    }


def generate(prompt, model=None, system=None, stream=False, timeout=TIMEOUT):
    """生成回复"""
    model = model or DEFAULT_MODEL
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "options": {
            "temperature": 0.7,
            "num_predict": 2048,
        }
    }
    if system:
        payload["system"] = system

    if stream:
        # 流式：逐块读取
        url = f"{OLLAMA_HOST}/api/generate"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                full_text = []
                for line in resp:
                    chunk = json.loads(line.decode("utf-8"))
                    if "response" in chunk:
                        full_text.append(chunk["response"])
                        print(chunk["response"], end="", flush=True)
                    if chunk.get("done"):
                        print()
                        return {"text": "".join(full_text), "done": True}
                return {"text": "".join(full_text), "done": True}
        except Exception as e:
            return {"error": str(e)}
    else:
        result = _ollama_request("POST", "generate", payload, timeout=timeout)
        if "error" in result:
            return result
        text = result.get("response", "") or result.get("thinking", "")
        return {"text": text, "done": result.get("done", False)}


def list_models():
    """列出可用模型"""
    result = _ollama_request("GET", "tags", timeout=5)
    if "error" in result:
        return ["[ERR] 无法连接: " + result["error"]]
    models = result.get("models", [])
    if not models:
        return ["(无模型 — 先运行 ollama pull <模型名>)"]
    lines = []
    for m in models:
        size = m.get("size", 0)
        size_str = f"{size/1e9:.1f}GB" if size > 1e9 else f"{size/1e6:.0f}MB"
        modified = m.get("modified_at", "")[:19].replace("T", " ")
        lines.append(f"  {m['name']:30s} {size_str:>8s}  {modified}")
    return lines


def classify(text, categories, model=None):
    """快速分类：判断文本属于哪个类别"""
    prompt = f"""对以下文本进行分类，只返回类别名称，不要解释。

类别: {', '.join(categories)}

文本: {text}

分类结果:"""
    result = generate(prompt, model=model, system="你是一个精准的分类器，只输类别名称。")
    return result.get("text", "").strip()


# ── CLI ──
def main():
    parser = argparse.ArgumentParser(description="本地 Ollama 推理")
    parser.add_argument("prompt", nargs="?", help="推理提示词")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"模型名 (默认: {DEFAULT_MODEL})")
    parser.add_argument("--system", "-s", help="系统提示")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--stream", action="store_true", help="流式输出")
    parser.add_argument("--check", action="store_true", help="检查服务可用性")
    parser.add_argument("--list", action="store_true", help="列出可用模型")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help=f"超时秒数 (默认: {TIMEOUT})")
    args = parser.parse_args()

    if args.check:
        info = check()
        if info["available"]:
            print(f"[OK] Ollama 可用 | 模型: {', '.join(info['models']) or '(无)'}")
        else:
            print(f"[ERR] {info['error']}")
        return

    if args.list:
        lines = list_models()
        for line in lines:
            print(line)
        return

    if not args.prompt:
        parser.print_help()
        return

    if args.json:
        result = generate(args.prompt, args.model, args.system, stream=False, timeout=args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = generate(args.prompt, args.model, args.system, stream=args.stream, timeout=args.timeout)
        if "error" in result:
            print(f"\n[ERR] {result['error']}")
        elif not args.stream:
            print(result.get("text", ""))


if __name__ == "__main__":
    main()
