"""Provider 能力匹配与筛选逻辑。

将 TaskProfile 映射到必需的 ProviderCapabilities，并提供匹配/筛选函数，
供 Registry 和 Router 使用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ProviderCapabilities

if TYPE_CHECKING:
    from ..hybrid_engine.task_analyzer import TaskProfile


def capability_for_task(
    profile: TaskProfile,
    expected_output: str = "answer",
    has_files: bool = False,
) -> ProviderCapabilities:
    """从任务画像推导必须满足的能力集合。

    规则（按设计规格 §10.5-10.6）：
      - 纯文本 → 只需 text
      - 图片/文件 → 需要 vision_understanding, file_upload
      - 需要搜索 → 需要 web_search
      - 需要规划/长文本 → 偏好 planning, long_context（软约束）
      - JSON/结构化输出 → 需要 structured_output（硬约束）
    """
    caps = ProviderCapabilities(text=True)

    # 硬约束
    if profile.has_image:
        caps.vision_understanding = True
    if profile.has_file or has_files:
        caps.file_upload = True
    if profile.needs_search:
        caps.web_search = True

    # expected_output 对 structured_output 的影响
    if expected_output in ("json", "structured"):
        caps.structured_output = True

    # 软约束（偏好而非必须）
    if profile.needs_planning:
        caps.planning = True
    if profile.is_long:
        caps.long_context = True

    return caps


def matches_capabilities(
    provider_caps: ProviderCapabilities,
    required: ProviderCapabilities,
) -> bool:
    """检查 provider 能力是否满足所有必需项。

    核心字段为硬约束（必须匹配），其余字段为软约束（偏好匹配不影响通过/失败）。
    硬约束字段：text, vision_understanding, file_upload, web_search, structured_output
    """
    # 硬约束字段
    hard_fields = (
        "text",
        "vision_understanding",
        "file_upload",
        "web_search",
        "structured_output",
    )
    for field in hard_fields:
        if getattr(required, field, False) and not getattr(provider_caps, field, False):
            return False
    return True


def capability_match_score(
    provider_caps: ProviderCapabilities,
    required: ProviderCapabilities,
) -> float:
    """计算能力匹配得分 (0.0 - 1.0)。

    硬约束未满足 = 0.0。满足所有约束后根据额外能力匹配加分。
    """
    if not matches_capabilities(provider_caps, required):
        return 0.0

    all_fields = [
        f for f in vars(ProviderCapabilities()).keys()
        if not f.startswith("_")
    ]

    required_count = sum(1 for f in all_fields if getattr(required, f, False))
    if required_count == 0:
        return 1.0  # 无特殊要求，任何 provider 都满分

    matched = sum(
        1 for f in all_fields
        if getattr(required, f, False) and getattr(provider_caps, f, False)
    )
    return matched / required_count


def filter_by_capability(
    provider_caps_list: list[tuple[str, ProviderCapabilities]],
    required: ProviderCapabilities,
) -> list[str]:
    """从 provider 能力列表中筛选出满足要求的 provider id。

    Args:
        provider_caps_list: [(provider_id, capabilities), ...]
        required: 必需的能力集合

    Returns:
        满足要求的 provider id 列表
    """
    return [
        pid for pid, caps in provider_caps_list
        if matches_capabilities(caps, required)
    ]


def text_only_capability() -> ProviderCapabilities:
    """仅需文本对话的能力要求。"""
    return ProviderCapabilities(text=True)
