#!/usr/bin/env python3
"""Voice MCP Server — speak + listen tools for Reasonix Code.

Tools:
  voice_speak(text: str)      — 文本转语音（edge-tts 晓晓 / SAPI5 降级）
  voice_listen(seconds: float) — 麦克风录音 → 硅基流动 SenseVoiceSmall 转写

Reads speak.py + asr.py from D:/AgentWork/scripts/ — no duplication.
"""

import json
import sys
import os
import tempfile
import time
import wave
import asyncio

# ── Path setup: find AgentWork scripts ──
AGENTWORK = r"D:\AgentWork\scripts"
sys.path.insert(0, os.path.join(AGENTWORK, "tools"))
sys.path.insert(0, os.path.join(AGENTWORK, "core"))

from speak import speak as _speak_tts  # D:\AgentWork\scripts\tools\speak.py
from asr import transcribe as _asr     # D:\AgentWork\scripts\core\asr.py

import sounddevice as sd
import numpy as np

# ── MCP imports ──
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("voice")


def _record_audio(duration: float, sample_rate: int = 16000) -> str:
    """Record from default microphone, return path to WAV file."""
    print(f"[voice] 录音 {duration}s @ {sample_rate}Hz ...", file=sys.stderr, flush=True)
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    sd.wait()

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav_path = tmp.name
    tmp.close()

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())

    print(f"[voice] 录音完成 → {wav_path}", file=sys.stderr, flush=True)
    return wav_path


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="voice_speak",
            description="将文本转换为语音朗读出来。使用 edge-tts 晓晓中文语音，自动过滤代码块和 URL。",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要朗读的文本内容",
                    },
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="voice_listen",
            description="通过麦克风录音并转写为文字。使用硅基流动 SenseVoiceSmall 模型。",
            inputSchema={
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "录音时长（秒），默认 5 秒，最大 60 秒",
                        "default": 5,
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "voice_speak":
        text = arguments.get("text", "")
        if not text.strip():
            return [types.TextContent(type="text", text="[voice] 没有可朗读的内容")]
        try:
            ok = _speak_tts(text)
            if ok:
                return [types.TextContent(type="text", text=f"[voice] ✓ 已朗读")]
            else:
                return [types.TextContent(type="text", text="[voice] ✗ TTS 失败，请检查音频设备")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[voice] ✗ 错误: {e}")]

    elif name == "voice_listen":
        seconds = min(max(float(arguments.get("seconds", 5)), 1), 60)
        try:
            wav_path = _record_audio(seconds)
            text = _asr(wav_path)
            try:
                os.unlink(wav_path)
            except Exception:
                pass
            if text.startswith("[错误]"):
                return [types.TextContent(type="text", text=text)]
            return [types.TextContent(type="text", text=f"[voice] 🎤 {text}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[voice] ✗ 录音失败: {e}")]

    else:
        return [types.TextContent(type="text", text=f"[voice] 未知工具: {name}")]


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
