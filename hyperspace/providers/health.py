"""Provider 健康评分与筛选逻辑。

健康评分供 Registry/Router 做健康感知排序。
"""

from __future__ import annotations

from .base import ProviderHealth, ProviderStatus, ProviderType


def compute_health_score(health: ProviderHealth) -> float:
    """根据 ProviderHealth 计算综合分数 (0-100)。

    已计算分数的 health 直接返回；未计算的按 status 估算。
    """
    if health.score > 0:
        return health.score

    # 按 status 估算基础分数
    status_scores = {
        ProviderStatus.AVAILABLE: 90.0,
        ProviderStatus.DEGRADED: 55.0,
        ProviderStatus.UNAVAILABLE: 15.0,
        ProviderStatus.NOT_IMPLEMENTED: 30.0,
        ProviderStatus.DISABLED: 0.0,
    }
    return status_scores.get(health.status, 0.0)


def filter_available(
    providers: list[tuple[str, ProviderHealth, ProviderType | None]],
    *,
    allow_degraded: bool = True,
    exclude_placeholder: bool = True,
    exclude_disabled: bool = True,
) -> list[str]:
    """筛选可用的 provider id。

    默认规则：
      - AVAILABLE 总是可以通过
      - DEGRADED 由 allow_degraded 控制（默认通过）
      - UNAVAILABLE/NOT_IMPLEMENTED/DISABLED 默认不通过
      - PLACEHOLDER_WEB 由 exclude_placeholder 控制（默认排除）

    Args:
        providers: [(provider_id, health, provider_type), ...]
        allow_degraded: DEGRADED 是否算可用
        exclude_placeholder: PLACEHOLDER_WEB 是否排除
        exclude_disabled: DISABLED 是否排除

    Returns:
        可用的 provider id 列表
    """
    available_statuses = {ProviderStatus.AVAILABLE}
    if allow_degraded:
        available_statuses.add(ProviderStatus.DEGRADED)

    result = []
    for pid, health, ptype in providers:
        # 占位 provider 默认排除
        if exclude_placeholder and ptype == ProviderType.PLACEHOLDER_WEB:
            continue
        # disabled
        if exclude_disabled and health.status == ProviderStatus.DISABLED:
            continue
        if health.status in available_statuses:
            result.append(pid)
    return result


def sort_by_health(
    providers: list[tuple[str, ProviderHealth]],
    *,
    descending: bool = True,
) -> list[tuple[str, ProviderHealth]]:
    """按健康分数排序 provider 列表。

    Args:
        providers: [(provider_id, health), ...]
        descending: True = 高分在前（默认）

    Returns:
        排序后的列表
    """
    return sorted(
        providers,
        key=lambda item: compute_health_score(item[1]),
        reverse=descending,
    )


def sort_candidates_by_strategy(
    candidates: list[tuple[str, ProviderHealth, ProviderType, float]],
    strategy: str = "auto",
) -> list[str]:
    """根据路由策略对候选 provider 排序。

    支持策略:
      - auto: 默认（Web 优先 → API）
      - web_first: Web 优先
      - api_first: API 优先
      - zero_cost_first / cheapest: 按 cost_tier 排序（由 Registry 预处理）
      - fastest: 按 latency_ms 升序
      - balanced: 综合健康分 + 能力分

    Args:
        candidates: [(provider_id, health, provider_type, cost_score), ...]
                   cost_score 由 Registry 预处理（FREE=0, LOW_COST=1, PAID=2, UNKNOWN=1）
        strategy: 路由策略

    Returns:
        排序后的 provider id 列表
    """
    if strategy in ("web_first", "auto"):
        # Web 优先
        web = [c for c in candidates if c[2] == ProviderType.WEB]
        api = [c for c in candidates if c[2] != ProviderType.WEB]
        web_sorted = sorted(web, key=lambda c: compute_health_score(c[1]), reverse=True)
        api_sorted = sorted(api, key=lambda c: compute_health_score(c[1]), reverse=True)
        return [c[0] for c in web_sorted + api_sorted]

    if strategy == "api_first":
        api = [c for c in candidates if c[2] == ProviderType.API]
        web = [c for c in candidates if c[2] != ProviderType.API]
        api_sorted = sorted(api, key=lambda c: compute_health_score(c[1]), reverse=True)
        web_sorted = sorted(web, key=lambda c: compute_health_score(c[1]), reverse=True)
        return [c[0] for c in api_sorted + web_sorted]

    if strategy in ("zero_cost_first", "cheapest"):
        return [
            c[0] for c in sorted(candidates, key=lambda c: (c[3], -compute_health_score(c[1])))
        ]

    if strategy == "fastest":
        return [
            c[0] for c in sorted(
                candidates,
                key=lambda c: (c[1].latency_ms if c[1].latency_ms else 999999),
            )
        ]

    if strategy == "balanced":
        return [
            c[0] for c in sorted(
                candidates,
                key=lambda c: (
                    -compute_health_score(c[1]),
                    c[3],
                    c[1].latency_ms if c[1].latency_ms else 999999,
                ),
            )
        ]

    # fallback / force_provider / 未知策略 → 保持原序
    return [c[0] for c in candidates]


def is_placeholder(ptype: ProviderType | None, status: ProviderStatus | None = None) -> bool:
    """判断是否为占位 provider。"""
    if ptype == ProviderType.PLACEHOLDER_WEB:
        return True
    if status == ProviderStatus.NOT_IMPLEMENTED:
        return True
    return False


def cost_tier_to_score(tier) -> float:
    """cost_tier 转为数值分数，供排序使用。"""
    from .base import CostTier
    return {
        CostTier.FREE: 0,
        CostTier.LOW_COST: 1,
        CostTier.UNKNOWN: 1.5,
        CostTier.PAID: 2,
    }.get(tier, 1.0)
