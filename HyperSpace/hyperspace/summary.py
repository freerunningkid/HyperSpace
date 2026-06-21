# -*- coding: utf-8 -*-
"""成本摘要 —— 读取 data/hyperspace_cost.log, 展示节省快照.

用法:
    python -m hyperspace.summary              # 完整摘要
    python -m hyperspace.summary --json       # JSON 输出 (供脚本消费)
    python -m hyperspace.summary --last       # 只显示最近一次
    python -m hyperspace.summary --since 2026-06-20  # 从某日期起
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .config import COST_LOG


def load_entries(file: Path = COST_LOG) -> list[dict]:
    """读取成本日志, 返回有序条目列表 (最新在末尾)."""
    if not file.exists():
        print(f"[summary] ⛔ 成本日志不存在: {file}", file=sys.stderr)
        print("[summary] 先调用 hyperspace_query 产生数据.", file=sys.stderr)
        return []
    entries: list[dict] = []
    with file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _since_filter(entries: list[dict], since_str: str) -> list[dict]:
    """过滤出指定日期之后的条目."""
    try:
        if "T" in since_str:
            cutoff = datetime.fromisoformat(since_str)
        else:
            cutoff = datetime.fromisoformat(since_str)
    except ValueError:
        print(f"[summary] ⛔ 无法解析日期: {since_str} (格式: YYYY-MM-DD)", file=sys.stderr)
        return entries

    result = []
    for e in entries:
        ts = e.get("ts", "")
        if not ts:
            continue
        try:
            if "T" in ts:
                dt = datetime.fromisoformat(ts)
            else:
                dt = datetime.fromisoformat(ts)
            if dt >= cutoff:
                result.append(e)
        except ValueError:
            continue
    return result


def build_summary(entries: list[dict]) -> dict:
    """从条目列表构建统计摘要."""
    if not entries:
        return {"total": 0, "message": "无数据"}

    total = len(entries)
    tier_count: Counter[str] = Counter()
    provider_count: Counter[str] = Counter()
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_actual_cost = 0.0
    total_equivalent = 0.0
    total_saved = 0.0

    for e in entries:
        tier_count[e.get("actual_tier", "unknown")] += 1
        provider_count[e.get("provider", "unknown")] += 1
        total_prompt_tokens += e.get("prompt_tokens", 0) or 0
        total_completion_tokens += e.get("completion_tokens", 0) or 0
        total_actual_cost += e.get("actual_cost_usd", 0.0) or 0.0
        total_equivalent += e.get("equivalent_premium_usd", 0.0) or 0.0
        total_saved += e.get("saved_usd", 0.0) or 0.0

    # 各 tier 占比
    tier_pct = {t: round(c / total * 100, 1) for t, c in tier_count.most_common()}
    free_pct = round(
        sum(v for t, v in tier_pct.items() if t.startswith("free")), 1
    )

    return {
        "total": total,
        "period": {
            "first": entries[0].get("ts", "?"),
            "last": entries[-1].get("ts", "?"),
        },
        "tier_distribution": dict(tier_count.most_common()),
        "tier_pct": tier_pct,
        "free_tier_pct": free_pct,
        "provider_distribution": dict(provider_count.most_common()),
        "tokens": {
            "prompt": total_prompt_tokens,
            "completion": total_completion_tokens,
            "total": total_prompt_tokens + total_completion_tokens,
        },
        "cost_usd": {
            "actual": round(total_actual_cost, 6),
            "equivalent_premium": round(total_equivalent, 6),
            "saved": round(total_saved, 6),
        },
        # 预估人民币 (按 7.2 汇率)
        "cost_cny": {
            "actual": round(total_actual_cost * 7.2, 4),
            "equivalent_premium": round(total_equivalent * 7.2, 4),
            "saved": round(total_saved * 7.2, 4),
        },
    }


def print_summary(s: dict, json_mode: bool = False):
    """打印摘要到 stdout."""
    if json_mode:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return

    if s["total"] == 0:
        print(s.get("message", "无数据"))
        return

    print("╔══════════════════════════════════════════════╗")
    print("║  HyperSpace 成本摘要                        ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  总请求: {s['total']:<5d}                    ║")
    print(f"║  期间:   {s['period']['first'][:10]} → {s['period']['last'][:10]} ║")
    print(f"║  免费档: {s['free_tier_pct']}%                  ║")
    print("╠══════════════════════════════════════════════╣")

    print("║  Tier 分布:")
    for tier, pct in s["tier_pct"].items():
        bar = "█" * int(pct / 5)
        print(f"║    {tier:<20s} {pct:5.1f}% {bar}")

    print("╠══════════════════════════════════════════════╣")
    print(f"║  Token 总计: {s['tokens']['total']:<8d}          ║")
    print(f"║  其中输入: {s['tokens']['prompt']:<6d} / 输出: {s['tokens']['completion']:<6d}║")
    print("╠══════════════════════════════════════════════╣")

    cu = s["cost_cny"]
    print(f"║  实耗成本:     ¥{cu['actual']:<8.4f}          ║")
    print(f"║  等效 premium: ¥{cu['equivalent_premium']:<8.4f}          ║")
    print(f"║  ✅ 节省:      ¥{cu['saved']:<8.4f}          ║")
    print("╚══════════════════════════════════════════════╝")


def main():
    parser = argparse.ArgumentParser(description="HyperSpace 成本摘要工具")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--last", action="store_true", help="只显示最近一次")
    parser.add_argument("--since", help="从日期起 YYYY-MM-DD")
    args = parser.parse_args()

    entries = load_entries()
    if not entries:
        return

    if args.last:
        entries = entries[-1:]
    if args.since:
        entries = _since_filter(entries, args.since)
    if not entries:
        print("[summary] 过滤后无数据", file=sys.stderr)
        return

    s = build_summary(entries)
    print_summary(s, json_mode=args.json)


if __name__ == "__main__":
    main()
