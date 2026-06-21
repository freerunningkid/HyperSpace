"""Router —— 廉价规则路由: 选 Tier.

auto 模式判定顺序 (零 token 成本):
  1. 有 images            → FREE_VISION
  2. prompt 判定复杂      → CHEAP_CAPABLE
  3. 否则                 → FREE_TEXT (默认免费文本)

复杂判定见 _looks_complex: 代码标记 / 复杂关键词 / 长度, 命中任一即复杂.
规则全部从 routing.yaml 读, 可调.

执行 + 回退逻辑在 executor.py (本文件只负责「选哪个 tier」).
"""

from __future__ import annotations

from .config import Config
from .tiers import Tier


def select_tier(
    prompt: str,
    images: list[str] | None,
    mode: Tier,
    cfg: Config,
) -> Tier:
    """根据 mode/prompt/images 选定执行 tier.

    mode != AUTO 时直接返回该 mode (显式覆盖).
    """
    if mode != Tier.AUTO:
        return mode

    if images:
        return Tier.FREE_VISION
    if _looks_complex(prompt, cfg):
        return Tier.CHEAP_CAPABLE
    return Tier.FREE_TEXT


def _looks_complex(prompt: str, cfg: Config) -> bool:
    """纯规则复杂度判定. 命中任一信号即 True."""
    rules = cfg.routing
    low = prompt.lower()

    # 长度
    if len(prompt) > rules.length_threshold:
        return True
    # 代码标记
    for marker in rules.code_markers:
        if marker in prompt:
            return True
    # 复杂关键词 (中英; 英文小写比对)
    for kw in rules.complex_keywords:
        if kw in prompt or kw.lower() in low:
            return True
    return False
