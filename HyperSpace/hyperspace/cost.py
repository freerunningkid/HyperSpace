"""成本追踪 —— 记录每次命中的 provider/model/tier/token, 折算「等效节省」.

诚实口径 (符合执行闭环铁律, 不预设固定省 %):
  - 实际成本: 免费档 = 0, 廉价档按官方 API 价折算
  - 等效节省: 假设「同样请求走 Claude/GPT premium 价」减去「实际成本」
  - 定价表可改 (PRICING 元组), 默认用公开档位近似值
日志写入 data/hyperspace_cost.log (gitignored), 一行 JSON 一条记录.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

from .config import COST_LOG

# 每百万 token 价格 (美元). 仅作等效节省估算, 非结算依据.
# 按公开文档近似值; 厂商调价时改这里即可. 缺省 (未知) 按 premium 估.
# (provider, model 前缀) → (input $/M, output $/M)
PRICING = {
    # 免费档
    ("zhipu", "glm-4-flash"): (0.0, 0.0),
    ("zhipu", "glm-4v-flash"): (0.0, 0.0),
    ("zhipu", "glm-4.7-flash"): (0.0, 0.0),
    # 廉价档
    ("deepseek", "deepseek-chat"): (0.27, 1.10),
    ("kimi", "moonshot-v1-32k"): (3.30, 3.30),
    # premium (等效基线) —— 用 Claude 3.5 Sonnet 公开价作「如果不省钱会花多少」的锚
    ("premium", "baseline"): (3.00, 15.00),
}


def _price_for(provider: str, model: str) -> tuple[float, float]:
    """查定价; 精确 provider+model 前缀匹配, 否则 0(保守)."""
    for (p, m), price in PRICING.items():
        if provider == p and model.startswith(m):
            return price
    return (0.0, 0.0)


def _equivalent_premium_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """「等效 premium 成本」= 若这请求走 premium 基线要花多少 (美元)."""
    ip, op = PRICING[("premium", "baseline")]
    return (prompt_tokens / 1_000_000) * ip + (completion_tokens / 1_000_000) * op


def record(
    *,
    provider: str,
    model: str,
    requested_tier: str,
    actual_tier: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict:
    """记录一次命中, 返回统计字典 (供 server 拼进返回元信息)."""
    ip, op = _price_for(provider, model)
    actual_cost = (prompt_tokens / 1_000_000) * ip + (completion_tokens / 1_000_000) * op
    equivalent = _equivalent_premium_cost(prompt_tokens, completion_tokens)
    saved = max(equivalent - actual_cost, 0.0)

    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "model": model,
        "requested_tier": requested_tier,
        "actual_tier": actual_tier,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "actual_cost_usd": round(actual_cost, 6),
        "equivalent_premium_usd": round(equivalent, 6),
        "saved_usd": round(saved, 6),
    }
    try:
        with COST_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        # 日志写失败不影响主流程
        print(f"[hyperspace] ⚠ 成本日志写入失败: {e}", file=sys.stderr, flush=True)
    return entry
