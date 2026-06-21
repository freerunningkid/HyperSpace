# -*- coding: utf-8 -*-
"""
Reasonix 中文状态行 — 一行显示模型/费用/令牌/缓存/上下文
接收 stdin JSON: {"model","contextUsed","contextWindow","cwd"}
输出一行替换底部状态栏（UTF-8，无乱码）
"""
import json, os, sys, glob

# Windows 下强制 stdout 输出 UTF-8，避免 GBK 乱码
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 模型名简写映射
MODEL_SHORT = {
    "deepseek-v4-flash": "DS V4F",
    "deepseek-v4-pro":   "DS V4P",
}

def fmt_price(cost):
    """费用格式化，CNY"""
    if cost >= 100:
        return "¥{:.0f}".format(cost)
    if cost >= 1:
        return "¥{:.2f}".format(cost)
    if cost >= 0.01:
        return "¥{:.4f}".format(cost)
    return "¥{:.6f}".format(cost)


def fmt_tok(n):
    """令牌数简写"""
    if n >= 1_000_000:
        return "{:.1f}M".format(n / 1_000_000)
    if n >= 1_000:
        return "{}K".format(n // 1000)
    return str(n)


def find_latest_meta(cwd):
    """按工作区匹配最新的会话 meta.json"""
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
        if raw.startswith("\ufeff"):
            raw = raw[1:]
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        data = {}

    cwd = data.get("cwd", os.getcwd())
    ctx_used = data.get("contextUsed", 0) or 0
    ctx_win = data.get("contextWindow", 0) or 0
    model_raw = data.get("model", "")
    meta = find_latest_meta(cwd)

    # 模型名
    model_short = MODEL_SHORT.get(model_raw, model_raw)
    # 如果映射不到，取最后一段
    if not model_short or model_short == model_raw:
        if "/" in model_raw:
            model_short = model_raw.rsplit("/", 1)[-1]

    if not meta:
        print(model_short)
        return

    cost = meta.get("totalCostUsd", 0) or 0
    cache_hit = meta.get("cacheHitTokens", 0) or 0
    cache_miss = meta.get("cacheMissTokens", 0) or 0
    total_tok = cache_hit + cache_miss
    hit_pct = (cache_hit / total_tok * 100) if total_tok > 0 else 0
    ctx_pct = (ctx_used / ctx_win * 100) if ctx_win else 0

    # 费用 USD → CNY（汇率 7.2）
    cost_cny = cost * 7.2

    parts = [
        model_short,
        "费用 {}".format(fmt_price(cost_cny)),
        "令牌 {}".format(fmt_tok(total_tok)),
        "缓存 {:.0f}%".format(hit_pct),
        "上下文 {:.0f}%".format(ctx_pct),
    ]

    sys.stdout.write(" │ ".join(parts) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
