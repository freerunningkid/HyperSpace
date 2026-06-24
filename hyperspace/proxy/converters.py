"""Anthropic Messages API ↔ OpenAI Chat Completions API 格式转换.

核心逻辑：在代理层做双向格式翻译，让 Claude Code 能通过 OpenAI 兼容的厂商（如 SiliconFlow）
调用 Anthropic 格式不支持的模型。

转换覆盖：
  - 文本消息
  - System prompt
  - 工具定义 & 工具调用
  - 流式 SSE 事件
  - 非流式完整响应
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Optional

# ── 工具函数 ──

def _generate_id(prefix: str = "msg") -> str:
    """生成 Anthropic 风格的消息 ID."""
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _stop_reason_map(openai_finish: str | None) -> str | None:
    """OpenAI finish_reason → Anthropic stop_reason."""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }
    return mapping.get(openai_finish) if openai_finish else None


# ── 请求转换: Anthropic → OpenAI ──

def anthropic_to_openai_request(body: dict) -> dict:
    """将 Anthropic Messages API 请求体转为 OpenAI Chat Completions 格式.

    处理: system prompt, messages, tools, tool_choice, max_tokens,
    temperature, stream.
    """
    oai_messages: list[dict] = []

    # 1. System prompt → system message
    system = body.get("system", "")
    if isinstance(system, list):
        # Anthropic 允许 system 为 block 列表
        system = " ".join(
            b.get("text", "") for b in system if isinstance(b, dict)
        )
    if system:
        oai_messages.append({"role": "system", "content": system})

    # 2. Messages 转换
    for msg in body.get("messages", []):
        converted = _convert_anthropic_message(msg)
        # 合并连续的相同 role 的消息（OpenAI 不允许连续 assistant 或连续 tool）
        if oai_messages and oai_messages[-1]["role"] == converted["role"]:
            continue
        oai_messages.append(converted)

    # 3. Tools 转换
    tools = None
    raw_tools = body.get("tools")
    if raw_tools:
        tools = [_convert_anthropic_tool(t) for t in raw_tools]

    # 4. tool_choice
    tool_choice = None
    raw_choice = body.get("tool_choice")
    if raw_choice:
        if isinstance(raw_choice, dict):
            tc_type = raw_choice.get("type", "auto")
            if tc_type == "any":
                tool_choice = "required"
            elif tc_type == "tool":
                tool_choice = {"type": "function", "function": {"name": raw_choice.get("name", "")}}
            else:
                tool_choice = tc_type
        else:
            tool_choice = raw_choice

    # 5. 组装 OpenAI 请求
    oai_body = {
        "model": body.get("model", ""),
        "messages": oai_messages,
        "max_tokens": body.get("max_tokens", 4096),
        "stream": body.get("stream", False),
    }
    for key in ("temperature", "top_p", "stop", "presence_penalty", "frequency_penalty", "n"):
        if key in body:
            oai_body[key] = body[key]

    if tools:
        oai_body["tools"] = tools
    if tool_choice:
        oai_body["tool_choice"] = tool_choice

    return oai_body


def _convert_anthropic_message(msg: dict) -> dict:
    """单条 Anthropic 消息 → OpenAI 消息."""
    role = msg.get("role", "user")
    content = msg.get("content", "")

    # 文本消息
    if isinstance(content, str):
        if role == "assistant" and msg.get("stop_reason"):
            return {"role": "assistant", "content": content}
        return {"role": role, "content": content}

    # Content block 数组
    if isinstance(content, list):
        return _convert_anthropic_content_blocks(role, content)

    return {"role": role, "content": str(content)}


def _convert_anthropic_content_blocks(role: str, blocks: list) -> dict:
    """Anthropic content blocks → OpenAI 消息."""
    oai_content: list[dict] = []
    tool_calls: list[dict] = []

    for block in blocks:
        btype = block.get("type", "text")

        if btype == "text":
            oai_content.append({"type": "text", "text": block.get("text", "")})

        elif btype == "image":
            source = block.get("source", {})
            if source.get("type") == "base64":
                media_type = source.get("media_type", "image/jpeg")
                data = source.get("data", "")
                oai_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{data}"},
                })

        elif btype == "tool_use":
            tool_calls.append({
                "id": block.get("id", f"call_{uuid.uuid4().hex[:16]}"),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {})),
                },
            })

        elif btype == "tool_result":
            # tool_result → OpenAI tool role
            tool_use_id = block.get("tool_use_id", "")
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                texts = [b.get("text", "") for b in result_content if isinstance(b, dict) and b.get("type") == "text"]
                result_content = "\n".join(texts)
            return {
                "role": "tool",
                "tool_call_id": tool_use_id,
                "content": str(result_content),
            }

    # 构建消息
    if tool_calls:
        # 如果有工具调用, content 可以是文本或空
        text = ""
        for c in oai_content:
            if c.get("type") == "text":
                text = c["text"]
                break
        return {
            "role": "assistant",
            "content": text or None,
            "tool_calls": tool_calls,
        }

    # 纯文本
    texts = [c.get("text", "") for c in oai_content if c.get("type") == "text"]
    return {"role": role, "content": "\n".join(texts)}


def _convert_anthropic_tool(tool: dict) -> dict:
    """Anthropic tool 定义 → OpenAI function 定义."""
    return {
        "type": "function",
        "function": {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {}),
        },
    }


# ── 响应转换: OpenAI → Anthropic (非流式) ──

def openai_to_anthropic_response(openai_resp: dict, model: str) -> dict:
    """将 OpenAI Chat Completions 完整响应转为 Anthropic Messages 格式."""
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    usage = openai_resp.get("usage", {})

    # content blocks
    content: list[dict] = []

    # 文本
    text = message.get("content") or ""
    if text:
        content.append({"type": "text", "text": text})

    # 工具调用
    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        for tc in tool_calls:
            func = tc.get("function", {})
            try:
                arguments = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}
            content.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:16]}"),
                "name": func.get("name", ""),
                "input": arguments,
            })

    stop_reason = _stop_reason_map(choice.get("finish_reason"))

    return {
        "id": _generate_id("msg"),
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0) or 0,
            "output_tokens": usage.get("completion_tokens", 0) or 0,
        },
    }


# ── 流式转换: OpenAI SSE → Anthropic SSE ──

class OpenAIStreamConverter:
    """把 OpenAI 流式 chunk 逐个转成 Anthropic SSE 事件字符串.

    用法:
        converter = OpenAIStreamConverter(model="nex-agi/Nex-N2-Pro")
        async for chunk in openai_stream:
            for event_str in converter.feed(chunk):
                yield event_str
        for event_str in converter.flush():
            yield event_str
    """

    def __init__(self, model: str):
        self.model = model
        self._msg_id = _generate_id("msg")
        self._started = False
        self._text_buffer = ""
        self._finished = False
        self._input_tokens = 0
        self._output_tokens = 0

    def feed(self, chunk: dict) -> list[str]:
        """处理一个 OpenAI chunk, 返回 0-N 个 Anthropic SSE 事件字符串."""
        events: list[str] = []
        choices = chunk.get("choices", [])
        usage = chunk.get("usage", {})

        # 记录 token 用量（OpenAI 可能在最后一个 chunk 返回 usage）
        if usage:
            self._input_tokens = usage.get("prompt_tokens", 0) or self._input_tokens
            self._output_tokens = usage.get("completion_tokens", 0) or self._output_tokens

        if not choices:
            return events

        delta = choices[0].get("delta", {})
        finish = choices[0].get("finish_reason")

        # 1. 第一个 chunk: 发送 message_start + content_block_start
        if not self._started:
            self._started = True

            # message_start
            events.append(self._sse("message_start", {
                "type": "message_start",
                "message": {
                    "id": self._msg_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": self.model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": self._input_tokens or 1, "output_tokens": 0},
                },
            }))

            # content_block_start (文本)
            events.append(self._sse("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            }))

        # 2. 文本增量
        content_delta = delta.get("content", "")
        if content_delta:
            self._text_buffer += content_delta
            events.append(self._sse("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": content_delta},
            }))

        # 3. 工具调用增量 (简化处理: 非流式 tool_calls 在 final chunk 一次性给)
        tool_calls = delta.get("tool_calls")
        if tool_calls and not self._finished:
            for tc in tool_calls:
                func = tc.get("function", {})
                idx = tc.get("index", 0)
                # OpenAI 流式 tool_calls 可能跨多个 chunk
                # 这里简化处理：非流式才完整支持
                pass

        # 4. 结束
        if finish:
            self._finished = True

            # content_block_stop
            events.append(self._sse("content_block_stop", {
                "type": "content_block_stop",
                "index": 0,
            }))

            # message_delta
            stop_reason = _stop_reason_map(finish)
            events.append(self._sse("message_delta", {
                "type": "message_delta",
                "delta": {
                    "stop_reason": stop_reason,
                    "stop_sequence": None,
                },
                "usage": {
                    "output_tokens": self._output_tokens or max(1, len(self._text_buffer) // 4),
                },
            }))

            # message_stop
            events.append(self._sse("message_stop", {
                "type": "message_stop",
            }))

        return events

    def flush(self) -> list[str]:
        """流结束后调用, 发送未发送的结束事件."""
        if not self._finished and self._started:
            return self.feed({
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": len(self._text_buffer) // 4},
            })
        return []

    def get_text(self) -> str:
        """获取累积的文本."""
        return self._text_buffer

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        """构建 SSE 事件字符串."""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── 流式响应: 直接透传 (用于 Anthropic 兼容后端) ──

async def passthrough_stream( response: AsyncIterator[bytes]) -> AsyncIterator[str]:
    """将 Anthropic 兼容后端的 SSE 流直接透传给客户端.

    response: httpx 流式响应的 bytes 迭代器.
    返回: 格式正确的 SSE 字符串.
    """
    # 直接透传, 保留原始格式
    buffer = b""
    async for chunk in response:
        buffer += chunk
        # 按行切分, 可能会跨 chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            decoded = line.decode("utf-8", errors="replace")
            if decoded:
                yield decoded + "\n"
    # 剩余 buffer
    if buffer:
        yield buffer.decode("utf-8", errors="replace")
