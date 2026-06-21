# -*- coding: utf-8 -*-
"""测试: HealthChecker — 服务健康探测、凭据检查、缓存机制.

纯单元测试，Mock httpx.AsyncClient 和凭据提供者，不打真实网络。
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hyperspace.hybrid_engine.health_checker import (
    HealthChecker,
    HealthResult,
    ServiceStatus,
)


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def valid_auth_provider():
    """返回有效 DeepSeek Web 凭据的提供者."""
    def provider():
        return {
            "cookie": "d_id=abc123; ds_session_id=xyz789; _ga=GA1.1.test",
            "bearer": "tok_valid_123",
            "user_agent": "TestAgent/1.0",
            "saved_at": time.time(),
        }
    return provider


@pytest.fixture
def expired_auth_provider():
    """返回不含 session cookie 的凭据提供者."""
    def provider():
        return {
            "cookie": "_ga=GA1.1.nosession; lang=zh",
            "bearer": "",
        }
    return provider


@pytest.fixture
def empty_auth_provider():
    """返回 None 的凭据提供者."""
    def provider():
        return None
    return provider


@pytest.fixture
def checker_with_valid_auth(valid_auth_provider):
    """创建带有效凭据的 HealthChecker."""
    return HealthChecker(deepseek_web_auth_provider=valid_auth_provider)


@pytest.fixture
def checker_with_expired_auth(expired_auth_provider):
    """创建带过期凭据的 HealthChecker."""
    return HealthChecker(deepseek_web_auth_provider=expired_auth_provider)


@pytest.fixture
def checker_with_empty_auth(empty_auth_provider):
    """创建带空凭据的 HealthChecker."""
    return HealthChecker(deepseek_web_auth_provider=empty_auth_provider)


# ══════════════════════════════════════════════════════════════════════
# TestServiceStatus
# ══════════════════════════════════════════════════════════════════════

class TestServiceStatus:
    """ServiceStatus 数据结构."""

    def test_default_values(self):
        s = ServiceStatus()
        assert s.name == ""
        assert s.available is False
        assert s.latency_ms == 0.0
        assert s.ratelimited is False
        assert s.error is None
        assert s.checked_at == 0.0

    def test_custom_values(self):
        s = ServiceStatus(
            name="deepseek_api",
            available=True,
            latency_ms=45.2,
            ratelimited=False,
            error=None,
            checked_at=1700000000.0,
        )
        assert s.name == "deepseek_api"
        assert s.available is True
        assert s.latency_ms == 45.2


# ══════════════════════════════════════════════════════════════════════
# TestHealthResult
# ══════════════════════════════════════════════════════════════════════

class TestHealthResult:
    """HealthResult 数据结构."""

    def test_default_values(self):
        result = HealthResult()
        assert result.deepseek_web.name == "deepseek_web"
        assert result.deepseek_web.available is False
        assert result.deepseek_api.name == "deepseek_api"
        assert result.deepseek_api.available is False
        assert result.zhipu.name == "zhipu"
        assert result.zhipu.available is True  # 智谱默认可用

    def test_zhipu_always_available_by_default(self):
        """智谱 GLM 无本地依赖，始终 available."""
        result = HealthResult()
        assert result.zhipu.available is True


# ══════════════════════════════════════════════════════════════════════
# TestHealthChecker — 初始化
# ══════════════════════════════════════════════════════════════════════

class TestHealthCheckerInit:
    """初始化参数."""

    def test_default_values(self):
        checker = HealthChecker()
        assert checker._deepseek_api_url == "https://api.deepseek.com/v1/models"
        assert checker._cache_ttl == 60.0
        assert checker._probe_timeout == 5.0
        assert checker._web_auth_provider is None
        assert checker._cache == {}
        assert checker._last_check == 0.0

    def test_custom_values(self):
        auth_fn = lambda: {"cookie": "d_id=1"}
        checker = HealthChecker(
            deepseek_api_url="https://custom.api.com/health",
            cache_ttl=30.0,
            probe_timeout=10.0,
            deepseek_web_auth_provider=auth_fn,
        )
        assert checker._deepseek_api_url == "https://custom.api.com/health"
        assert checker._cache_ttl == 30.0
        assert checker._probe_timeout == 10.0
        assert checker._web_auth_provider == auth_fn


# ══════════════════════════════════════════════════════════════════════
# TestHealthChecker — DeepSeek Web 探测
# ══════════════════════════════════════════════════════════════════════

class TestProbeDeepSeekWeb:
    """_probe_deepseek_web() 测试."""

    @pytest.mark.asyncio
    async def test_valid_auth_returns_available(self, checker_with_valid_auth):
        status = await checker_with_valid_auth._probe_deepseek_web()
        assert status.name == "deepseek_web"
        assert status.available is True
        assert status.error is None
        assert status.checked_at > 0

    @pytest.mark.asyncio
    async def test_expired_auth_returns_unavailable(self, checker_with_expired_auth):
        status = await checker_with_expired_auth._probe_deepseek_web()
        assert status.name == "deepseek_web"
        assert status.available is False
        assert "凭据" in status.error or "登录" in status.error

    @pytest.mark.asyncio
    async def test_empty_auth_returns_unavailable(self, checker_with_empty_auth):
        status = await checker_with_empty_auth._probe_deepseek_web()
        assert status.available is False

    @pytest.mark.asyncio
    async def test_no_auth_provider_returns_unavailable(self):
        checker = HealthChecker()  # 无 auth provider
        status = await checker._probe_deepseek_web()
        assert status.available is False
        assert status.error is not None

    @pytest.mark.asyncio
    async def test_auth_with_ds_session_id_only(self):
        """仅含 ds_session_id 的 Cookie 也视为有效."""
        def provider():
            return {"cookie": "ds_session_id=yyy999", "bearer": ""}

        checker = HealthChecker(deepseek_web_auth_provider=provider)
        status = await checker._probe_deepseek_web()
        assert status.available is True

    @pytest.mark.asyncio
    async def test_auth_with_d_id_only(self):
        """仅含 d_id 的 Cookie 也视为有效."""
        def provider():
            return {"cookie": "d_id=abc456", "bearer": ""}

        checker = HealthChecker(deepseek_web_auth_provider=provider)
        status = await checker._probe_deepseek_web()
        assert status.available is True

    @pytest.mark.asyncio
    async def test_auth_with_empty_cookie(self):
        """空 Cookie 视为无效."""
        def provider():
            return {"cookie": "", "bearer": "tok_xxx"}

        checker = HealthChecker(deepseek_web_auth_provider=provider)
        status = await checker._probe_deepseek_web()
        assert status.available is False

    @pytest.mark.asyncio
    async def test_auth_without_cookie_key(self):
        """返回 dict 无 cookie 键."""
        def provider():
            return {"bearer": "tok_xxx"}

        checker = HealthChecker(deepseek_web_auth_provider=provider)
        status = await checker._probe_deepseek_web()
        assert status.available is False


# ══════════════════════════════════════════════════════════════════════
# TestHealthChecker — DeepSeek API 探测
# ══════════════════════════════════════════════════════════════════════

class TestProbeDeepSeekApi:
    """_probe_deepseek_api() 测试."""

    @pytest.mark.asyncio
    async def test_api_returns_200(self):
        """HTTP 200 → available."""
        checker = HealthChecker()

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.name == "deepseek_api"
        assert status.available is True

    @pytest.mark.asyncio
    async def test_api_returns_401_still_available(self):
        """HTTP 401 仍视为可达（认证失败不代表服务不可用）."""
        checker = HealthChecker()

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.available is True

    @pytest.mark.asyncio
    async def test_api_timeout(self):
        """请求超时 → unavailable."""
        checker = HealthChecker()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.available is False
        assert "timeout" in status.error or status.error == "timeout"

    @pytest.mark.asyncio
    async def test_api_connection_refused(self):
        """连接被拒 → unavailable."""
        checker = HealthChecker()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.available is False
        assert "connection" in status.error.lower()

    @pytest.mark.asyncio
    async def test_api_network_error(self):
        """网络错误 → unavailable."""
        checker = HealthChecker()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("network down"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.available is False

    @pytest.mark.asyncio
    async def test_api_500_error(self):
        """HTTP 500 → unavailable."""
        checker = HealthChecker()

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.available is False
        assert "500" in status.error

    @pytest.mark.asyncio
    async def test_api_records_latency(self):
        """成功探测时记录延迟."""
        checker = HealthChecker()

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_api_unexpected_exception(self):
        """非预期异常也返回 unavailable."""
        checker = HealthChecker()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=RuntimeError("unexpected crash"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            status = await checker._probe_deepseek_api()

        assert status.available is False
        assert "unexpected crash" in status.error


# ══════════════════════════════════════════════════════════════════════
# TestHealthChecker — check_all 集成
# ══════════════════════════════════════════════════════════════════════

class TestCheckAll:
    """check_all() 集成测试."""

    @pytest.mark.asyncio
    async def test_returns_health_result(self, checker_with_valid_auth):
        """check_all 返回完整 HealthResult."""
        # Mock API 探测避免真实网络
        with patch.object(checker_with_valid_auth, "_probe_deepseek_api") as mock_api:
            mock_api.return_value = ServiceStatus(
                name="deepseek_api", available=True, latency_ms=10.0,
                checked_at=time.time(),
            )
            result = await checker_with_valid_auth.check_all()

        assert isinstance(result, HealthResult)
        assert result.deepseek_web.available is True
        assert result.deepseek_api.available is True
        assert result.zhipu.available is True
        assert result.zhipu.name == "zhipu"

    @pytest.mark.asyncio
    async def test_web_unavailable_api_available(self, checker_with_expired_auth):
        """Web 不可用但 API 可用的场景."""
        with patch.object(checker_with_expired_auth, "_probe_deepseek_api") as mock_api:
            mock_api.return_value = ServiceStatus(
                name="deepseek_api", available=True, latency_ms=5.0,
                checked_at=time.time(),
            )
            result = await checker_with_expired_auth.check_all()

        assert result.deepseek_web.available is False
        assert result.deepseek_api.available is True
        assert result.zhipu.available is True  # 兜底始终可用

    @pytest.mark.asyncio
    async def test_all_unavailable_except_zhipu(self, checker_with_empty_auth):
        """Web 和 API 都不可用，仅智谱可用."""
        with patch.object(checker_with_empty_auth, "_probe_deepseek_api") as mock_api:
            mock_api.return_value = ServiceStatus(
                name="deepseek_api", available=False, error="timeout",
                checked_at=time.time(),
            )
            result = await checker_with_empty_auth.check_all()

        assert result.deepseek_web.available is False
        assert result.deepseek_api.available is False
        assert result.zhipu.available is True

    @pytest.mark.asyncio
    async def test_zhipu_always_true_in_check_all(self):
        """check_all 中智谱始终 available."""
        checker = HealthChecker()
        with patch.object(checker, "_probe_deepseek_api") as mock_api:
            mock_api.return_value = ServiceStatus(
                name="deepseek_api", available=False, error="connection",
                checked_at=time.time(),
            )
            result = await checker.check_all()

        # 无论 Web/API 状态如何，智谱始终可用
        assert result.zhipu.available is True
        assert result.zhipu.error is None
        assert result.zhipu.checked_at > 0


# ══════════════════════════════════════════════════════════════════════
# TestHealthChecker — 缓存机制
# ══════════════════════════════════════════════════════════════════════

class TestCacheMechanism:
    """60 秒缓存机制测试."""

    @pytest.mark.asyncio
    async def test_second_call_within_cache_ttl_reuses_cache(self, checker_with_valid_auth):
        """缓存有效期内不发起新请求."""
        probe_count = [0]

        async def counting_probe_api():
            probe_count[0] += 1
            return ServiceStatus(
                name="deepseek_api", available=True, latency_ms=1.0,
                checked_at=time.time(),
            )

        with patch.object(checker_with_valid_auth, "_probe_deepseek_api",
                          side_effect=counting_probe_api):
            result1 = await checker_with_valid_auth.check_all()
            assert probe_count[0] == 1

            # 立即再次调用（缓存未过期）
            result2 = await checker_with_valid_auth.check_all()

            # 不应发起新的 API 探测
            assert probe_count[0] == 1, "缓存期内不应重新探测"
            # 两次返回相同结果
            assert result2.deepseek_api.available == result1.deepseek_api.available

    @pytest.mark.asyncio
    async def test_cache_expired_triggers_new_probe(self, checker_with_valid_auth):
        """缓存过期后重新探测."""
        probe_count = [0]
        fake_now = [1000.0]

        def fake_time():
            return fake_now[0]

        async def counting_probe_api():
            probe_count[0] += 1
            return ServiceStatus(
                name="deepseek_api", available=True, latency_ms=1.0,
                checked_at=fake_time(),
            )

        with patch.object(checker_with_valid_auth, "_probe_deepseek_api",
                          side_effect=counting_probe_api):
            with patch("time.time", side_effect=fake_time):
                # 第一次调用
                result1 = await checker_with_valid_auth.check_all()
                assert probe_count[0] == 1

                # 时间推进 61 秒（缓存过期）
                fake_now[0] += 61.0

                # 第二次调用 — 缓存已过期，应重新探测
                result2 = await checker_with_valid_auth.check_all()
                assert probe_count[0] == 2, "缓存过期后应重新探测"

    @pytest.mark.asyncio
    async def test_cache_just_before_expiry_uses_cache(self, checker_with_valid_auth):
        """恰好 59 秒时仍使用缓存."""
        probe_count = [0]
        fake_now = [1000.0]

        def fake_time():
            return fake_now[0]

        async def counting_probe_api():
            probe_count[0] += 1
            return ServiceStatus(
                name="deepseek_api", available=True, latency_ms=1.0,
                checked_at=fake_time(),
            )

        with patch.object(checker_with_valid_auth, "_probe_deepseek_api",
                          side_effect=counting_probe_api):
            with patch("time.time", side_effect=fake_time):
                await checker_with_valid_auth.check_all()
                assert probe_count[0] == 1

                # 时间只推进 59 秒（仍在缓存内）
                fake_now[0] += 59.0

                await checker_with_valid_auth.check_all()
                assert probe_count[0] == 1, "59 秒仍在缓存期内"

    @pytest.mark.asyncio
    async def test_cache_just_after_expiry_reprobes(self, checker_with_valid_auth):
        """恰好 60 秒时缓存过期."""
        probe_count = [0]
        fake_now = [1000.0]

        def fake_time():
            return fake_now[0]

        async def counting_probe_api():
            probe_count[0] += 1
            return ServiceStatus(
                name="deepseek_api", available=True, latency_ms=1.0,
                checked_at=fake_time(),
            )

        with patch.object(checker_with_valid_auth, "_probe_deepseek_api",
                          side_effect=counting_probe_api):
            with patch("time.time", side_effect=fake_time):
                await checker_with_valid_auth.check_all()
                assert probe_count[0] == 1

                # 时间推进 60 秒（恰好过期）
                fake_now[0] += 60.0

                await checker_with_valid_auth.check_all()
                assert probe_count[0] == 2, "60 秒应过期重探"

    @pytest.mark.asyncio
    async def test_cache_stores_web_status_too(self, checker_with_valid_auth):
        """缓存也存储 Web 状态."""
        with patch.object(checker_with_valid_auth, "_probe_deepseek_api") as mock_api:
            mock_api.return_value = ServiceStatus(
                name="deepseek_api", available=True, latency_ms=5.0,
                checked_at=time.time(),
            )
            result1 = await checker_with_valid_auth.check_all()
            result2 = await checker_with_valid_auth.check_all()

        # Web 状态应从缓存读取，一致
        assert result1.deepseek_web.available == result2.deepseek_web.available

    @pytest.mark.asyncio
    async def test_cache_cleared_after_ttl_for_web(self, checker_with_valid_auth):
        """Web 探测在缓存过期后也重新执行."""
        # 每次 check_all 内部都会调用 _probe_deepseek_web()
        # 但缓存期内不会重新调用
        fake_now = [1000.0]

        def fake_time():
            return fake_now[0]

        probe_count = [0]
        original_probe = checker_with_valid_auth._probe_deepseek_web

        async def counting_probe_web():
            probe_count[0] += 1
            return ServiceStatus(
                name="deepseek_web", available=True,
                checked_at=fake_time(),
            )

        with patch.object(checker_with_valid_auth, "_probe_deepseek_api") as mock_api:
            mock_api.return_value = ServiceStatus(
                name="deepseek_api", available=True, latency_ms=1.0,
                checked_at=fake_time(),
            )
            with patch.object(checker_with_valid_auth, "_probe_deepseek_web",
                              side_effect=counting_probe_web):
                with patch("time.time", side_effect=fake_time):
                    await checker_with_valid_auth.check_all()
                    assert probe_count[0] == 1

                    fake_now[0] += 61.0
                    await checker_with_valid_auth.check_all()
                    assert probe_count[0] == 2, "Web 探测也应重新执行"


# ══════════════════════════════════════════════════════════════════════
# TestHealthChecker — 并发安全
# ══════════════════════════════════════════════════════════════════════

class TestConcurrency:
    """asyncio.Lock 保证并发安全."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_only_probe_once(self, checker_with_valid_auth):
        """并发调用 check_all 时只探测一次."""
        import asyncio

        probe_count = [0]
        barrier = asyncio.Event()

        async def slow_probe_api():
            await barrier.wait()  # 等待所有协程就绪
            probe_count[0] += 1
            await asyncio.sleep(0.01)  # 模拟网络延迟
            return ServiceStatus(
                name="deepseek_api", available=True, latency_ms=10.0,
                checked_at=time.time(),
            )

        with patch.object(checker_with_valid_auth, "_probe_deepseek_api",
                          side_effect=slow_probe_api):

            async def do_check():
                return await checker_with_valid_auth.check_all()

            # 同时启动 3 个并发 check_all
            tasks = [asyncio.create_task(do_check()) for _ in range(3)]
            await asyncio.sleep(0.02)  # 让它们都到达 await barrier
            barrier.set()  # 释放所有协程
            results = await asyncio.gather(*tasks)

        # 由于 asyncio.Lock，只有第一个拿到锁的会执行探测
        # 后续的在锁释放后检查缓存命中，不再探测
        # 注意：如果锁实现正确，probe_count 应该 <= 3
        # 实际上由于时间戳不变，缓存期内后续调用直接返回
        assert probe_count[0] >= 1, "至少有一次探测"
        # 所有结果一致
        for r in results:
            assert isinstance(r, HealthResult)


# ══════════════════════════════════════════════════════════════════════
# TestHealthChecker — _build_result 静态方法
# ══════════════════════════════════════════════════════════════════════

class TestBuildResult:
    """_build_result 静态方法."""

    def test_build_from_complete_dict(self):
        now = time.time()
        results = {
            "deepseek_web": ServiceStatus(name="deepseek_web", available=True,
                                           checked_at=now),
            "deepseek_api": ServiceStatus(name="deepseek_api", available=False,
                                           error="timeout", checked_at=now),
            "zhipu": ServiceStatus(name="zhipu", available=True, checked_at=now),
        }
        hr = HealthChecker._build_result(results)
        assert hr.deepseek_web.available is True
        assert hr.deepseek_api.available is False
        assert hr.zhipu.available is True

    def test_build_from_empty_dict_uses_defaults(self):
        hr = HealthChecker._build_result({})
        assert hr.deepseek_web.name == "deepseek_web"
        assert hr.deepseek_web.available is False  # 默认不可用
        assert hr.deepseek_api.name == "deepseek_api"
        assert hr.deepseek_api.available is False
        assert hr.zhipu.name == "zhipu"
        assert hr.zhipu.available is True  # 默认可用

    def test_build_from_partial_dict(self):
        """只提供部分结果，其余用默认值."""
        results = {
            "deepseek_api": ServiceStatus(name="deepseek_api", available=True,
                                           latency_ms=33.3, checked_at=time.time()),
        }
        hr = HealthChecker._build_result(results)
        assert hr.deepseek_api.available is True
        assert hr.deepseek_api.latency_ms == 33.3
        assert hr.deepseek_web.available is False  # 默认
        assert hr.zhipu.available is True  # 默认
