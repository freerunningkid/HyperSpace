#!/usr/bin/env python3
"""HyperSpace CLI —— 让本地 Agent 免费调用 DeepSeek Web 等大模型.

用法:
    hyperspace ask <prompt>                    # 一问一答
    hyperspace ask <prompt> --search           # 联网搜索
    hyperspace ask <prompt> --mode force_web   # 强制 Web 引擎
    hyperspace ask <prompt> --image img.png    # 识图
    hyperspace chat                            # 交互模式
    hyperspace info                            # 系统信息
    hyperspace summary                         # 成本摘要
    hyperspace serve                           # 兼容旧 MCP 模式

快速开始:
    export ZHIPU_API_KEY=your_key     # 兜底必填
    python -m hyperspace.cli ask "你好"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# ── 强制 UTF-8 输出，避免 Windows GBK 炸 emoji ──
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# ── 路径修正: 支持 python -m hyperspace.cli 和 python cli.py 两种启动 ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

from hyperspace.config import ENV_FILE
from hyperspace.hybrid_engine import HybridRouter
from hyperspace.hybrid_engine.result_processor import ProcessedResult

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("hyperspace.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hyperspace",
        description="HyperSpace — 免费推理 CLI，深度接入 DeepSeek Web 等大模型",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── ask ──
    ask = sub.add_parser("ask", help="一问一答模式")
    ask.add_argument("prompt", nargs="?", default="", help="提问内容")
    ask.add_argument("--mode", "-m", default="auto",
                      choices=["auto", "force_web", "force_zhipu", "force_github", "force_agnes"],
                     help="路由模式 (默认 auto)")
    ask.add_argument("--web-mode", "-w", default="auto",
                     choices=["auto", "quick", "expert", "vision"],
                     help="DeepSeek Web 内部模式 (默认 auto)")
    ask.add_argument("--search", "-s", action="store_true", default=None,
                     help="启用联网搜索")
    ask.add_argument("--no-search", action="store_true", default=None,
                     help="禁用联网搜索")
    ask.add_argument("--session", type=str, default="",
                     help="多轮会话标识符")
    ask.add_argument("--image", "-i", type=str, action="append", default=None,
                     help="图片路径 (可多次)")

    # ── chat ──
    chat = sub.add_parser("chat", help="交互式对话")
    chat.add_argument("--mode", "-m", default="auto",
                       choices=["auto", "force_web", "force_zhipu", "force_github", "force_agnes"])
    chat.add_argument("--web-mode", "-w", default="auto",
                      choices=["auto", "quick", "expert", "vision"])
    chat.add_argument("--search", "-s", action="store_true", default=None)
    chat.add_argument("--no-search", action="store_true", default=None)

    # ── info / summary / serve ── (直接委托已有模块)
    sub.add_parser("info", help="查看系统信息 (同 python -m hyperspace.info)")
    sub.add_parser("summary", help="查看成本摘要 (同 python -m hyperspace.summary)")
    sub.add_parser("serve", help="以 MCP 模式启动 (兼容旧入口)")

    return parser


def _resolve_search(args) -> bool | None:
    if args.search:
        return True
    if args.no_search:
        return False
    return None


async def cmd_ask(args: argparse.Namespace) -> None:
    """执行一问一答。"""
    # 加载 .env 文件确保 API Key 可用
    load_dotenv(ENV_FILE)

    prompt = args.prompt
    if not prompt and sys.stdin.isatty():
        prompt = sys.stdin.read()
    if not prompt:
        print("请输入提问内容")
        sys.exit(1)

    # 从环境变量读取 API Key 传入 HybridRouter
    zhipu_key = os.environ.get("ZHIPU_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

    zhipu_cfg = {"api_key": zhipu_key} if zhipu_key else None
    deepseek_api_cfg = {"api_key": deepseek_key} if deepseek_key else None

    router = HybridRouter(
        zhipu_config=zhipu_cfg,
        deepseek_api_config=deepseek_api_cfg,
    )
    result: ProcessedResult = await router.execute(
        prompt=prompt,
        images=args.image,
        mode=args.mode,
        session_key=args.session,
        web_mode=args.web_mode,
        search_enabled=_resolve_search(args),
    )

    _print_result(result)


async def cmd_chat(args: argparse.Namespace) -> None:
    """交互式多轮对话。"""
    # 加载 .env 文件确保 API Key 可用
    load_dotenv(ENV_FILE)

    print("╔══════════════════════════════════════╗")
    print("║     HyperSpace 交互模式              ║")
    print("║    输入 /bye 退出, /new 重置会话     ║")
    print("╚══════════════════════════════════════╝")
    print()

    zhipu_key = os.environ.get("ZHIPU_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    router = HybridRouter(
        zhipu_config={"api_key": zhipu_key} if zhipu_key else None,
        deepseek_api_config={"api_key": deepseek_key} if deepseek_key else None,
    )
    session_key = "cli-interactive"
    turn = 0

    while True:
        try:
            prompt = input(f"\n[{turn + 1}] You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not prompt:
            continue
        if prompt == "/bye":
            break
        if prompt == "/new":
            session_key = f"cli-interactive-{id(object())}"
            turn = 0
            print("[会话已重置]")
            continue

        result = await router.execute(
            prompt=prompt,
            mode=args.mode,
            session_key=session_key,
            web_mode=args.web_mode,
            search_enabled=_resolve_search(args),
        )

        _print_result(result)
        turn += 1


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数."""
    return max(1, int(len(text) * 0.3))


def _print_result(result: ProcessedResult) -> None:
    """打印路由结果，结构化输出供 Agent 解析和展示."""
    provider = result.used_executor or "?"
    model = result.used_model or ""

    engine_label = {
        "deepseek_web": "DeepSeek Web (¥0)",
        "zhipu": "智谱 GLM (¥0)",
        "github": "GitHub GPT-4o (¥0)",
        "agnes": "Agnes Flash (¥0)",
    }.get(provider, provider)

    # ── Token 估算 ──
    answer = result.answer or ""
    thinking = getattr(result, 'plan', '') or getattr(result, 'thinking', '')
    total_text = thinking + answer if thinking else answer
    est_tokens = _estimate_tokens(total_text)

    # 成本（¥）：使用 cost 模块的精确定价
    try:
        from hyperspace.cost import calculate_cost as calc, record as cost_record
        # 所有 Web / 免费 Provider → ¥0
        cost_rmb = 0.0
        cost_record(
            provider=provider, model=model or "unknown",
            requested_tier=provider, actual_tier=provider,
            prompt_tokens=0, completion_tokens=est_tokens,
        )
    except Exception:
        cost_rmb = 0.0

    # ── 引擎信息行 ──
    sep = "─" * 60
    model_suffix = f" · {model}" if model else ""
    cost_str = f" | {est_tokens}tk · ¥{cost_rmb:.4f}" if cost_rmb > 0 else f" | {est_tokens}tk · ¥0"
    print(f"\n{sep}")
    print(f"[HyperSpace] 🌐 {engine_label}{model_suffix}{cost_str}")
    print(sep)

    # ── 推理过程 (如有) ──
    if thinking:
        print(f"\n[思考]")
        print(thinking)
        print(f"[思考结束]\n")

    # ── 最终回答 ──
    print(answer)
    print(sep)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "info":
        from hyperspace.info import main as info_main
        import sys as _sys
        _sys.argv = [_sys.argv[0]]
        info_main()
        return

    if args.command == "summary":
        from hyperspace.summary import main as summary_main
        import sys as _sys
        _sys.argv = [_sys.argv[0]]
        summary_main()
        return

    if args.command == "serve":
        os.execvp(sys.executable, [sys.executable,
                                   str(_PROJECT_ROOT / "hyperspace" / "server.py")])

    if args.command == "ask":
        asyncio.run(cmd_ask(args))
        return

    if args.command == "chat":
        asyncio.run(cmd_chat(args))
        return


if __name__ == "__main__":
    main()
