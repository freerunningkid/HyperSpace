# -*- coding: utf-8 -*-
"""HyperSpace 系统信息 —— 一键查看可用档位/Provider/Key/成本快照.

用法:
    python -m hyperspace.info          # 完整信息
    python -m hyperspace.info --keys   # 显示已配 key 名称 (不泄露值)
    python -m hyperspace.info --cost    # 只看成本快照
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from .config import load_config, CONFIG_DIR, DATA_DIR, PROVIDERS_FILE, ROUTING_FILE
from .summary import build_summary, load_entries

# ── 辅助 ──

def _mask_key(key: str) -> str:
    """只显示 key 前后 4 字符, 中间用 *** 替代."""
    if not key:
        return "(未配置)"
    if len(key) < 12:
        return key[:4] + "***" + key[-2:]
    return key[:4] + "****" + key[-4:]


def _yesno(v: Any) -> str:
    return "✅" if v else "⛔ 未配置"


def main():
    parser = argparse.ArgumentParser(description="HyperSpace 系统信息")
    parser.add_argument("--keys", action="store_true", help="只显示 Key 状态")
    parser.add_argument("--cost", action="store_true", help="只显示成本快照")
    args = parser.parse_args()

    cfg = load_config()

    if args.cost:
        show_cost()
        return
    if args.keys:
        show_keys(cfg)
        return

    # ── 完整信息 ──
    print("╔══════════════════════════════════════════════╗")
    print("║            HyperSpace 系统信息               ║")
    print("╠══════════════════════════════════════════════╣")

    # 配置路径
    print("║  配置路径:")
    for f in [PROVIDERS_FILE, ROUTING_FILE]:
        exists = f.exists()
        print(f"║    {'✅' if exists else '⛔'} {f.name}")
    print(f"║    {'✅' if DATA_DIR.exists() else '⛔'} data/")

    print("╠══════════════════════════════════════════════╣")
    # Key 状态
    print("║  API Keys:")
    all_keys = {
        "ZHIPU_API_KEY": "免费档 (智谱 GLM-4.7/4.6V)",
        "DEEPSEEK_API_KEY": "廉价档 (DeepSeek)",
        "MOONSHOT_API_KEY": "廉价档 (Kimi, 备选)",
    }
    for env_name, desc in all_keys.items():
        val = os.environ.get(env_name)
        status = _mask_key(val) if val else "⛔ 未配置"
        print(f"║    {env_name:<20s} {status}")

    print("╠══════════════════════════════════════════════╣")
    # 可用档位
    print("║  可用 Tier 候选 (key 已配):")
    for tier_name in ["free_text", "free_vision", "cheap_capable", "premium"]:
        cands = cfg.candidates_for(tier_name)
        if cands:
            descs = [f"{c.provider}/{c.model}" for c in cands]
            print(f"║    ✅ {tier_name:<20s} {' → '.join(descs)}")
        else:
            print(f"║    ⏸ {tier_name:<20s} 无可用候选 (key 未配置)")

    print("╠══════════════════════════════════════════════╣")
    # 路由规则摘要
    print("║  路由规则:")
    r = cfg.routing
    print(f"║    代码标记:      {', '.join(r.code_markers[:3])}" + ("..." if len(r.code_markers) > 3 else ""))
    print(f"║    复杂关键词:    {', '.join(r.complex_keywords[:4])}" + ("..." if len(r.complex_keywords) > 4 else ""))
    print(f"║    长度阈值:      {r.length_threshold} 字符")
    print(f"║    升档链:        {' → '.join(r.escalation_chain)}")

    print("╠══════════════════════════════════════════════╣")
    # 成本快照
    show_cost(prefix="║  ")

    print("╚══════════════════════════════════════════════╝")


def show_keys(cfg: Any = None):
    """只显示 key 状态."""
    if cfg is None:
        cfg = load_config()
    all_keys = ["ZHIPU_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY"]
    for k in all_keys:
        v = os.environ.get(k)
        status = f"   {_mask_key(v)}" if v else "   ⛔ 未配置"
        print(f"{k:<20s}{status}")


def show_cost(prefix: str = ""):
    """只显示成本快照."""
    entries = load_entries()
    if not entries:
        print(f"{prefix}成本日志: 无数据 (先调用 hyperspace_query)")
        return
    s = build_summary(entries)
    p = prefix
    print(f"{p}总请求:     {s['total']}")
    print(f"{p}免费档占比: {s['free_tier_pct']}%")
    # tier 柱状
    for tier, pct in s["tier_pct"].items():
        bar = "█" * int(pct / 5)
        print(f"{p}  {tier:<20s} {pct:5.1f}% {bar}")
    cu = s["cost_cny"]
    print(f"{p}实耗: ¥{cu['actual']:<8.4f}  | 等效 premium: ¥{cu['equivalent_premium']:<8.4f}  |  ✅ 节省: ¥{cu['saved']:<8.4f}")


if __name__ == "__main__":
    main()
