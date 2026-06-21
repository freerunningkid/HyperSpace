"""Executor —— 按 tier 执行 provider 调用 + 回退/升档.

流程:
  1. 取 tier 的候选列表 (已过滤掉缺 key 的)
  2. 依次尝试每个候选; 任何 ProviderError → 跳下一个
  3. 整 tier 失败 → 按升档链 (escalation_chain) 升一档, 重试
  4. 全部失败 → 抛 ProviderError, 由 server 转成 MCP 错误文本

设计: executor 是唯一「真正打网络」的层; router 只决策. 两者解耦便于测试.
"""

from __future__ import annotations

from .config import Config
from .providers import OpenAICompatProvider, ProviderError, ProviderResponse
from .tiers import Tier


class Executor:
    """执行一个 tier 的候选并负责回退."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    async def execute(
        self,
        tier: Tier,
        prompt: str,
        images: list[str] | None = None,
        context: str | None = None,
    ) -> ProviderResponse:
        """执行指定 tier; 失败则升档, 直至耗尽."""
        tried: list[str] = []  # 已尝试的 (provider/model) 用于诊断

        # 当前 tier + 升档链一起去重尝试
        tiers_to_try = [tier.value] + self.cfg.escalation_after(tier.value)
        for tval in tiers_to_try:
            candidates = self.cfg.candidates_for(tval)
            if not candidates:
                continue
            for cand in candidates:
                tag = f"{cand.provider}/{cand.model}"
                tried.append(tag)
                try:
                    provider = OpenAICompatProvider(cand)
                    resp = await provider.chat(prompt, images=images, context=context)
                    # 记录实际命中的 tier (可能与请求 tier 不同, 因升档)
                    resp.__dict__["requested_tier"] = tier.value
                    resp.__dict__["actual_tier"] = tval
                    return resp
                except ProviderError as e:
                    # 打到 stderr (MCP 日志可见), 继续回退
                    import sys
                    print(f"[hyperspace] ⚠ {tag} 失败, 回退: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                    continue
        raise ProviderError(
            f"所有候选均失败, 已尝试: {tried}. 请检查 .env 的 API key 与网络."
        )
