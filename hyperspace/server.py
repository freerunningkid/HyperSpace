"""HyperSpace MCP 服务端 —— 混合引擎 (DeepSeek Web × DeepSeek API → 智谱 GLM 兜底).

接入 (.mcp.json, Cline 格式):
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
from hyperspace.hybrid_engine import HybridRouter

server = Server("hyperspace")

# ── 模式枚举 (用于 inputSchema) ──────────────────────────────────
_MODES = [
    "auto",
    "free_text",
    "free_vision",
    "cheap_capable",
    "premium",
    "force_web",
    "force_api",
    "force_zhipu",
]
_FORCE_MODES = {"force_web", "force_api", "force_zhipu"}
_LEGACY_MODES = {"free_text", "free_vision", "cheap_capable", "premium"}

# ── 配置 (启动时加载一次) ────────────────────────────────────────
_cfg: Config = load_config()
_executor = Executor(_cfg)

# 混合引擎 (hybrid_config.yaml + API key 配置)
_hybrid_config_path = os.path.join(_PROJECT_ROOT, "config", "hybrid_config.yaml")

# 从旧配置中提取 API executor 配置
_deepseek_api_cfg = None
_zhipu_cfg = None
if _cfg:
    for tier_name in ["cheap_capable", "free_text"]:
        cands = _cfg.candidates_for(tier_name)
        for c in cands:
            if c.provider == "deepseek":
                _deepseek_api_cfg = {
                    "base_url": c.base_url,
                    "model": c.model,
                    "api_key": c.api_key or "",
                    "timeout": 60,
                }
            elif c.provider == "zhipu":
                _zhipu_cfg = {
                    "base_url": c.base_url,
                    "model": c.model,
                    "api_key": c.api_key or "",
                    "timeout": 30,
                }

_hybrid_router = HybridRouter(
    config_path=_hybrid_config_path if os.path.exists(_hybrid_config_path) else None,
    deepseek_api_config=_deepseek_api_cfg,
    zhipu_config=_zhipu_cfg,
)

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
        _STARTUP_MSGS.append(f"  [OK] {tname:<15s} {' → '.join(descs)}")
    else:
        key_envs = {
            "free_text": "ZHIPU_API_KEY",
            "free_vision": "ZHIPU_API_KEY",
            "cheap_capable": "DEEPSEEK_API_KEY 或 MOONSHOT_API_KEY",
            "premium": "OPENROUTER_API_KEY",
        }
        hint = key_envs.get(tname, "?")
        _STARTUP_MSGS.append(f"  [--] {tname:<15s} 无可用候选 (需 {hint})")

# 混合引擎状态
_hybrid_config_status = "已加载" if os.path.exists(_hybrid_config_path) else "使用默认配置"
_web_auth_status = "有凭据" if _hybrid_router._get_saved_auth() else "无凭据 (需 web_auth --extract)"
_api_key_status = "已配 DeepSeek API" if _deepseek_api_cfg and _deepseek_api_cfg.get("api_key") else "未配 DeepSeek API"
_STARTUP_MSGS.append(f"  混合引擎: {_hybrid_config_status} | Web: {_web_auth_status} | API: {_api_key_status}")
_hybrid_router_type = type(_hybrid_router).__name__
_ctx_mgr_status = "上下文管理已启用" if hasattr(_hybrid_router, '_ctx_mgr') and _hybrid_router._ctx_mgr else "无上下文管理 (需登录 Web)"
_web_ready = " (Web 就绪)" if hasattr(_hybrid_router, '_web_client') and _hybrid_router._web_client else " (仅 API/Zhipu)"
_STARTUP_MSGS.append(f"  路由模式: auto / force_web(原生) / force_api / force_zhipu{_web_ready}")
_STARTUP_MSGS.append(f"  上下文管理: {_ctx_mgr_status} | session_id 参数支持多轮对话")

if not _cfg.candidates_for("free_text") and not _cfg.candidates_for("cheap_capable"):
    _STARTUP_MSGS.insert(0, "  [!!] 所有档位均无可用候选! 请在 .env 配置 API key。")
    _STARTUP_MSGS.append("  参考 .env.example 或 README.md")

_cost_count = 0
if COST_LOG.exists():
    try:
        with open(COST_LOG, encoding="utf-8") as _f:
            _cost_count = len([e for e in _f.readlines() if e.strip()])
    except (PermissionError, FileNotFoundError, OSError) as _e:
        _STARTUP_MSGS.append(f"  [!!] 成本日志读取失败: {_e}")
_STARTUP_MSGS.append(f"  成本日志: {_cost_count} 条")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """声明 hyperspace_query 工具 (增强版)."""
    return [
        types.Tool(
            name="hyperspace_query",
            description=(
                "向云端大模型提问并获取回答 (混合引擎: DeepSeek Web + API 为主, 智谱 GLM 兜底). "
                "默认 auto: 有图/搜索/规划/长文 → Web 端 (零 Token), "
                "代码/翻译/结构化 → API (低成本), 其余→ Web 端经济优先. "
                "可用 mode 显式指定引擎: force_web | force_api | force_zhipu."
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
                        "description": "图片列表 (可选). 元素可为本地路径 / http(s) URL / data:image base64.",
                    },
                    "context": {
                        "type": "string",
                        "description": "额外系统上下文 (可选), 作为 system message 前置.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": _MODES,
                        "default": "auto",
                        "description": "路由模式: auto(自动判定) | free_text | free_vision | "
                        "cheap_capable | premium | "
                        "force_web(强制 Web 端) | force_api(强制 API) | force_zhipu(强制智谱兜底).",
                    },
                    "session_id": {
                        "type": "string",
                        "default": "",
                        "description": "多轮对话会话标识 (可选). 同一 id 自动追踪上下文, "
                        "Web 端窗口满时自动压缩历史并创建新会话. "
                        "不传或空 = 每次新建 (无状态, 适合单次问答).",
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
        return [types.TextContent(type="text", text=f"[hyperspace] !! 未知工具: {name}")]

    prompt: str = arguments.get("prompt", "")
    if not prompt:
        return [types.TextContent(type="text", text="[hyperspace] !! 缺少必填参数 prompt")]
    images: list[str] | None = arguments.get("images")
    context: str | None = arguments.get("context")
    mode_str: str = arguments.get("mode", "auto")
    session_key: str = arguments.get("session_id", "")

    # ── 混合引擎路径 (新 mode + auto) ──
    if mode_str in _FORCE_MODES or mode_str == "auto":
        try:
            result = await _hybrid_router.execute(
                prompt=prompt,
                images=images,
                context=context,
                mode=mode_str,
                session_key=session_key,
            )
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"[hyperspace] !! 混合引擎执行失败: {e}",
            )]

        # 如果混合引擎返回 legacy fallback, 降级到旧路由
        if result.used_executor == "legacy":
            # 记录并降级
            print(f"[hyperspace] 混合引擎返回 legacy 标记, 降级旧路由", file=sys.stderr, flush=True)
            return await _legacy_route(prompt, images, context, mode_str)

        # 成本追踪 (只追踪实际产生成本的调用)
        meta_lines = [f"\n\n---\n[hyperspace] 引擎: {result.used_executor}/{result.used_model}"]
        if result.plan:
            meta_lines.append(f"规划: {result.plan[:200]}")
        meta = "\n".join(meta_lines)

        return [types.TextContent(type="text", text=result.answer + meta)]

    # ── 旧路由路径 (legacy modes) ──
    if mode_str in _LEGACY_MODES or mode_str == "auto":
        return await _legacy_route(prompt, images, context, mode_str)

    return [types.TextContent(type="text", text=f"[hyperspace] !! 未知 mode: {mode_str}")]


async def _legacy_route(
    prompt: str,
    images: list[str] | None,
    context: str | None,
    mode_str: str,
) -> list[types.TextContent]:
    """旧路由: 使用 select_tier + Executor (兼容 free_text/free_vision/cheap_capable/premium)."""
    # 解析 mode
    try:
        mode = Tier.from_str(mode_str)
    except ValueError as e:
        return [types.TextContent(type="text", text=f"[hyperspace] !! {e}")]

    # 路由
    tier = select_tier(prompt, images, mode, _cfg)
    print(f"[hyperspace] 旧路由: mode={mode_str} -> tier={tier.value}", file=sys.stderr, flush=True)

    # 候选可用性预检
    if not _cfg.candidates_for(tier.value):
        return [types.TextContent(
            type="text",
            text=(f"[hyperspace] !! tier={tier.value} 无可用候选 "
                  f"(对应 provider 的 API key 未配置, 见 .env / .env.example)."),
        )]

    # 执行 (含回退/升档)
    try:
        resp = await _executor.execute(tier, prompt, images=images, context=context)
    except ProviderError as e:
        return [types.TextContent(type="text", text=f"[hyperspace] x 执行失败: {e}")]

    # 成本追踪
    stat = record_cost(
        provider=resp.provider,
        model=resp.model,
        requested_tier=tier.value,
        actual_tier=getattr(resp, "actual_tier", tier.value),
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
    )

    # 返回
    meta = (f"\n\n---\n[hyperspace] v {resp.provider}/{resp.model} "
            f"(档位 {stat['actual_tier']}, "
            f"tokens {stat['prompt_tokens']}->{stat['completion_tokens']}, "
            f"等效省 ${stat['saved_usd']:.4f})")
    return [types.TextContent(type="text", text=resp.text + meta)]


async def main():
    print("[hyperspace] ** 启动 (v2.0 混合引擎)", file=sys.stderr, flush=True)
    for msg in _STARTUP_MSGS:
        print(f"[hyperspace] {msg}", file=sys.stderr, flush=True)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
