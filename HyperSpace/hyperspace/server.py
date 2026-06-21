"""HyperSpace MCP 服务端 —— 合法的云端大模型路由器.

向本地 Agent (Reasonix / ClaudeCode / Copilot) 暴露单一工具:
  hyperspace_query(prompt, images?, context?, mode?)
内部按图片/复杂度自动路由到免费档(智谱 GLM-4.7-Flash / GLM-4.6V-Flash)或廉价档
(DeepSeek / Kimi), 仅极少数高精度需求走 premium. 全部调用厂商官方 OpenAI 兼容 API,
合法、可开源.

接入 (.mcp.json, Cline 格式, 与 os-safe 等并列):
  "hyperspace": {
    "command": "python",
    "args": ["D:\\\\Reasonix\\\\HyperSpace\\\\hyperspace\\\\server.py"],
    "env": {"PYTHONIOENCODING": "utf-8"},
    "autoApprove": ["*"]
  }

约定: 低级 mcp SDK (非 FastMCP), 中文返回 + emoji 状态, stderr 标启动
(对齐 scripts/mcp/os_safe_server.py).
"""

from __future__ import annotations

import asyncio
import os
import sys

# MCP 以脚本路径直接启动 (python .../server.py), 此时 __package__ 为空,
# 相对导入会失败. 把项目根加入 sys.path 并改用绝对包导入, 兼容两种启动方式.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from hyperspace.config import COST_LOG, Config, load_config
from hyperspace.cost import record as record_cost
from hyperspace.executor import Executor
from hyperspace.providers import ProviderError
from hyperspace.router import select_tier
from hyperspace.tiers import Tier

server = Server("hyperspace")

# 模块级配置 (启动时加载一次; key 缺失仅告警, 不阻止启动 —— premium 可选)
_cfg: Config = load_config()
_executor = Executor(_cfg)

# ── 启动诊断 ─────────────────────────────────────────────────────
_STARTUP_MSGS: list[str] = []

_all_tiers = {
    "free_text": "免费文本 (智谱 GLM-4.7-Flash)",
    "free_vision": "免费识图 (智谱 GLM-4.6V-Flash)",
    "cheap_capable": "廉价能力 (DeepSeek/Kimi)",
    "premium": "高精度 (Claude/GPT)",
}
for tname, tdesc in _all_tiers.items():
    cands = _cfg.candidates_for(tname)
    if cands:
        descs = [f"{c.provider}/{c.model}" for c in cands]
        _STARTUP_MSGS.append(f"  ✅ {tname:<15s} {' → '.join(descs)}")
    else:
        key_envs = {
            "free_text": "ZHIPU_API_KEY",
            "free_vision": "ZHIPU_API_KEY",
            "cheap_capable": "DEEPSEEK_API_KEY 或 MOONSHOT_API_KEY",
            "premium": "OPENROUTER_API_KEY",
        }
        hint = key_envs.get(tname, "?")
        _STARTUP_MSGS.append(f"  ⏸ {tname:<15s} 无可用候选 (需 {hint})")

if not _cfg.candidates_for("free_text") and not _cfg.candidates_for("cheap_capable"):
    _STARTUP_MSGS.insert(0, "  ⛔ 所有档位均无可用候选! 请在 .env 配置 API key。")
    _STARTUP_MSGS.append("  📄 参考 .env.example 或 README.md")

_STARTUP_MSGS.append(f"  📊 已有成本日志: {len([e for e in open(COST_LOG).readlines() if e.strip()]) if COST_LOG.exists() else 0} 条")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """声明唯一工具 hyperspace_query."""
    return [
        types.Tool(
            name="hyperspace_query",
            description=(
                "向云端大模型提问并获取回答 (自动路由到免费/廉价档以降本). "
                "默认 auto: 有图→免费识图(GLM-4V-Flash), 复杂任务→廉价档(DeepSeek/Kimi), "
                "其余→免费文本(GLM-4-Flash). 可用 mode 显式指定档位. "
                "全部走厂商官方 API, 合法合规."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "要提问的内容 (必填).",
                    },
                    "images": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "图片列表 (可选). 元素可为本地路径 / http(s) URL / data:image base64. "
                        "传入后自动走免费识图档.",
                    },
                    "context": {
                        "type": "string",
                        "description": "额外系统上下文 (可选), 作为 system message 前置.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": _MODES,
                        "default": "auto",
                        "description": "路由模式: auto(默认, 自动判定) | free_text | free_vision | "
                        "cheap_capable | premium. 非 auto 时强制该档.",
                    },
                },
                "required": ["prompt"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """分发工具调用."""
    if name != "hyperspace_query":
        return [types.TextContent(type="text", text=f"[hyperspace] ⛔ 未知工具: {name}")]

    prompt: str = arguments.get("prompt", "")
    if not prompt:
        return [types.TextContent(type="text", text="[hyperspace] ⛔ 缺少必填参数 prompt")]
    images: list[str] | None = arguments.get("images")
    context: str | None = arguments.get("context")
    mode_str: str = arguments.get("mode", "auto")

    # 解析 mode
    try:
        mode = Tier.from_str(mode_str)
    except ValueError as e:
        return [types.TextContent(type="text", text=f"[hyperspace] ⛔ {e}")]

    # 路由
    tier = select_tier(prompt, images, mode, _cfg)
    print(f"[hyperspace] 路由: mode={mode_str} → tier={tier.value}", file=sys.stderr, flush=True)

    # 候选可用性预检 (避免无谓网络调用)
    if not _cfg.candidates_for(tier.value):
        return [types.TextContent(
            type="text",
            text=(f"[hyperspace] ⛔ tier={tier.value} 无可用候选 "
                  f"(对应 provider 的 API key 未配置, 见 .env / .env.example)."),
        )]

    # 执行 (含回退/升档)
    try:
        resp = await _executor.execute(tier, prompt, images=images, context=context)
    except ProviderError as e:
        return [types.TextContent(type="text", text=f"[hyperspace] ✗ 执行失败: {e}")]

    # 成本追踪
    stat = record_cost(
        provider=resp.provider,
        model=resp.model,
        requested_tier=tier.value,
        actual_tier=getattr(resp, "actual_tier", tier.value),
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
    )

    # 返回: 模型回答 + 一行路由/成本元信息 (便于 Agent 与用户感知降本效果)
    meta = (f"\n\n---\n[hyperspace] ✓ {resp.provider}/{resp.model} "
            f"(档位 {stat['actual_tier']}, "
            f"tokens {stat['prompt_tokens']}→{stat['completion_tokens']}, "
            f"等效省 ${stat['saved_usd']:.4f})")
    return [types.TextContent(type="text", text=resp.text + meta)]


async def main():
    print("[hyperspace] 🚀 启动", file=sys.stderr, flush=True)
    for msg in _STARTUP_MSGS:
        print(f"[hyperspace] {msg}", file=sys.stderr, flush=True)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
