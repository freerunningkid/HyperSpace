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

# ── 路径修正: 支持 python -m hyperspace.cli 和 python cli.py 两种启动 ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
                     choices=["auto", "force_web", "force_api", "force_zhipu"],
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
                      choices=["auto", "force_web", "force_api", "force_zhipu"])
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
    prompt = args.prompt
    if not prompt and sys.stdin.isatty():
        prompt = sys.stdin.read()
    if not prompt:
        print("请输入提问内容")
        sys.exit(1)

    router = HybridRouter()
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
    print("╔══════════════════════════════════════╗")
    print("║     HyperSpace 交互模式              ║")
    print("║    输入 /bye 退出, /new 重置会话     ║")
    print("╚══════════════════════════════════════╝")
    print()

    router = HybridRouter()
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


def _box_line(text: str, width: int = 58) -> str:
    """生成框内一行，两端各留一个空格，总宽 width. 自动处理中文/emoji 等宽字符。"""
    vis = sum(2 if ord(c) > 0x2E80 else 1 for c in text)
    pad = width - vis - 2  # 减去两端空格
    return f"║ {text}{' ' * pad} ║"


def _print_result(result: ProcessedResult) -> None:
    """打印路由结果，带明显分隔。"""
    provider = result.used_executor or "?"
    model = result.used_model or ""

    engine_label = {
        "deepseek_web": "DeepSeek Web (¥0)",
        "deepseek_api": "DeepSeek API",
        "zhipu": "智谱 GLM (¥0)",
    }.get(provider, provider)

    sep = '═' * 58
    print(f"\n╔{sep}╗")
    print(_box_line(f"🌐 {engine_label}"))
    if model:
        print(_box_line(f"   {model}"))
    print(f"╚{sep}╝")

    # 思维链
    thinking = getattr(result, 'plan', '') or getattr(result, 'thinking', '')
    if thinking:
        print(f"\n── 推理过程 ──\n{thinking}\n──────────────\n")

    # 回答
    print(result.answer)


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
