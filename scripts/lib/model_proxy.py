#!/usr/bin/env python3
"""
Claude Code 模型翻译代理
将 Anthropic Messages API 格式 ↔ 各模型原生 API 格式

用法:
  python scripts/lib/model_proxy.py
  启动后在 127.0.0.1:8030 监听

Claude Code settings.json 中设置:
  ANTHROPIC_BASE_URL = http://127.0.0.1:8030
  ANTHROPIC_AUTH_TOKEN = proxy-key
  然后在 /model 命令中切换模型名即可

环境变量:
  DEEPSEEK_API_KEY     DeepSeek API Key
  AGNES_API_KEY        Agnes API Key
  ZHIPU_API_KEY        智谱AI (GLM) API Key
"""

import json
import http.server
import os
import requests
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("proxy")

HOST = "127.0.0.1"
PORT = 15721

# ======== 模型配置（API Key 从环境变量读取） ========
PROVIDERS = {
    "deepseek-v4-flash": {
        "name": "DeepSeek V4 Flash",
        "type": "anthropic",  # 原生支持 Anthropic Messages API
        "endpoint": "https://api.deepseek.com/anthropic/v1/messages",
        "api_key_env": "DEEPSEEK_API_KEY",
        "max_tokens": 8192,
    },
    "deepseek-v4-pro": {
        "name": "DeepSeek V4 Pro",
        "type": "anthropic",
        "endpoint": "https://api.deepseek.com/anthropic/v1/messages",
        "api_key_env": "DEEPSEEK_API_KEY",
        "max_tokens": 8192,
    },
    "agnes-2.0-flash": {
        "name": "Agnes 2.0 Flash",
        "type": "openai",
        "anthropic_direct": True,
        "endpoint": "https://apihub.agnes-ai.com/v1/messages",
        "api_key_env": "AGNES_API_KEY",
        "max_tokens": 8192,
        "context_window": 1048576,
    },
    "glm-4.7-flash": {
        "name": "GLM-4.7-Flash (智谱AI)",
        "type": "openai",  # 需要翻译为 OpenAI Chat 格式
        "anthropic_direct": False,
        "endpoint": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "ZHIPU_API_KEY",
        "max_tokens": 8192,
        "context_window": 131072,
    },
    "siliconflow-qwen-32b": {
        "name": "Qwen2.5-32B (硅基流动)",
        "type": "openai",
        "anthropic_direct": False,
        "endpoint": "https://api.siliconflow.cn/v1/chat/completions",
        "api_key_env": "SILICONFLOW_API_KEY",
        "max_tokens": 8192,
        "context_window": 65536,
    },
    "groq-llama-4-fast": {
        "name": "Llama 4 Fast (Groq)",
        "type": "openai",
        "anthropic_direct": False,
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY",
        "max_tokens": 8192,
        "context_window": 131072,
    },
    "dashscope-qwen-plus": {
        "name": "Qwen-Plus (DashScope)",
        "type": "openai",
        "anthropic_direct": False,
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "DASHSCOPE_API_KEY",
        "max_tokens": 8192,
        "context_window": 131072,
    },
}

# 模型名别名（处理 DeepSeek 的 [1M] 后缀、桌面版硬编码名等）
MODEL_ALIASES = {
    "deepseek-v4-flash[1M]": "deepseek-v4-flash",
    "deepseek-v4-pro[1M]": "deepseek-v4-pro",
    "deepseek-v4-flash[32k]": "deepseek-v4-flash",
    "deepseek-v4-pro[32k]": "deepseek-v4-pro",
    # Claude 桌面版（汉化）把 UI 模型名映射为官方名再发请求
    "claude-opus-4-8": "deepseek-v4-pro",
    "claude-opus-4-8[1m]": "deepseek-v4-pro",
    "claude-sonnet-4-5": "agnes-2.0-flash",
    "claude-sonnet-4-5[1m]": "agnes-2.0-flash",
    "claude-haiku-4-5": "deepseek-v4-flash",
    "claude-haiku-4-5[1m]": "deepseek-v4-flash",
}


def _get_api_key(config):
    """从环境变量获取 API Key，带友好报错"""
    env_var = config.get("api_key_env")
    if not env_var:
        return None, f"Model '{config['name']}' has no api_key_env configured"
    key = os.environ.get(env_var)
    if not key:
        return None, f"环境变量 {env_var} 未设置"
    return key, None


def resolve_model(model_name):
    """解析模型名（处理别名）"""
    if model_name in MODEL_ALIASES:
        resolved = MODEL_ALIASES[model_name]
        log.info(f"  [alias] {model_name} -> {resolved}")
        return resolved
    return model_name


# ======== 翻译函数 ========

def anthropic_to_openai_messages(anthropic_body):
    """将 Anthropic Messages 格式请求体转为 OpenAI Chat 格式"""
    system_prompt = anthropic_body.get("system", "")
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for msg in anthropic_body.get("messages", []):
        role = msg["role"]
        content = msg.get("content", "")

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block["text"])
            content = "\n".join(text_parts) if text_parts else " "

        messages.append({"role": role, "content": content})

    model = anthropic_body.get("model", "glm-4.7-flash")

    openai_body = {
        "model": model,
        "messages": messages,
        "max_tokens": anthropic_body.get("max_tokens", 4096),
        "temperature": anthropic_body.get("temperature", 0.7),
        "stream": False,
    }

    return openai_body


def openai_to_anthropic_response(openai_response, model):
    """将 OpenAI Chat 格式响应体转为 Anthropic Messages 格式"""
    choice = openai_response.get("choices", [{}])[0]
    msg = choice.get("message", {})

    content_blocks = []
    reasoning = msg.get("reasoning_content", "")
    if reasoning:
        content_blocks.append({
            "type": "thinking",
            "thinking": reasoning,
            "signature": f"proxy_{model}_{openai_response.get('id', 'unknown')}"
        })

    text = msg.get("content", "")
    if text:
        content_blocks.append({"type": "text", "text": text})

    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    usage = openai_response.get("usage", {})

    return {
        "id": openai_response.get("id", f"proxy_{model}"),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content_blocks,
        "stop_reason": choice.get("finish_reason", "end_turn"),
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
    }


def handle_anthropic(body, model):
    """处理 Anthropic Messages API 请求"""
    config = PROVIDERS.get(model)
    if not config:
        return None, f"Unknown model: {model}"

    api_key, err = _get_api_key(config)
    if err:
        return None, err

    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    if config["type"] == "anthropic":
        headers["x-api-key"] = api_key
        payload = body

    elif config.get("anthropic_direct"):
        headers["x-api-key"] = api_key
        payload = body

    else:
        headers["Authorization"] = f"Bearer {api_key}"
        payload = anthropic_to_openai_messages(body)
        log.info(f"  [translate] Anthropic -> OpenAI for {model}")

    try:
        resp = requests.post(
            config["endpoint"],
            headers=headers,
            json=payload,
            timeout=120,
        )

        if resp.status_code != 200:
            err = resp.text[:500]
            return None, f"API error ({resp.status_code}): {err}"

        data = resp.json()

        if config.get("type") == "anthropic" or config.get("anthropic_direct"):
            return data, None
        else:
            return openai_to_anthropic_response(data, model), None

    except requests.exceptions.Timeout:
        return None, f"Timeout connecting to {model}"
    except Exception as e:
        return None, f"Request failed: {str(e)}"


# ======== HTTP Server ========

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_len)
        body = raw.decode("utf-8", errors="replace")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return

        path = self.path
        model_raw = data.get("model", "unknown")
        model = resolve_model(model_raw)

        log.info(f"--> {model_raw if model_raw != model else model} {path}")

        # Strip /claude-desktop prefix (used by Chinese Desktop version)
        if path.startswith("/claude-desktop"):
            path = path[len("/claude-desktop"):] or "/"
            log.info(f"  [desktop] stripped prefix -> {path}")

        if path == "/v1/messages":
            result, error = handle_anthropic(data, model)
            if error:
                self._send_error(400, error)
                return
            self._send_json(result, 200)
            log.info(f"<-- {model} OK (tokens: {result.get('usage', {}).get('output_tokens', '?')})")

        elif path == "/health":
            self._send_json({"status": "ok", "models": list(PROVIDERS.keys())}, 200)

        elif path == "/v1/models":
            self._send_json({
                "models": [
                    {
                        "id": k,
                        "name": v["name"],
                        "context_window": v.get("context_window", 100000),
                        "type": v["type"],
                    }
                    for k, v in PROVIDERS.items()
                ]
            }, 200)

        else:
            self._send_error(404, f"Not found: {path}")

    def do_GET(self):
        path = self.path
        # Strip /claude-desktop prefix
        if path.startswith("/claude-desktop"):
            path = path[len("/claude-desktop"):] or "/"
        if path == "/health":
            self._send_json({"status": "ok", "models": list(PROVIDERS.keys())}, 200)
        elif path == "/v1/models":
            self._send_json({
                "models": [
                    {"id": k, "name": v["name"], "type": v["type"]}
                    for k, v in PROVIDERS.items()
                ]
            }, 200)
        else:
            self._send_error(404, f"Not found: {path}")

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_error(self, status, message):
        self._send_json({"error": {"type": str(status), "message": message}}, status)

    def log_message(self, format, *args):
        pass


def main():
    server = http.server.HTTPServer((HOST, PORT), ProxyHandler)

    print(f"=== Claude Code Model Proxy ===")
    print(f"Listening: http://{HOST}:{PORT}")
    print()
    print("Available models:")

    missing_env = []
    for k, v in PROVIDERS.items():
        tag = "direct" if v.get("type") == "anthropic" or v.get("anthropic_direct") else "translate"
        env_var = v.get("api_key_env", "")
        key = os.environ.get(env_var)
        status = "[OK]" if key else "[MISSING]"
        if not key:
            missing_env.append(env_var)
        print(f"  {k:24s} -> {v['name']:24s} [{tag}] {status}")

    if missing_env:
        print()
        print("! 以下环境变量未设置（模型不可用）：")
        for var in sorted(set(missing_env)):
            print(f"    {var}")

    print()
    print("Claude Code settings.json:")
    print("  ANTHROPIC_BASE_URL = http://127.0.0.1:8030")
    print("  ANTHROPIC_AUTH_TOKEN = proxy-key")
    print("  Then use /model <model_name> to switch")
    print()
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
