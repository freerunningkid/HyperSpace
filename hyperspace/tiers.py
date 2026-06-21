"""Tier 枚举 —— Router 与 Provider Registry 共用的分层抽象.

四档:
  free_text      免费文本档 (GLM-4-Flash)        默认日常对话
  free_vision    免费识图档 (GLM-4V-Flash)        有图片时
  cheap_capable  廉价能力档 (DeepSeek/Kimi)        复杂推理/编码
  premium        高精度档 (Claude/GPT via OpenRouter)  可选, 后期
"""

from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    """路由分档. 继承 str 以便直接序列化 / YAML 比对."""

    FREE_TEXT = "free_text"
    FREE_VISION = "free_vision"
    CHEAP_CAPABLE = "cheap_capable"
    PREMIUM = "premium"
    AUTO = "auto"  # 仅作为 mode 入参占位, 不作为真实执行档

    @classmethod
    def from_str(cls, s: str) -> "Tier":
        """从字符串解析, 未知值抛 ValueError (供 inputSchema enum 校验)."""
        try:
            return cls(s)
        except ValueError:
            valid = [t.value for t in cls if t != cls.AUTO]
            raise ValueError(f"未知 tier: {s!r}, 可选: {valid}") from None

    @property
    def is_executable(self) -> bool:
        """auto 不是可执行档, 其余都是."""
        return self != Tier.AUTO
