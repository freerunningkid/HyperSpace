"""HealthChecker —— 服务健康检查.

异步探测各执行器健康状态:
- DeepSeek Web (chat.deepseek.com)
- DeepSeek API (api.deepseek.com)
- 智谱 GLM / GitHub GPT-4o / Agnes (始终可用)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class ServiceStatus:
    """一个执行器的健康状态."""
    name: str = ""
    available: bool = False
    latency_ms: float = 0.0
    ratelimited: bool = False
    error: str | None = None
    checked_at: float = 0.0


@dataclass
class HealthResult:
    """所有执行器的健康状态汇总."""
    deepseek_web: ServiceStatus = field(
        default_factory=lambda: ServiceStatus(name="deepseek_web", available=False)
    )
    deepseek_api: ServiceStatus = field(
        default_factory=lambda: ServiceStatus(name="deepseek_api", available=False)
    )
    zhipu: ServiceStatus = field(
        default_factory=lambda: ServiceStatus(name="zhipu", available=True)
    )
    github: ServiceStatus = field(
        default_factory=lambda: ServiceStatus(name="github", available=True)
    )
    agnes: ServiceStatus = field(
        default_factory=lambda: ServiceStatus(name="agnes", available=True)
    )


class HealthChecker:
    """健康检查器 —— 异步探测 + 缓存."""

    def __init__(
        self,
        deepseek_api_url: str = "https://api.deepseek.com/v1/models",
        cache_ttl: float = 60.0,
        probe_timeout: float = 5.0,
        deepseek_web_auth_provider=None,
    ):
        self._deepseek_api_url = deepseek_api_url
        self._cache_ttl = cache_ttl
        self._probe_timeout = probe_timeout
        self._web_auth_provider = deepseek_web_auth_provider
        self._cache: dict[str, ServiceStatus] = {}
        self._last_check: float = 0.0
        self._lock = asyncio.Lock()

    async def check_all(self) -> HealthResult:
        """检查所有执行器健康状态 (带缓存)."""
        now = time.time()
        async with self._lock:
            if now - self._last_check < self._cache_ttl and self._cache:
                return self._build_result(self._cache)

        results: dict[str, ServiceStatus] = {}

        tasks = [
            self._probe_deepseek_web(),
            self._probe_deepseek_api(),
        ]
        for coro in asyncio.as_completed(tasks):
            status = await coro
            results[status.name] = status

        results["zhipu"] = ServiceStatus(name="zhipu", available=True, checked_at=now)
        results["github"] = ServiceStatus(name="github", available=True, checked_at=now)
        results["agnes"] = ServiceStatus(name="agnes", available=True, checked_at=now)

        self._cache = results
        self._last_check = now
        return self._build_result(results)

    async def _probe_deepseek_web(self) -> ServiceStatus:
        """探测 DeepSeek Web 凭据是否可用."""
        now = time.time()
        if self._web_auth_provider:
            auth = self._web_auth_provider()
            if auth and auth.get("cookie") and (
                "d_id=" in auth["cookie"] or "ds_session_id=" in auth["cookie"]
            ):
                return ServiceStatus(
                    name="deepseek_web", available=True, latency_ms=0, checked_at=now,
                )
        return ServiceStatus(
            name="deepseek_web",
            available=False,
            error="无登录凭据 (需运行 web_auth --auto)",
            checked_at=now,
        )

    async def _probe_deepseek_api(self) -> ServiceStatus:
        """探测 DeepSeek API 是否可达."""
        start = time.time()
        now = time.time()
        try:
            async with httpx.AsyncClient(timeout=self._probe_timeout) as client:
                resp = await client.get(self._deepseek_api_url)
                latency = (time.time() - start) * 1000
                if resp.status_code in (200, 401):
                    return ServiceStatus(
                        name="deepseek_api", available=True,
                        latency_ms=round(latency, 1), checked_at=now,
                    )
                return ServiceStatus(
                    name="deepseek_api", available=False,
                    error=f"HTTP {resp.status_code}", checked_at=now,
                )
        except httpx.TimeoutException:
            return ServiceStatus(
                name="deepseek_api", available=False, error="timeout", checked_at=now,
            )
        except httpx.RequestError as e:
            return ServiceStatus(
                name="deepseek_api", available=False,
                error=f"connection: {e}", checked_at=now,
            )
        except Exception as e:
            return ServiceStatus(
                name="deepseek_api", available=False, error=str(e), checked_at=now,
            )

    @staticmethod
    def _build_result(results: dict[str, ServiceStatus]) -> HealthResult:
        return HealthResult(
            deepseek_web=results.get("deepseek_web", ServiceStatus(name="deepseek_web", available=False)),
            deepseek_api=results.get("deepseek_api", ServiceStatus(name="deepseek_api", available=False)),
            zhipu=results.get("zhipu", ServiceStatus(name="zhipu", available=True)),
            github=results.get("github", ServiceStatus(name="github", available=True)),
            agnes=results.get("agnes", ServiceStatus(name="agnes", available=True)),
        )
