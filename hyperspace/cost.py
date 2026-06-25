"""成本追踪 —— 记录每次命中的 provider/model/token, 按 DeepSeek V4 官方定价折算.

DeepSeek V4 定价 (元/百万 tokens, 2025-06):
  ┌─────────────────┬──────────┬────────────┬────────┐
  │ 模型            │ 输入(命中)│ 输入(未命中)│ 输出   │
  ├─────────────────┼──────────┼────────────┼────────┤
  │ V4 Flash        │ ¥0.02   │ ¥1.00      │ ¥2.00  │
  │ V4 Pro          │ ¥0.025  │ ¥3.00      │ ¥6.00  │
  └─────────────────┴──────────┴────────────┴────────┘

HyperSpace Web 端: ¥0 (免费). 智谱 GLM: ¥0 (免费).

日志写入 data/hyperspace_cost.log (gitignored), 一行 JSON 一条记录.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

from .config import COST_LOG

# 定价: (provider, model_prefix) → (input_cache_hit, input_cache_miss, output) 元/M tokens
# DeepSeek V4 系列
PRICING = {
    # V4 Flash
    ("deepseek", "deepseek-v4-flash"):             (0.02, 1.00, 2.00),
    # V4 Pro
    ("deepseek", "deepseek-v4-pro"):               (0.025, 3.00, 6.00),
    # 旧版 deepseek-chat (兼容)
    ("deepseek", "deepseek-chat"):                 (0.025, 3.00, 6.00),
    # 免费档
    ("zhipu", "glm-4.7-flash"):                    (0.0, 0.0, 0.0),
    ("zhipu", "glm-4.6v-flash"):                   (0.0, 0.0, 0.0),
    ("deepseek_web", "deepseek-chat"):             (0.0, 0.0, 0.0),  # Web 端免费
    ("github", "openai/gpt-4o"):                   (0.0, 0.0, 0.0),  # GitHub Models
    ("agnes", "agnes-2.0-flash"):                  (0.0, 0.0, 0.0),  # Agnes
    ("agnes", "agnes-image-2.1-flash"):            (0.0, 0.0, 0.0),  # Agnes
    ("agnes", "agnes-video-v2.0"):                 (0.0, 0.0, 0.0),  # Agnes
}


def _price_for(provider: str, model: str) -> tuple[float, float, float]:
    """查定价; 精确 provider+model 前缀匹配, 未匹配返回 (0,0,0)."""
    for (p, m), price in PRICING.items():
        if provider == p and model.startswith(m):
            return price
    return (0.0, 0.0, 0.0)


def calculate_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int = 0,
) -> dict:
    """计算实际成本 (元).

    Returns:
        {input_cost, cache_hit_cost, output_cost, total_cost, all in RMB}
    """
    ip_hit, ip_miss, op = _price_for(provider, model)
    cache_miss_tokens = max(prompt_tokens - cache_hit_tokens, 0)
    input_cost = (cache_miss_tokens / 1_000_000) * ip_miss + (cache_hit_tokens / 1_000_000) * ip_hit
    output_cost = (completion_tokens / 1_000_000) * op
    total = input_cost + output_cost
    return {
        "input_cost_rmb": round(input_cost, 6),
        "output_cost_rmb": round(output_cost, 6),
        "total_cost_rmb": round(total, 6),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_hit_tokens": cache_hit_tokens,
    }


def estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数 (中英文混合)."""
    return max(1, int(len(text) * 0.3))


def record(
    *,
    provider: str,
    model: str,
    requested_tier: str,
    actual_tier: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int = 0,
) -> dict:
    """记录一次命中, 返回统计字典."""
    cost = calculate_cost(provider, model, prompt_tokens, completion_tokens, cache_hit_tokens)

    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "model": model,
        "requested_tier": requested_tier,
        "actual_tier": actual_tier,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "input_cost_rmb": cost["input_cost_rmb"],
        "output_cost_rmb": cost["output_cost_rmb"],
        "total_cost_rmb": cost["total_cost_rmb"],
    }
    try:
        with COST_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[hyperspace] ⚠ 成本日志写入失败: {e}", file=sys.stderr, flush=True)
    return entry
