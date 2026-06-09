"""
Reasonix statusline — 一行显示累计消费 + token + 缓存 + 上下文
接收 stdin JSON: {"model","contextUsed","contextWindow","cwd"}
输出一行替换底部状态栏
"""
import json, os, sys, glob

def fmt_price(cost):
    if cost >= 100:
        return "Y{:.0f}".format(cost)
    if cost >= 1:
        return "Y{:.2f}".format(cost)
    if cost >= 0.01:
        return "Y{:.4f}".format(cost)
    return "Y{:.6f}".format(cost)

def fmt_tok(n):
    if n >= 1_000_000:
        return "{:.1f}M".format(n / 1_000_000)
    if n >= 1_000:
        return "{}K".format(n // 1000)
    return str(n)

def find_latest_meta(cwd):
    session_dir = os.path.join(os.path.expanduser("~"), ".reasonix", "sessions")
    metas = sorted(
        glob.glob(os.path.join(session_dir, "*.meta.json")),
        key=os.path.getmtime, reverse=True,
    )
    for path in metas:
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
            ws = m.get("workspace", "") or ""
            if ws and cwd.startswith(ws):
                return m
        except (json.JSONDecodeError, OSError):
            continue
    if metas:
        try:
            with open(metas[0], encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return None

def main():
    try:
        raw = sys.stdin.read()
        if raw.startswith("﻿"):
            raw = raw[1:]
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        data = {}

    cwd = data.get("cwd", os.getcwd())
    ctx_used = data.get("contextUsed", 0) or 0
    ctx_win = data.get("contextWindow", 0) or 0
    meta = find_latest_meta(cwd)

    if not meta:
        print("cost: --")
        return

    cost = meta.get("totalCostUsd", 0) or 0
    cache_hit = meta.get("cacheHitTokens", 0) or 0
    cache_miss = meta.get("cacheMissTokens", 0) or 0
    total_tok = cache_hit + cache_miss
    hit_pct = (cache_hit / total_tok * 100) if total_tok > 0 else 0
    ctx_pct = (ctx_used / ctx_win * 100) if ctx_win else 0

    # 一行显示全部
    parts = [
        "cost {}".format(fmt_price(cost)),
        "tok {}".format(fmt_tok(total_tok)),
        "cache {:.0f}%".format(hit_pct),
        "ctx {:.0f}%".format(ctx_pct),
    ]
    sys.stdout.write(" | ".join(parts) + "\n")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
