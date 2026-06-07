#!/usr/bin/env python3
"""Voice Bridge MCP — runs in WSL, calls Windows speak.py via PowerShell.

Tools:
  voice_speak(text) — 朗读中文文本（Windows SAPI5 晓晓）
"""
import sys, os, subprocess, json, asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("voice-bridge")
SPEAK_SCRIPT = r"D:\Reasonix\scripts\lib\speak.py"

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="voice_speak",
            description="将中文文本转为语音朗读出来。使用 Windows SAPI5 晓晓自然语音。",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要朗读的文本",
                    },
                },
                "required": ["text"],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "voice_speak":
        text = arguments.get("text", "").strip()
        if not text:
            return [types.TextContent(type="text", text="[voice] 没有内容")]
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 f"python '{SPEAK_SCRIPT}' \"{text}\""],
                capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return [types.TextContent(type="text", text="[voice] ✓ 已朗读")]
            else:
                return [types.TextContent(type="text", text=f"[voice] ✗ 失败({r.returncode}): {r.stderr[:200]}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"[voice] ✗ 异常: {e}")]
    return [types.TextContent(type="text", text=f"[voice] 未知工具: {name}")]

async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
