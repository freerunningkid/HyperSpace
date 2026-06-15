"""在线图片识别工具（多引擎）

引擎:
  （无 --model，默认）— 竞速模式：gpt-4o + deepseek-ocr 并行，谁快用谁
  gpt-4o               — GPT-4o（GitHub Models，综合理解）
  qwen3-vl             — Qwen3-VL-Plus（阿里云百炼，5000万免费tokens）
  paddle               — PaddleOCR-VL-1.6（官网 v2 API，版面解析）
  deepseek-ocr         — DeepSeek-OCR（硅基流动，纯文字提取）
  agnes                — Agnes-2.0-Flash（免费云端，视觉+理解，全能型）
  ms-vl-235b           — Qwen3-VL-235B（ModelScope，高精度，每日2000次免费）
  ms-vl-30b            — Qwen3-VL-30B（ModelScope，快速版，每日2000次免费）

用法:
  python ocr.py <图片路径> [提示词]              # 竞速模式（推荐）
  python ocr.py <图片路径> [提示词] --model gpt-4o|qwen3-vl|paddle|deepseek-ocr|agnes|ms-vl-235b|ms-vl-30b
  python ocr.py <图片路径> --all                 # 所有模型并行分析
  python ocr.py <图片路径> --model ms-vl-30b --summary  # OCR + Qwen3.5-397B 免费分析

示例:
  python ocr.py D:/图片/screenshot.png                       # 竞速模式，2~11s
  python ocr.py D:/图片/screenshot.png "提取图中文字"
  python ocr.py D:/图片/photo.jpg --model qwen3-vl
  python ocr.py D:/图片/photo.jpg --model ms-vl-30b
  python ocr.py D:/图片/photo.jpg --model ms-vl-30b --summary
"""

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
import concurrent.futures
from datetime import datetime

# ── GitHub Models ──
GH_API_URL = "https://models.github.ai/inference/chat/completions"
GH_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github_token.json")

# ── 硅基流动 ──
SF_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
SF_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siliconflow_token.json")

def _load_token(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f).get("token", "")
    except Exception:
        return ""

SF_API_KEY = _load_token(SF_TOKEN_FILE)


SF_MODELS = {
    "deepseek-ocr": "deepseek-ai/DeepSeek-OCR",
}

# ── PaddleOCR 官网 API（v2 job-based，1.6 模型）──
PADDLE_JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
PADDLE_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paddle_token.json")
PADDLE_CUSTOM_TOKEN = _load_token(PADDLE_TOKEN_FILE)
PADDLE_MODEL = "PaddleOCR-VL-1.6"
PADDLE_OUTPUT_DIR = r"D:\Reasonix\screenshots-截图\paddle_output"

# ── 阿里云百炼（DashScope）─
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DASHSCOPE_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashscope_token.json")

# ── ModelScope（魔搭社区，每日 2000 次免费）─
MS_API_URL = "https://api-inference.modelscope.cn/v1/chat/completions"
MS_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelscope_token.json")

# ── Agnes AI（免费云端，支持视觉 + 图像生成）─
AGNES_API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
AGNES_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agnes_token.json")
AGNES_MODEL = "agnes-2.0-flash"  # 或 agnes-1.5-flash

def _get_agnes_token():
    if not os.path.exists(AGNES_TOKEN_FILE):
        return None
    with open(AGNES_TOKEN_FILE, "r") as f:
        data = json.load(f)
    return data.get("token", "").strip()


def _call_agnes(image_path, prompt, model=None, timeout=60):
    """调用 Agnes AI 视觉模型（免费，支持图像理解）"""
    api_key = _get_agnes_token()
    if not api_key:
        return "[跳过] Agnes token 未配置"
    if not os.path.exists(image_path):
        return f"[错误] 文件不存在: {image_path}"

    model = model or AGNES_MODEL
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    mime = _mime_type(image_path)
    data_url = f"data:{mime};base64,{img_b64}"

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        "max_tokens": 2048,
        "temperature": 0.5,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        AGNES_API_URL, data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        return "[错误] Agnes 返回空响应"
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:200]
        return f"[错误] Agnes HTTP {e.code}: {err}"
    except urllib.error.URLError as e:
        return f"[错误] Agnes 连接失败: {e.reason}"
    except Exception as e:
        return f"[错误] {e}"


DEFAULT_MODEL = None  # None = 竞速模式（gpt-4o + deepseek-ocr 并行）
MAX_IMG_SIZE_MB = 20


def _get_gh_token():
    if not os.path.exists(GH_TOKEN_FILE):
        return None
    with open(GH_TOKEN_FILE, "r") as f:
        data = json.load(f)
    return data.get("token", "").strip()


def _get_ms_token():
    if not os.path.exists(MS_TOKEN_FILE):
        return None
    with open(MS_TOKEN_FILE, "r") as f:
        data = json.load(f)
    return data.get("token", "").strip()


def _mime_type(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    }.get(ext, "image/png")


def _call_vision_api(image_path, prompt, model, api_url, api_key, extra_headers=None):
    """通用 OpenAI 兼容视觉 API 调用"""
    if not os.path.exists(image_path):
        return f"[错误] 文件不存在: {image_path}"

    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > MAX_IMG_SIZE_MB:
        print(f"[警告] 图片 {size_mb:.1f}MB，可能需要较长时间", flush=True)

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    mime = _mime_type(image_path)
    data_url = f"data:{mime};base64,{img_b64}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "auto"}}
                ]
            }
        ],
        "max_tokens": 4096
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(
        api_url,
        data=data,
        headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"].strip()
        else:
            return f"[错误] 返回格式异常: {json.dumps(result, ensure_ascii=False)[:500]}"

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        if e.code == 429:
            return "[错误] 请求过于频繁，请稍后再试"
        return f"[错误] HTTP {e.code}: {body[:500]}"
    except urllib.error.URLError as e:
        return f"[错误] 网络连接失败: {e.reason}"
    except Exception as e:
        return f"[错误] {e}"


def _call_github_models(image_path, prompt, model):
    token = _get_gh_token()
    if not token:
        return "[错误] 未找到 GitHub Token，请检查 github_token.json"
    return _call_vision_api(image_path, prompt, model, GH_API_URL, token,
                            extra_headers={
                                "Accept": "application/vnd.github+json",
                                "X-GitHub-Api-Version": "2022-11-28"
                            })


def _call_dashscope(image_path, prompt, model):
    token_file = DASHSCOPE_TOKEN_FILE
    if not os.path.exists(token_file):
        return "[错误] 未找到 DashScope Token，请检查 dashscope_token.json"
    with open(token_file, "r") as f:
        data = json.load(f)
    token = data.get("token", "").strip()
    if not token:
        return "[错误] DashScope Token 为空"
    return _call_vision_api(image_path, prompt, model, DASHSCOPE_API_URL, token)


def _call_modelscope(image_path, prompt, model):
    token_file = MS_TOKEN_FILE
    if not os.path.exists(token_file):
        return "[错误] 未找到 ModelScope Token，请检查 modelscope_token.json"
    with open(token_file, "r") as f:
        data = json.load(f)
    token = data.get("token", "").strip()
    if not token:
        return "[错误] ModelScope Token 为空"
    return _call_vision_api(image_path, prompt, model, MS_API_URL, token)


def _call_text_model(messages, model, api_url, api_key, max_tokens=1024):
    """通用 OpenAI 兼容文本模型调用（无图片）"""
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url, data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if "choices" in result and len(result["choices"]) > 0:
            msg = result["choices"][0].get("message", {}) or {}
            return msg.get("content", "").strip()
        return f"[错误] 返回格式异常: {json.dumps(result, ensure_ascii=False)[:500]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return f"[错误] HTTP {e.code}: {body[:500]}"
    except urllib.error.URLError as e:
        return f"[错误] 网络连接失败: {e.reason}"
    except Exception as e:
        return f"[错误] {e}"


def _call_siliconflow(image_path, prompt, model):
    return _call_vision_api(image_path, prompt, model, SF_API_URL, SF_API_KEY)


def _call_paddle_custom(image_path, prompt=None, save_images=False):
    """调用 PaddleOCR-VL-1.6 官网 v2 job API（异步提交+轮询+下载结果）

    使用 requests 库替代原始 urllib 手动拼接 multipart，支持 URL 模式。
    save_images=True 时下载版面图片到 PADDLE_OUTPUT_DIR。
    """
    try:
        import requests
    except ImportError:
        return "[错误] 缺少 requests 库，请运行: pip install requests"

    if not os.path.exists(image_path) and not image_path.startswith("http"):
        return f"[错误] 文件不存在: {image_path}"

    headers = {
        "Authorization": f"bearer {PADDLE_CUSTOM_TOKEN}",
    }

    optional_payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    }

    try:
        # Step 1: 提交 job
        if image_path.startswith("http"):
            # URL Mode
            headers["Content-Type"] = "application/json"
            payload = {
                "fileUrl": image_path,
                "model": PADDLE_MODEL,
                "optionalPayload": optional_payload
            }
            job_response = requests.post(PADDLE_JOB_URL, json=payload, headers=headers, timeout=60)
        else:
            # Local File Mode
            if not os.path.exists(image_path):
                return f"[错误] 文件不存在: {image_path}"

            data = {
                "model": PADDLE_MODEL,
                "optionalPayload": json.dumps(optional_payload, ensure_ascii=False)
            }

            with open(image_path, "rb") as f:
                files = {"file": f}
                job_response = requests.post(PADDLE_JOB_URL, headers=headers, data=data, files=files, timeout=120)

        if job_response.status_code != 200:
            return f"[错误] HTTP {job_response.status_code}: {job_response.text[:300]}"

        result = job_response.json()
        if result.get("code") != 0:
            return f"[错误] 提交失败: {result.get('msg', str(result)[:300])}"

        job_id = result["data"]["jobId"]

        # Step 2: 轮询等待完成（最多 120 秒）
        deadline = time.time() + 120
        jsonl_url = ""

        while time.time() < deadline:
            time.sleep(5)
            job_result_response = requests.get(f"{PADDLE_JOB_URL}/{job_id}", headers=headers, timeout=30)
            if job_result_response.status_code != 200:
                continue

            job = job_result_response.json()
            state = job["data"]["state"]

            if state == "pending":
                print("   ⏳ job pending...", flush=True)
            elif state == "running":
                try:
                    progress = job["data"]["extractProgress"]
                    total = progress["totalPages"]
                    extracted = progress["extractedPages"]
                    print(f"   📄 处理中: {extracted}/{total} 页", flush=True)
                except KeyError:
                    print("   ⏳ 处理中...", flush=True)
            elif state == "done":
                try:
                    progress = job["data"]["extractProgress"]
                    print(f"   ✅ 完成: 提取 {progress['extractedPages']} 页", flush=True)
                except KeyError:
                    print("   ✅ 完成", flush=True)
                jsonl_url = job["data"]["resultUrl"]["jsonUrl"]
                break
            elif state == "failed":
                error_msg = job["data"].get("errorMsg", "未知")
                return f"[错误] PaddleOCR job 失败: {error_msg}"

        if not jsonl_url:
            return "[错误] PaddleOCR job 超时（120s）"

        # Step 3: 下载并解析 JSONL 结果
        jsonl_response = requests.get(jsonl_url, timeout=30)
        jsonl_response.raise_for_status()
        lines = jsonl_response.text.strip().split("\n")

        output_dir = None
        if save_images:
            output_dir = PADDLE_OUTPUT_DIR
            os.makedirs(output_dir, exist_ok=True)

        texts = []
        page_num = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            for res in obj.get("result", {}).get("layoutParsingResults", []):
                texts.append(res["markdown"]["text"])

                if save_images and output_dir:
                    # 保存 Markdown 文件
                    md_filename = os.path.join(output_dir, f"doc_{page_num}.md")
                    with open(md_filename, "w", encoding="utf-8") as md_file:
                        md_file.write(res["markdown"]["text"])
                    print(f"   📝 Markdown 已保存: {md_filename}", flush=True)

                    # 下载 markdown 中嵌入的图片
                    for img_path, img_url in res["markdown"].get("images", {}).items():
                        full_img_path = os.path.join(output_dir, img_path)
                        os.makedirs(os.path.dirname(full_img_path), exist_ok=True)
                        try:
                            img_bytes = requests.get(img_url).content
                            with open(full_img_path, "wb") as img_file:
                                img_file.write(img_bytes)
                            print(f"   🖼️ 图片已保存: {full_img_path}", flush=True)
                        except Exception as e:
                            print(f"   ⚠️ 图片下载失败: {e}", flush=True)

                    # 下载 outputImages
                    for img_name, img_url in res.get("outputImages", {}).items():
                        try:
                            img_response = requests.get(img_url)
                            if img_response.status_code == 200:
                                filename = os.path.join(output_dir, f"{img_name}_{page_num}.jpg")
                                with open(filename, "wb") as f:
                                    f.write(img_response.content)
                                print(f"   🖼️ 输出图片已保存: {filename}", flush=True)
                        except Exception as e:
                            print(f"   ⚠️ 输出图片下载失败: {e}", flush=True)
                page_num += 1

        return "\n\n".join(texts) if texts else "[错误] 未解析到文字"

    except requests.exceptions.Timeout:
        return "[错误] PaddleOCR 请求超时"
    except requests.exceptions.ConnectionError:
        return "[错误] PaddleOCR 网络连接失败"
    except Exception as e:
        return f"[错误] {e}"


FAST_TIMEOUT = 3  # deepseek-ocr 超时秒数，超时则触发 gpt-4o 兜底


def _call_local_qwen(image_path, prompt, model="agnes-2.0-flash", timeout=60):
    """[已废弃] 原本地 Ollama。重定向到 Agnes AI 云端"""
    return _call_agnes(image_path, prompt, model=model, timeout=timeout)




def _looks_valid(text):
    """快速判断 OCR 结果是否像有效内容（非乱码）"""
    if len(text) < 10:
        return False
    clean = text.strip()
    total = max(len(clean), 1)
    # 中文字符 + ASCII 字母
    alpha = sum(1 for c in clean if '一' <= c <= '鿿' or 'a' <= c <= 'z' or 'A' <= c <= 'Z')
    # 特殊符号（乱码标志）
    junk = sum(1 for c in clean if c in '}]{[\\|/~^<>`')
    ratio = alpha / total
    junk_ratio = junk / total
    return ratio > 0.4 and junk_ratio < 0.15  # 有效字符 >40% 且乱码符号 <15%


def ocr_fastest(image_path, prompt=None):
    """级联竞速：先跑 deepseek-ocr（快），3s 超时/质量差则触发 gpt-4o 兜底"""
    p = prompt or "请识别这张图片：1）如果包含文字，完整提取所有文字内容；2）如果没有文字，详细描述图片中的场景、物体、人物等内容。"

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    ds_fut = pool.submit(_call_siliconflow, image_path, p, "deepseek-ai/DeepSeek-OCR")

    # 等 deepseek-ocr 最多 FAST_TIMEOUT 秒
    done, _ = concurrent.futures.wait([ds_fut], timeout=FAST_TIMEOUT)

    if done:
        result = ds_fut.result()
        if result and not result.startswith("[错误]") and not result.startswith("[跳过]") and _looks_valid(result):
            pool.shutdown(wait=False)
            return result

    # deepseek 超时/质量差 → 启动 gpt-4o 兜底
    gpt_fut = pool.submit(_call_github_models, image_path, p, "gpt-4o")

    done, pending = concurrent.futures.wait(
        [gpt_fut, ds_fut],
        return_when=concurrent.futures.FIRST_COMPLETED,
        timeout=120
    )

    for fut in done:
        try:
            result = fut.result(timeout=0)
            if result and not result.startswith("[错误]") and not result.startswith("[跳过]") and _looks_valid(result):
                pool.shutdown(wait=False)
                return result
        except Exception:
            continue

    # deepseek 烂结果但 gpt-4o 还没完——等它
    if gpt_fut in pending:
        done2, _ = concurrent.futures.wait([gpt_fut], timeout=120)
        for fut in done2:
            try:
                result = fut.result(timeout=0)
                if result and not result.startswith("[错误]") and not result.startswith("[跳过]") and _looks_valid(result):
                    pool.shutdown(wait=False)
                    return result
            except Exception:
                continue

    pool.shutdown(wait=False)
    return "[错误] 竞速模式：所有云端模型均失败"


def ocr(image_path, prompt=None, model=None):
    if model is None:
        return ocr_fastest(image_path, prompt)
    p = prompt or "请识别这张图片：1）如果包含文字，完整提取所有文字内容；2）如果没有文字，详细描述图片中的场景、物体、人物等内容。"
    if model == "paddle":
        return _call_paddle_custom(image_path, p, save_images=True)
    if model == "qwen3-vl":
        return _call_dashscope(image_path, p, "qwen3-vl-plus")
    if model in ("ms-vl-235b", "ms-vl-30b"):
        info = MODEL_REGISTRY[model]
        return _call_modelscope(image_path, p, info["id"])
    if model in SF_MODELS:
        return _call_siliconflow(image_path, p, SF_MODELS[model])
    return _call_github_models(image_path, p, model)


# ── 并行模型分析 ──

MODEL_REGISTRY = {
    "qwen3-vl":     {"provider": "dashscope",     "id": "qwen3-vl-plus"},
    "deepseek-ocr": {"provider": "siliconflow",   "id": "deepseek-ai/DeepSeek-OCR"},
    "paddle":       {"provider": "paddle-custom",   "id": "PaddleOCR-VL-1.6"},
    "gpt-4o":       {"provider": "github",         "id": "openai/gpt-4o"},
    "ms-vl-235b":   {"provider": "modelscope",     "id": "Qwen/Qwen3-VL-235B-A22B-Instruct"},
    "ms-vl-30b":    {"provider": "modelscope",     "id": "Qwen/Qwen3-VL-30B-A3B-Instruct"},
}


def _run_single_model(image_path, prompt, model_name):
    """执行单个模型分析（供线程池调用）"""
    info = MODEL_REGISTRY[model_name]
    try:
        if info["provider"] == "github":
            result = _call_github_models(image_path, prompt, info["id"])
        elif info["provider"] == "paddle-custom":
            result = _call_paddle_custom(image_path, prompt)
        elif info["provider"] == "dashscope":
            result = _call_dashscope(image_path, prompt, info["id"])

            result = _call_vision_api(image_path, prompt, info["id"], SF_API_URL, SF_API_KEY)
        return model_name, result
    except Exception as e:
        return model_name, f"[错误] {e}"


def ocr_all(image_path, prompt=None):
    """所有注册模型并行分析，返回 {model_name: result}"""
    p = prompt or "请识别这张图片：1）如果包含文字，完整提取所有文字内容；2）如果没有文字，详细描述图片中的场景、物体、人物等内容。"
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(MODEL_REGISTRY)) as pool:
        fut_map = {pool.submit(_run_single_model, image_path, p, name): name for name in MODEL_REGISTRY}
        for fut in concurrent.futures.as_completed(fut_map):
            name, text = fut.result()
            results[name] = text
    return results


# ── OCR 文本后处理（Qwen3.5-397B 免费总结 / 分析）─

SUMMARIZE_PROMPT = (
    "你是一个图片分析助手。下面是一张图片的OCR识别结果，请根据文字内容："
    "1）用一两句话总结图片的核心信息；"
    "2）判断图片类型（如：聊天截图、网页、文档、代码、表格、海报等）。"
)


def summarize_ocr(ocr_text, instruction=None):
    """对OCR识别结果进行文本后处理（总结/翻译/分析），使用 ModelScope Qwen3.5-397B 免费模型"""
    token = _get_ms_token()
    if not token:
        return "[错误] 未找到 ModelScope Token"
    messages = [
        {"role": "system", "content": instruction or SUMMARIZE_PROMPT},
        {"role": "user", "content": f"OCR识别结果：\n\n{ocr_text}"},
    ]
    return _call_text_model(messages, "Qwen/Qwen3.5-397B-A17B", MS_API_URL, token, max_tokens=512)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.upper() in ("GBK", "GB2312"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    prompt = None
    model = DEFAULT_MODEL
    run_all = False
    do_summary = False

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif args[i] == "--all":
            run_all = True
            i += 1
        elif args[i] == "--summary":
            do_summary = True
            i += 1
        else:
            prompt = args[i]
            i += 1

    if run_all:
        results = ocr_all(path, prompt)
        for name in ["gpt-4o", "qwen3-vl", "paddle", "deepseek-ocr", "ms-vl-235b", "ms-vl-30b"]:
            print(f"╔══ {name} ══╗")
            print(results.get(name, "[无结果]"))
            print()
    else:
        result = ocr(path, prompt, model)
        if result and not result.startswith("[错误]"):
            print(result, flush=True)
            if do_summary:
                print()
                print("── AI 分析 ──")
                analysis = summarize_ocr(result)
                print(analysis, flush=True)
        else:
            print(result, flush=True)
