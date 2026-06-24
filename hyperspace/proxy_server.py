#!/usr/bin/env python3
"""HyperSpace 代理模式 —— 多模型 API 网关.

在本地启动一个 HTTP 服务, 接收 Anthropic Messages API 格式的请求,
根据模型名称自动路由到不同厂商。

启动:
    python -m hyperspace.proxy_server [--port 9090] [--host 127.0.0.1]

然后在 Claude Code 设置:
    ANTHROPIC_BASE_URL=http://localhost:9090

之后 /model 里就能看到所有配置的模型, 随意切换。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import aiohttp.web
import httpx
import yaml
from dotenv import load_dotenv

from hyperspace.proxy.converters import (
    anthropic_to_openai_request,
    openai_to_anthropic_response,
    OpenAIStreamConverter,
    passthrough_stream,
)

logger = logging.getLogger("hyperspace.proxy")

# ── 路径 ──
HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "proxy_config.yaml"

# ── 配置加载 ──

def load_proxy_config(path: str | Path = CONFIG_PATH) -> dict:
    """加载代理配置."""
    path = Path(path)
    if not path.exists():
        logger.error("配置文件不存在: %s", path)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg:
        logger.error("配置文件为空: %s", path)
        sys.exit(1)
    return cfg


# ── 模型路由 ──

class ModelRouter:
    """根据模型名查找路由目标."""

    def __init__(self, config: dict):
        self.models = config.get("models", {})
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 9090)

    def list_models(self) -> list[dict]:
        """返回 Claude Code 可识别的模型列表."""
        result = []
        for name, info in self.models.items():
            entry = {
                "type": "model",
                "id": name,
                "display_name": name,
            }
            # 加上最大 token 信息
            if "max_tokens" in info:
                entry["max_tokens"] = info["max_tokens"]
            result.append(entry)
        return result

    def get_route(self, model_name: str) -> dict | None:
        """获取模型的路由信息. 不存在则返回 None.
        
        自动剥离 [N] / [N context] 后缀以匹配配置中的基础模型名."""
        # 剥离 [xxx] 后缀 (如 "deepseek-v4-flash[1M]" → "deepseek-v4-flash")
        import re
        base_name = re.sub(r'\[.*?\]', '', model_name).strip()
        info = self.models.get(model_name)
        if not info and base_name != model_name:
            info = self.models.get(base_name)
        if not info:
            return None
        return info

    def resolve_api_key(self, info: dict) -> str | None:
        """从 env 或配置中解析 API Key."""
        env_key = info.get("api_key_env")
        if env_key:
            return os.environ.get(env_key) or os.environ.get(env_key)
        static_key = info.get("api_key")
        if static_key:
            return static_key
        return None


# ── 后端转发 ──

async def forward_to_anthropic_compat(
    body: dict,
    info: dict,
    api_key: str,
) -> dict | tuple[dict, str]:
    """转发到 Anthropic 兼容后端 (如 DeepSeek).

    返回值:
      非流式: dict (Anthropic 格式响应)
      流式:   (dict, "stream") → 首次 message_start 事件 + 后续由调用方处理
    """
    base_url = info["base_url"].rstrip("/")
    target_url = f"{base_url}/v1/messages"
    is_stream = body.get("stream", False)

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        if is_stream:
            # 流式: 直接透传 SSE
            req = client.build_request("POST", target_url, json=body, headers=headers)
            resp = await client.send(req, stream=True)
            resp.raise_for_status()
            return (resp, "stream")
        else:
            # 非流式
            resp = await client.post(target_url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()


async def forward_to_openai_compat(
    body: dict,
    info: dict,
    api_key: str,
) -> dict | tuple:
    """转发到 OpenAI 兼容后端 (如 SiliconFlow).

    先把 Anthropic 请求转成 OpenAI 格式, 转发后把结果转回 Anthropic 格式.

    返回值:
      非流式: dict (Anthropic 格式响应)
      流式:   (异步生成器) → 逐个产生 Anthropic SSE 事件字符串
    """
    base_url = info["base_url"].rstrip("/")
    target_url = f"{base_url}/chat/completions"
    is_stream = body.get("stream", False)
    model = info.get("model") or body.get("model", "")

    # 1. 转换请求
    oai_body = anthropic_to_openai_request(body)
    # 覆盖模型名：用路由配置中的 model 字段（如别名 → 真实上游名称）
    oai_body["model"] = model

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        if is_stream:
            oai_body["stream"] = True
            oai_body["stream_options"] = {"include_usage": True}
            req = client.build_request("POST", target_url, json=oai_body, headers=headers)
            resp = await client.send(req, stream=True)
            resp.raise_for_status()

            converter = OpenAIStreamConverter(model)
            return _openai_stream_to_anthropic(resp, converter)
        else:
            resp = await client.post(target_url, json=oai_body, headers=headers)
            resp.raise_for_status()
            oai_result = resp.json()
            return openai_to_anthropic_response(oai_result, model)


async def _openai_stream_to_anthropic(
    resp: httpx.Response,
    converter: OpenAIStreamConverter,
):
    """将 OpenAI 流式响应转成 Anthropic SSE 事件, 逐个 yield."""
    buffer = ""
    async for chunk in resp.aiter_bytes():
        buffer += chunk.decode("utf-8", errors="replace")
        # 解析 SSE lines
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue
                try:
                    oai_chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                for event_str in converter.feed(oai_chunk):
                    yield event_str
    # 结束
    for event_str in converter.flush():
        yield event_str


# ── HTTP 处理器 ──

class ProxyApp:
    """aiohttp web 应用."""

    def __init__(self, config: dict):
        self.router = ModelRouter(config)
        self._app = aiohttp.web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self._app.router.add_get("/v1/models", self.handle_list_models)
        self._app.router.add_post("/v1/messages", self.handle_messages)
        # 健康检查
        self._app.router.add_get("/health", self.handle_health)

    @property
    def app(self):
        return self._app

    async def handle_health(self, request):
        return aiohttp.web.json_response({"status": "ok"})

    async def handle_list_models(self, request):
        """GET /v1/models — 返回可用模型列表 (Anthropic 格式)."""
        models = self.router.list_models()
        return aiohttp.web.json_response({"data": models})

    async def handle_messages(self, request):
        """POST /v1/messages — 代理消息到对应后端."""
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            return aiohttp.web.json_response(
                {"error": {"type": "invalid_request_error", "message": str(e)}},
                status=400,
            )

        model_name = body.get("model", "")
        if not model_name:
            return aiohttp.web.json_response(
                {"error": {"type": "invalid_request_error", "message": "model 字段必填"}},
                status=400,
            )

        # 查找路由
        route_info = self.router.get_route(model_name)
        if not route_info:
            return aiohttp.web.json_response(
                {
                    "error": {
                        "type": "not_found_error",
                        "message": f"未知模型 '{model_name}', 可用模型: {[m['id'] for m in self.router.list_models()]}",
                    }
                },
                status=404,
            )

        # 解析 API Key
        api_key = self.router.resolve_api_key(route_info)
        if not api_key:
            return aiohttp.web.json_response(
                {
                    "error": {
                        "type": "authentication_error",
                        "message": f"模型 '{model_name}' 的 API Key 未配置 (env: {route_info.get('api_key_env', 'N/A')})",
                    }
                },
                status=401,
            )

        # 转发
        backend_type = route_info.get("type", "anthropic_compat")
        try:
            if backend_type == "anthropic_compat":
                result = await forward_to_anthropic_compat(body, route_info, api_key)
            elif backend_type == "openai_compat":
                result = await forward_to_openai_compat(body, route_info, api_key)
            else:
                return aiohttp.web.json_response(
                    {"error": {"type": "invalid_request_error", "message": f"未知后端类型: {backend_type}"}},
                    status=500,
                )
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            detail = ""
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:200]
            logger.error("后端错误 [%s]: %s %s", model_name, status, detail)
            return aiohttp.web.json_response(
                {
                    "error": {
                        "type": "upstream_error",
                        "message": f"后端服务错误 ({status})",
                        "upstream_status": status,
                    }
                },
                status=502,
            )
        except httpx.TimeoutException as e:
            logger.error("后端超时 [%s]: %s", model_name, e)
            return aiohttp.web.json_response(
                {"error": {"type": "timeout_error", "message": "后端请求超时"}},
                status=504,
            )
        except Exception as e:
            logger.error("代理错误 [%s]: %s", model_name, e, exc_info=True)
            return aiohttp.web.json_response(
                {"error": {"type": "proxy_error", "message": str(e)}},
                status=500,
            )

        # 返回结果
        if isinstance(result, tuple) and len(result) == 2 and result[1] == "stream":
            # 流式: 透传 Anthropic 兼容后端的 SSE
            resp = result[0]  # httpx.Response
            return await self._send_streaming_anthropic(request, resp)
        elif hasattr(result, "__aiter__"):
            # 流式: OpenAI 转换后的 SSE
            return await self._send_streaming_converted(request, result)
        else:
            # 非流式
            return aiohttp.web.json_response(result)

    async def _send_streaming_anthropic(self, request, upstream_resp):
        """透传 Anthropic 兼容后端的 SSE 流."""
        response = aiohttp.web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        try:
            async for event_str in passthrough_stream(upstream_resp.aiter_bytes()):
                await response.write(event_str.encode("utf-8"))
                await response.drain()
        except Exception as e:
            logger.error("流式透传错误: %s", e)
        finally:
            await upstream_resp.aclose()
            await response.write_eof()
        return response

    async def _send_streaming_converted(self, request, event_gen):
        """发送转换后的 SSE 流."""
        response = aiohttp.web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        try:
            async for event_str in event_gen:
                await response.write(event_str.encode("utf-8"))
                await response.drain()
        except Exception as e:
            logger.error("流式转换错误: %s", e)
        finally:
            await response.write_eof()
        return response


# ── 入口 ──

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HyperSpace 代理模式 —— 多模型 API 网关",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python -m hyperspace.proxy_server\n"
            "  python -m hyperspace.proxy_server --port 9090\n"
            "  python -m hyperspace.proxy_server --config path/to/proxy_config.yaml\n"
            "\n"
            "然后在 Claude Code 设置:\n"
            "  ANTHROPIC_BASE_URL=http://localhost:9090\n"
        ),
    )
    parser.add_argument("--host", default=None, help="监听地址 (默认: 配置中的 host)")
    parser.add_argument("--port", type=int, default=None, help="监听端口 (默认: 配置中的 port)")
    parser.add_argument("--config", default=str(CONFIG_PATH), help=f"配置文件路径 (默认: {CONFIG_PATH})")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    parser.add_argument("--log-file", help="日志文件路径 (默认: stderr)")
    return parser.parse_args(argv)


def setup_logging(verbose: bool = False, log_file: str | None = None):
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


async def main_async(args: argparse.Namespace | None = None):
    if args is None:
        args = parse_args()

    setup_logging(verbose=args.verbose, log_file=args.log_file)

    # 加载 .env
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("已加载 .env: %s", env_path)

    # 加载配置
    config = load_proxy_config(args.config)
    logger.info("已加载配置: %s", args.config)

    # 覆盖 host/port
    if args.host:
        config["host"] = args.host
    if args.port:
        config["port"] = args.port

    host = config.get("host", "127.0.0.1")
    port = config.get("port", 9090)

    # 打印可用模型
    router = ModelRouter(config)
    model_list = router.list_models()
    logger.info("可用模型 (%d 个):", len(model_list))
    for m in model_list:
        info = router.get_route(m["id"])
        provider = info.get("provider", "?") if info else "?"
        btype = info.get("type", "?") if info else "?"
        notes = info.get("notes", "") if info else ""
        logger.info("  - %-30s [%s/%s] %s", m["id"], provider, btype, notes)

    # 启动服务
    app = ProxyApp(config)
    logger.info("HyperSpace 代理启动 → http://%s:%d", host, port)
    logger.info("Claude Code 设置 ANTHROPIC_BASE_URL=http://%s:%d", host, port)

    runner = aiohttp.web.AppRunner(app.app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host, port)
    await site.start()

    # 保持运行
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


def main():
    """CLI 入口."""
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("代理已停止")


if __name__ == "__main__":
    main()
