"""HyperSpace MCP 服务端 —— 混合引擎 (多 Provider 架构 v2.0).

接入 (.mcp.json, Cline 格式):
  "hyperspace": {
    "command": "python",
    "args": ["D:\\\\Reasonix\\\\HyperSpace\\\\hyperspace\\\\server.py"],
    "env": {"PYTHONIOENCODING": "utf-8"},
    "autoApprove": ["*"]
  }

约定: 低级 mcp SDK (非 FastMCP), 中文返回 + emoji 状态, stderr 标启动
(标准 MCP SDK, 中文返回 + emoji 状态, stderr 标启动).
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
from hyperspace.providers.registry import ProviderRegistry
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
_WEB_MODES = ["auto", "quick", "expert", "vision"]

# ── Provider 中文标签 ────────────────────────────────────────────
_PROVIDER_LABELS: dict[str, str] = {
    "deepseek_web":          "DeepSeek Web 免费网页端",
    "deepseek_api":          "DeepSeek API",
    "zhipu":                 "智谱 API 免费",          # 旧 executor 名兼容
    "zhipu_api":             "智谱 API 免费",
    "qwen_api":              "Qwen API",
    "siliconflow_nex_n2_pro": "SiliconFlow 免费",
    "agnes_text":            "Agnes 免费文本",
    "agnes_image":           "Agnes 免费图片",
    "agnes_video":           "Agnes 免费视频",
    "chatglm_web":           "ChatGLM Web → Agnes",
    "qwen_chat_web":         "Qwen Web → API",
}


def _get_provider_label(provider_id: str) -> str:
    """根据 provider id 返回可读中文标签。"""
    return _PROVIDER_LABELS.get(provider_id, provider_id)


# ── v2.0 Provider 枚举 ───────────────────────────────────────────
_PROVIDERS = [
    "auto",
    "deepseek_web", "deepseek_api", "zhipu_api", "qwen_api",
    "siliconflow_nex_n2_pro",
    "agnes_text", "agnes_image", "agnes_video",
    "chatglm_web", "qwen_chat_web",
]
_ROUTING_STRATEGIES = [
    "auto", "web_first", "zero_cost_first", "api_first",
    "cheapest", "fastest", "balanced", "fallback", "force_provider",
]
_EXPECTED_OUTPUTS = [
    "answer", "plan", "json", "structured", "summary", "critique", "final_action_plan",
]

# ── 配置 (启动时加载一次) ────────────────────────────────────────
_cfg: Config = load_config()
_executor = Executor(_cfg)

# v2.0: 加载 Provider Registry
_providers_config_path = os.path.join(_PROJECT_ROOT, "config", "providers.yaml")
_registry: ProviderRegistry | None = None
_registry_load_error: str | None = None
try:
    if os.path.exists(_providers_config_path):
        _registry = ProviderRegistry.from_config(_providers_config_path)
        _STARTUP_MSGS_LATER: list[str] = []
    else:
        _registry_load_error = f"配置文件不存在: {_providers_config_path}"
except Exception as e:
    _registry_load_error = str(e)

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
    provider_registry=_registry,
    providers_config_path=_providers_config_path if os.path.exists(_providers_config_path) else None,
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

# v2.0: Provider Registry 启动诊断
if _registry:
    provider_ids = _registry.list_ids()
    enabled_count = len(_registry.list_enabled())
    placeholder_count = sum(
        1 for p in _registry.list_all()
        if hasattr(p, 'type') and str(p.type) == "placeholder_web"
    )
    _STARTUP_MSGS.append(f"  Provider Registry: {len(provider_ids)} 已注册 / {enabled_count} 可用 / {placeholder_count} 占位")
    _STARTUP_MSGS.append(f"  Provider IDs: {', '.join(provider_ids)}")
else:
    if _registry_load_error:
        _STARTUP_MSGS.append(f"  Provider Registry: 加载失败 ({_registry_load_error})，使用默认三 executor")
    else:
        _STARTUP_MSGS.append(f"  Provider Registry: 未配置，使用默认三 executor")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """声明 hyperspace_query + hyperspace_health 工具."""
    return [
        types.Tool(
            name="hyperspace_query",
            description=(
                "HyperSpace 多 Provider 混合推理 MCP 工具. "
                "不确定时使用 auto, HyperSpace 会根据 prompt、图片、文件和搜索意图自动判断. "
                "web_mode=quick: 关闭 thinking, 适合闲聊/简单问答/快速回答. "
                "web_mode=expert: 开启 thinking, 适合数学、复杂推理、规划、深度分析、复杂代码. "
                "web_mode=vision: 上传图片/文件 ref_file_ids 并开启 thinking, 适合截图、图片、PDF/Word/Excel/PPT/代码文件引用. "
                "search_enabled=true: 适合新闻、实时信息、最新资料、需要联网验证的问题; 图片/文件识图通常不传或 false. "
                "files/images: 可为本地路径、http(s) URL 或 data URI. "
                "mode 是执行器路由: auto/force_web/force_api/force_zhipu/legacy tiers; web_mode 是 DeepSeek Web 内部产品模式. "
                "provider: 显式指定 provider (auto = 自动). "
                "routing_strategy: 路由策略 (auto/web_first/zero_cost_first/api_first/cheapest/fastest/balanced). "
                "expected_output: 输出类型 (answer/plan/json/structured/summary/critique). "
                "session_id 用于多轮对话; 不传或空 = 单次无状态."
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
                        "description": "图片/截图列表 (可选). 元素可为本地路径 / http(s) URL / data:image base64.",
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "文件列表 (可选). 元素可为本地路径 / http(s) URL / data URI.",
                    },
                    "web_mode": {
                        "type": "string",
                        "enum": _WEB_MODES,
                        "default": "auto",
                        "description": "DeepSeek Web 产品模式: auto | quick | expert | vision.",
                    },
                    "search_enabled": {
                        "type": "boolean",
                        "description": "是否启用 DeepSeek Web 联网搜索.",
                    },
                    "context": {
                        "type": "string",
                        "description": "额外系统上下文 (可选), 作为 system message 前置.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": _MODES,
                        "default": "auto",
                        "description": "路由模式: auto | force_web | force_api | force_zhipu | legacy tiers.",
                    },
                    "provider": {
                        "type": "string",
                        "enum": _PROVIDERS,
                        "default": "auto",
                        "description": "显式指定 provider. auto = 自动选择.",
                    },
                    "routing_strategy": {
                        "type": "string",
                        "enum": _ROUTING_STRATEGIES,
                        "default": "auto",
                        "description": "路由策略: auto | web_first | zero_cost_first | api_first | cheapest | fastest | balanced | fallback.",
                    },
                    "expected_output": {
                        "type": "string",
                        "enum": _EXPECTED_OUTPUTS,
                        "default": "answer",
                        "description": "期望输出类型: answer | plan | json | structured | summary | critique | final_action_plan.",
                    },
                    "session_id": {
                        "type": "string",
                        "default": "",
                        "description": "多轮对话会话标识 (可选).",
                    },
                },
                "required": ["prompt"],
            },
        ),
        types.Tool(
            name="hyperspace_health",
            description=(
                "查询所有已注册 provider 的状态、能力、fallback 目标和最近错误. "
                "不暴露任何 API Key 或敏感凭据内容. "
                "返回 provider id, type, status, score, capabilities, cost_tier, fallback_to, last_error."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """分发工具调用."""
    # ── hyperspace_health ──
    if name == "hyperspace_health":
        return await _handle_health()

    if name != "hyperspace_query":
        return [types.TextContent(type="text", text=f"[hyperspace] !! 未知工具: {name}")]

    prompt: str = arguments.get("prompt", "")
    if not prompt:
        return [types.TextContent(type="text", text="[hyperspace] !! 缺少必填参数 prompt")]
    images: list[str] | None = arguments.get("images")
    files: list[str] | None = arguments.get("files")
    attachments = list(dict.fromkeys((images or []) + (files or [])))
    context: str | None = arguments.get("context")
    mode_str: str = arguments.get("mode", "auto")
    web_mode: str = arguments.get("web_mode", "auto")
    search_enabled: bool | None = arguments.get("search_enabled")
    session_key: str = arguments.get("session_id", "")
    provider: str = arguments.get("provider", "auto")
    routing_strategy: str = arguments.get("routing_strategy", "auto")
    expected_output: str = arguments.get("expected_output", "answer")

    # ── 混合引擎路径 (新 mode + auto) ──
    if mode_str in _FORCE_MODES or mode_str == "auto":
        try:
            result = await _hybrid_router.execute(
                prompt=prompt,
                images=attachments,
                context=context,
                mode=mode_str,
                session_key=session_key,
                web_mode=web_mode,
                search_enabled=search_enabled,
                provider=provider,
                routing_strategy=routing_strategy,
                expected_output=expected_output,
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
            return await _legacy_route(prompt, attachments, context, mode_str)

        # Provider 来源标签
        executor_id = result.used_executor or "unknown"
        label = _get_provider_label(executor_id)

        # 成本追踪 (只追踪实际产生成本的调用)
        meta_lines = [f"\n\n---\n[hyperspace] 引擎: {executor_id}/{result.used_model}"]
        if result.plan:
            meta_lines.append(f"规划: {result.plan[:200]}")
        meta = "\n".join(meta_lines)

        tagged = f"【{label}】\n{result.answer}"
        return [types.TextContent(type="text", text=tagged + meta)]

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

    # Provider 来源标签
    label = _get_provider_label(resp.provider)

    # 返回
    meta = (f"\n\n---\n[hyperspace] v {resp.provider}/{resp.model} "
            f"(档位 {stat['actual_tier']}, "
            f"tokens {stat['prompt_tokens']}->{stat['completion_tokens']}, "
            f"等效省 ${stat['saved_usd']:.4f})")
    tagged = f"【{label}】\n{resp.text}"
    return [types.TextContent(type="text", text=tagged + meta)]


async def _handle_health() -> list[types.TextContent]:
    """返回所有 provider 的健康/能力/fallback 信息。

    不暴露任何 API Key 或敏感凭据。
    """
    if not _registry:
        return [types.TextContent(
            type="text",
            text="[hyperspace] Provider Registry 未加载。请确认 config/providers.yaml 存在且配置正确。",
        )]

    providers_info: dict[str, dict] = {}
    for p in _registry.list_all():
        pid = p.id
        # 同步获取基础健康信息（不调用异步 health_check）
        health_status = str(p.type) if hasattr(p, 'type') else "unknown"

        info = {
            "type": str(p.type) if hasattr(p, 'type') else "unknown",
            "cost_tier": str(p.cost_tier) if hasattr(p, 'cost_tier') else "unknown",
            "capabilities": {
                k: v for k, v in vars(p.capabilities).items()
                if not k.startswith("_") and v is True
            } if hasattr(p, 'capabilities') else {},
        }

        # fallback 信息
        fallback_to = _registry._fallback_map.get(pid)
        if fallback_to:
            info["fallback_to"] = fallback_to

        # 尝试获取健康状态
        try:
            health = await p.health_check()
            info["status"] = str(health.status)
            info["score"] = health.score
            if health.last_error:
                info["last_error"] = health.last_error
            if health.message:
                info["message"] = health.message
        except Exception as e:
            info["status"] = "error"
            info["health_error"] = str(e)[:200]

        providers_info[pid] = info

    import json
    result = {
        "providers": providers_info,
        "total": len(providers_info),
    }

    return [types.TextContent(
        type="text",
        text=json.dumps(result, ensure_ascii=False, indent=2),
    )]


async def main():
    print("[hyperspace] ** 启动 (v2.0 多 Provider 混合引擎)", file=sys.stderr, flush=True)
    for msg in _STARTUP_MSGS:
        print(f"[hyperspace] {msg}", file=sys.stderr, flush=True)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
