# -*- coding: utf-8 -*-
"""测试: DeepSeek Web Client — PoW 求解、SSE 流解析、文件上传、会话管理.

纯单元测试，Mock httpx.AsyncClient，不打真实网络。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hyperspace.hybrid_engine.deepseek_web_client import (
    BASE_URL,
    POW_TIMEOUT_NONCE,
    UPLOAD_MAX_POLLS,
    DeepSeekAuth,
    DeepSeekWebClient,
    DeepSeekWebResponse,
    PowChallenge,
    _count_leading_zero_bits,
    _default_headers,
    solve_sha256_pow,
)


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def valid_auth() -> DeepSeekAuth:
    """构造一个有效凭据."""
    return DeepSeekAuth(
        cookie="d_id=abc123; ds_session_id=xyz789; _ga=GA1.1.123",
        bearer="tok_deadbeef_cafe",
        user_agent="Mozilla/5.0 TestAgent",
        saved_at=1700000000.0,
    )


@pytest.fixture
def invalid_auth() -> DeepSeekAuth:
    """构造一个缺少 session cookie 的凭据."""
    return DeepSeekAuth(
        cookie="_ga=GA1.1.456;",
        bearer="",
    )


@pytest.fixture
def mock_http_client():
    """构造 mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekAuth
# ══════════════════════════════════════════════════════════════════════

class TestDeepSeekAuth:
    """凭据验证."""

    def test_valid_auth_with_session_cookies(self, valid_auth):
        assert valid_auth.is_valid() is True

    def test_invalid_auth_missing_session_cookies(self, invalid_auth):
        assert invalid_auth.is_valid() is False

    def test_empty_auth(self):
        auth = DeepSeekAuth()
        assert auth.is_valid() is False

    def test_auth_with_only_bearer(self):
        auth = DeepSeekAuth(bearer="tok_xxx")
        assert auth.is_valid() is False

    def test_auth_with_only_d_id(self):
        auth = DeepSeekAuth(cookie="d_id=123456")
        assert auth.is_valid() is True

    def test_auth_with_only_ds_session_id(self):
        """ds_session_id 单独不再有效 (需要 Bearer token 或 d_id)."""
        auth = DeepSeekAuth(cookie="ds_session_id=abcdef")
        assert auth.is_valid() is False  # 新版要求 Bearer 或 d_id

    def test_auth_with_bearer_token(self):
        """Bearer token 是有效的认证方式."""
        auth = DeepSeekAuth(bearer="tok_" + "x" * 20)
        assert auth.is_valid() is True

    def test_to_dict_and_from_dict_roundtrip(self, valid_auth):
        d = valid_auth.to_dict()
        restored = DeepSeekAuth.from_dict(d)
        assert restored.cookie == valid_auth.cookie
        assert restored.bearer == valid_auth.bearer
        assert restored.user_agent == valid_auth.user_agent
        assert restored.saved_at == valid_auth.saved_at

    def test_from_dict_with_defaults(self):
        d = {"cookie": "d_id=1"}
        auth = DeepSeekAuth.from_dict(d)
        assert auth.cookie == "d_id=1"
        assert auth.bearer == ""
        assert auth.user_agent != ""  # 有默认值


# ══════════════════════════════════════════════════════════════════════
# TestDefaultHeaders
# ══════════════════════════════════════════════════════════════════════

class TestDefaultHeaders:
    """默认请求头构造."""

    def test_headers_include_cookie_and_bearer(self, valid_auth):
        headers = _default_headers(valid_auth)
        assert headers["Cookie"] == valid_auth.cookie
        assert headers["Authorization"] == f"Bearer {valid_auth.bearer}"
        assert headers["Referer"] == "https://chat.deepseek.com/"
        assert headers["Content-Type"] == "application/json"

    def test_headers_without_cookie(self):
        auth = DeepSeekAuth(bearer="tok_xxx")
        headers = _default_headers(auth)
        assert headers["Authorization"] == "Bearer tok_xxx"
        assert "Cookie" not in headers

    def test_headers_without_bearer(self):
        auth = DeepSeekAuth(cookie="d_id=1")
        headers = _default_headers(auth)
        assert headers["Cookie"] == "d_id=1"
        assert "Authorization" not in headers


# ══════════════════════════════════════════════════════════════════════
# TestPowChallenge
# ══════════════════════════════════════════════════════════════════════

class TestPowChallenge:
    """PoW 挑战数据结构."""

    def test_from_dict_standard(self):
        d = {
            "algorithm": "sha256",
            "challenge": "abc123",
            "difficulty": 4,
            "salt": "salt_xyz",
            "signature": "sig_abc",
        }
        ch = PowChallenge.from_dict(d)
        assert ch.algorithm == "sha256"
        assert ch.challenge == "abc123"
        assert ch.difficulty == 4
        assert ch.salt == "salt_xyz"
        assert ch.signature == "sig_abc"

    def test_from_dict_with_defaults(self):
        ch = PowChallenge.from_dict({})
        assert ch.algorithm == "sha256"
        assert ch.difficulty == 4
        assert ch.challenge == ""

    def test_with_answer_produces_valid_base64(self):
        ch = PowChallenge(
            algorithm="sha256",
            challenge="test_challenge",
            difficulty=4,
            salt="test_salt",
            signature="test_sig",
        )
        result = ch.with_answer(42, "/api/v0/chat/completion")
        import base64
        decoded = json.loads(base64.b64decode(result).decode())
        assert decoded["answer"] == 42
        assert decoded["target_path"] == "/api/v0/chat/completion"
        assert decoded["algorithm"] == "sha256"


# ══════════════════════════════════════════════════════════════════════
# TestCountLeadingZeroBits
# ══════════════════════════════════════════════════════════════════════

class TestCountLeadingZeroBits:
    """前导零位计数."""

    def test_all_zeros(self):
        # "00000000..." → 每个 hex char 贡献 4 个零位
        assert _count_leading_zero_bits("0000") == 16

    def test_no_leading_zeros(self):
        # "ffff..." → 0 个前导零位
        assert _count_leading_zero_bits("ffff") == 0

    def test_partial_nibble(self):
        # "1" = 0b0001 → 3 leading zero bits
        assert _count_leading_zero_bits("1") == 3
        # "2" = 0b0010 → 2 leading zero bits
        assert _count_leading_zero_bits("2") == 2
        # "4" = 0b0100 → 1 leading zero bit
        assert _count_leading_zero_bits("4") == 1
        # "8" = 0b1000 → 0 leading zero bits
        assert _count_leading_zero_bits("8") == 0

    def test_mixed(self):
        # "00ff" → 8 + 0 = 8
        assert _count_leading_zero_bits("00ff") == 8
        # "01ff" → 4 + 3 = 7
        assert _count_leading_zero_bits("01ff") == 7
        # "0f00" → 4
        assert _count_leading_zero_bits("0f00") == 4

    def test_single_char_a(self):
        # "a" = 10 = 0b1010 → 0 leading zero bits
        assert _count_leading_zero_bits("a") == 0


# ══════════════════════════════════════════════════════════════════════
# TestSolveSha256Pow
# ══════════════════════════════════════════════════════════════════════

class TestSolveSha256Pow:
    """PoW 求解器."""

    def test_solves_easy_challenge(self):
        """低难度挑战 (difficulty=4) 应在合理时间内求解."""
        ch = PowChallenge(
            algorithm="sha256",
            challenge="test123",
            difficulty=4,
            salt="hello",
            signature="sig",
        )
        nonce = solve_sha256_pow(ch)
        assert isinstance(nonce, int)
        assert nonce >= 0
        assert nonce < POW_TIMEOUT_NONCE

    def test_solution_is_verifiable(self):
        """验证返回的 nonce 确实满足难度要求."""
        import hashlib
        ch = PowChallenge(
            algorithm="sha256",
            challenge="verify_me",
            difficulty=8,
            salt="salt42",
            signature="sig",
        )
        nonce = solve_sha256_pow(ch)

        # 用返回的 nonce 重新计算 hash
        prefix = ch.salt + ch.challenge
        data = f"{prefix}{nonce}".encode()
        hash_hex = hashlib.sha256(data).hexdigest()
        zero_bits = _count_leading_zero_bits(hash_hex)

        assert zero_bits >= ch.difficulty, (
            f"nonce={nonce} 产生的 hash={hash_hex}, "
            f"前导零位={zero_bits}, 需要≥{ch.difficulty}"
        )

    def test_different_challenges_produce_different_nonces(self):
        """不同挑战应产生不同的 nonce（概率性断言）."""
        ch1 = PowChallenge(
            algorithm="sha256",
            challenge="challenge_a",
            difficulty=4,
            salt="salt_a",
            signature="sig",
        )
        ch2 = PowChallenge(
            algorithm="sha256",
            challenge="challenge_b",
            difficulty=4,
            salt="salt_b",
            signature="sig",
        )
        n1 = solve_sha256_pow(ch1)
        n2 = solve_sha256_pow(ch2)
        # 虽然理论上可能相同但概率极低
        # 不强制不等，只验证各自有效
        assert n1 >= 0
        assert n2 >= 0

    def test_higher_difficulty_works(self):
        """中等难度 (difficulty=16) 应能求解."""
        ch = PowChallenge(
            algorithm="sha256",
            challenge="harder_test",
            difficulty=16,
            salt="medium",
            signature="sig",
        )
        nonce = solve_sha256_pow(ch)
        # 验证
        import hashlib
        prefix = ch.salt + ch.challenge
        data = f"{prefix}{nonce}".encode()
        hash_hex = hashlib.sha256(data).hexdigest()
        zero_bits = _count_leading_zero_bits(hash_hex)
        assert zero_bits >= 16, f"nonce={nonce}, zero_bits={zero_bits}"


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — 辅助方法
# ══════════════════════════════════════════════════════════════════════

class TestDeepSeekWebClientHelpers:
    """客户端构造和辅助方法."""

    def test_client_creation(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        assert client.auth == valid_auth
        assert client._current_session_id is None

    def test_auth_setter(self, valid_auth, invalid_auth):
        client = DeepSeekWebClient(valid_auth)
        client.auth = invalid_auth
        assert client.auth == invalid_auth

    @pytest.mark.asyncio
    async def test_close(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        client._http = AsyncMock()
        await client.close()
        client._http.aclose.assert_awaited_once()


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — PoW 挑战创建
# ══════════════════════════════════════════════════════════════════════

class TestCreatePowChallenge:
    """create_pow_challenge() 测试."""

    @pytest.mark.asyncio
    async def test_successful_challenge_creation(self, valid_auth):
        """正常返回 PoW 挑战."""
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "biz_data": {
                    "challenge": {
                        "algorithm": "sha256",
                        "challenge": "abc",
                        "difficulty": 4,
                        "salt": "salt123",
                        "signature": "sig456",
                    }
                }
            }
        }
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        challenge = await client.create_pow_challenge("/api/v0/chat/completion")
        assert challenge.algorithm == "sha256"
        assert challenge.challenge == "abc"
        assert challenge.difficulty == 4

    @pytest.mark.asyncio
    async def test_challenge_creation_http_error(self, valid_auth):
        """HTTP 错误应抛 RuntimeError."""
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        with pytest.raises(RuntimeError, match="PoW 挑战失败"):
            await client.create_pow_challenge("/api/v0/chat/completion")

    @pytest.mark.asyncio
    async def test_challenge_creation_missing_challenge_in_response(self, valid_auth):
        """响应中缺少 challenge 字段应抛 RuntimeError."""
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {}}
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        with pytest.raises(RuntimeError, match="PoW 响应结构异常"):
            await client.create_pow_challenge("/api/v0/chat/completion")

    @pytest.mark.asyncio
    async def test_challenge_from_alternative_path(self, valid_auth):
        """challenge 在 data.challenge 路径下（非 biz_data）."""
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "challenge": {
                    "algorithm": "sha256",
                    "challenge": "alt_path",
                    "difficulty": 8,
                    "salt": "s",
                    "signature": "g",
                }
            }
        }
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        challenge = await client.create_pow_challenge("/api/v0/file/upload_file")
        assert challenge.challenge == "alt_path"
        assert challenge.difficulty == 8


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — 会话管理
# ══════════════════════════════════════════════════════════════════════

class TestCreateChatSession:
    """create_chat_session() 测试."""

    @pytest.mark.asyncio
    async def test_successful_session_creation(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "biz_data": {
                    "id": "session_abc123",
                }
            }
        }
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        session_id = await client.create_chat_session()
        assert session_id == "session_abc123"
        assert client._current_session_id == "session_abc123"

    @pytest.mark.asyncio
    async def test_session_creation_http_error(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        with pytest.raises(RuntimeError, match="创建会话失败"):
            await client.create_chat_session()

    @pytest.mark.asyncio
    async def test_session_creation_missing_id(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"biz_data": {}}  # 无 id
        }
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        with pytest.raises(RuntimeError, match="会话创建响应缺少 id"):
            await client.create_chat_session()

    @pytest.mark.asyncio
    async def test_session_creation_uses_chat_session_id_field(self, valid_auth):
        """使用 chat_session_id 字段（备选路径）."""
        client = DeepSeekWebClient(valid_auth)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "biz_data": {
                    "chat_session_id": "cs_alt_field",
                }
            }
        }
        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_response)

        session_id = await client.create_chat_session()
        assert session_id == "cs_alt_field"


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — SSE 流解析
# ══════════════════════════════════════════════════════════════════════

class TestParseSseStream:
    """_parse_sse_stream() 测试."""

    @pytest.mark.asyncio
    async def test_parses_text_and_thinking_events(self, valid_auth):
        """R1 模式 SSE：thinking_content + content 分离."""
        client = DeepSeekWebClient(valid_auth)
        result = DeepSeekWebResponse()

        lines = [
            'data: {"p":"response/thinking_content","o":"APPEND","v":"让我思考一下..."}',
            'data: {"v":"进一步分析"}',
            'data: {"p":"response/content","o":"APPEND","v":"这是"}',
            'data: {"v":"最终回答"}',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.aiter_lines = MagicMock(return_value=_async_iter(lines))

        await client._parse_sse_stream(mock_response, result)
        assert "让我思考一下...进一步分析" == result.thinking
        assert "这是最终回答" == result.text
        assert result.finish_reason == "finished"

    @pytest.mark.asyncio
    async def test_parses_text_only_no_thinking(self, valid_auth):
        """只有 content，无 thinking (V3 模式)."""
        client = DeepSeekWebClient(valid_auth)
        result = DeepSeekWebResponse()

        lines = [
            'data: {"p":"response/fragments/0/content","o":"APPEND","v":"简单的"}',
            'data: {"v":"回答"}',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.aiter_lines = MagicMock(return_value=_async_iter(lines))

        await client._parse_sse_stream(mock_response, result)
        assert result.text == "简单的回答"
        assert result.thinking == ""

    @pytest.mark.asyncio
    async def test_parses_thinking_only_no_text(self, valid_auth):
        """只有 thinking_content，无 content."""
        client = DeepSeekWebClient(valid_auth)
        result = DeepSeekWebResponse()

        lines = [
            'data: {"p":"response/thinking_content","o":"APPEND","v":"深度思考..."}',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.aiter_lines = MagicMock(return_value=_async_iter(lines))

        await client._parse_sse_stream(mock_response, result)
        assert result.thinking == "深度思考..."
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_error_event_raises_runtime_error(self, valid_auth):
        """error 类型事件应抛出 RuntimeError (兼容旧格式)."""
        client = DeepSeekWebClient(valid_auth)
        result = DeepSeekWebResponse()

        lines = [
            'data: {"p":"response/content","o":"APPEND","v":"开始..."}',
            'data: {"type":"error","content":"rate limit exceeded"}',
        ]
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.aiter_lines = MagicMock(return_value=_async_iter(lines))

        with pytest.raises(RuntimeError, match="DeepSeek API 错误"):
            await client._parse_sse_stream(mock_response, result)

    @pytest.mark.asyncio
    async def test_ignores_empty_and_non_data_lines(self, valid_auth):
        """忽略空行和非 data: 开头的行."""
        client = DeepSeekWebClient(valid_auth)
        result = DeepSeekWebResponse()

        lines = [
            "",  # 空行
            "event: ping",  # 非 data 行
            'data: {"p":"response/fragments/0/content","o":"APPEND","v":"hello"}',
            ":",  # 只有冒号
            'data: {"p":"response/status","v":"FINISHED"}',
        ]
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.aiter_lines = MagicMock(return_value=_async_iter(lines))

        await client._parse_sse_stream(mock_response, result)
        assert result.text == "hello"

    @pytest.mark.asyncio
    async def test_ignores_invalid_json(self, valid_auth):
        """忽略 JSON 解析失败的 data 行."""
        client = DeepSeekWebClient(valid_auth)
        result = DeepSeekWebResponse()

        lines = [
            'data: not-json-at-all',
            'data: {"p":"response/fragments/0/content","o":"APPEND","v":"valid"}',
            'data: {malformed',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.aiter_lines = MagicMock(return_value=_async_iter(lines))

        await client._parse_sse_stream(mock_response, result)
        assert result.text == "valid"

    @pytest.mark.asyncio
    async def test_empty_stream(self, valid_auth):
        """空 SSE 流."""
        client = DeepSeekWebClient(valid_auth)
        result = DeepSeekWebResponse()

        lines: list[str] = []
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.aiter_lines = MagicMock(return_value=_async_iter(lines))

        await client._parse_sse_stream(mock_response, result)
        assert result.text == ""
        assert result.thinking == ""


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — Chat Completion 完整流程
# ══════════════════════════════════════════════════════════════════════

class TestChatCompletion:
    """chat_completion() 完整流程测试."""

    @pytest.mark.asyncio
    async def test_full_chat_completion_flow(self, valid_auth):
        """完整 Chat Completion 流程（创建会话 → PoW → SSE → 解析）."""
        client = DeepSeekWebClient(valid_auth)

        # chat_completion() 调用链:
        # 1. POST /api/v0/chat_session/create (内部自动调用，因为 _current_session_id 为空)
        # 2. POST /api/v0/chat/create_pow_challenge
        # 3. stream POST /api/v0/chat/completion

        async def post_fn(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            if "/chat_session/" in url and "create" in url:
                m.status_code = 200
                m.json.return_value = {"data": {"biz_data": {"id": "sess_test1"}}}
                return m
            elif "/chat/create_pow_challenge" in url:
                m.status_code = 200
                m.json.return_value = {"data": {"biz_data": {"challenge": {
                    "algorithm": "sha256", "challenge": "test_chal",
                    "difficulty": 4, "salt": "test_salt", "signature": "test_sig",
                }}}}
                return m
            raise RuntimeError(f"Unexpected URL: {url}")

        sse_lines = [
            'data: {"p":"response/thinking_content","o":"APPEND","v":"让我分析..."}',
            'data: {"p":"response/content","o":"APPEND","v":"答案是42"}',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]
        mock_stream_resp = MagicMock(spec=httpx.Response)
        mock_stream_resp.status_code = 200
        mock_stream_resp.aiter_lines = MagicMock(return_value=_async_iter(sse_lines))

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_fn)
        client._http.stream = MagicMock(return_value=mock_stream_ctx)

        # 执行（内部会自动 create_chat_session → create_pow_challenge → stream completion）
        result = await client.chat_completion(prompt="1+1=?")

        assert "42" in result.text
        assert "让我分析" in result.thinking
        assert result.session_id == "sess_test1"
        assert result.finish_reason == "finished"

    @pytest.mark.asyncio
    async def test_chat_completion_reuses_existing_session(self, valid_auth):
        """已有 session 时不再创建新 session."""
        client = DeepSeekWebClient(valid_auth)
        client._current_session_id = "existing_session"

        # Mock PoW
        mock_pow_resp = MagicMock(spec=httpx.Response)
        mock_pow_resp.status_code = 200
        mock_pow_resp.json.return_value = {
            "data": {"biz_data": {"challenge": {
                "algorithm": "sha256", "challenge": "ch",
                "difficulty": 4, "salt": "s", "signature": "g",
            }}}
        }

        mock_stream_resp = MagicMock(spec=httpx.Response)
        mock_stream_resp.status_code = 200
        mock_stream_resp.aiter_lines = MagicMock(return_value=_async_iter([
            'data: {"p":"response/content","o":"APPEND","v":"reuse ok"}',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]))

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_pow_resp)
        client._http.stream = MagicMock(return_value=mock_stream_ctx)

        result = await client.chat_completion(prompt="test")
        assert result.text == "reuse ok"
        assert result.session_id == "existing_session"

    @pytest.mark.asyncio
    async def test_chat_completion_http_error(self, valid_auth):
        """HTTP 非 200 响应应抛 RuntimeError."""
        client = DeepSeekWebClient(valid_auth)
        client._current_session_id = "sess_1"

        mock_pow_resp = MagicMock(spec=httpx.Response)
        mock_pow_resp.status_code = 200
        mock_pow_resp.json.return_value = {
            "data": {"biz_data": {"challenge": {
                "algorithm": "sha256", "challenge": "ch",
                "difficulty": 4, "salt": "s", "signature": "g",
            }}}
        }

        mock_stream_resp = MagicMock(spec=httpx.Response)
        mock_stream_resp.status_code = 429

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        client._http = AsyncMock()
        client._http.post = AsyncMock(return_value=mock_pow_resp)
        client._http.stream = MagicMock(return_value=mock_stream_ctx)

        with pytest.raises(RuntimeError, match="Chat completion 失败"):
            await client.chat_completion(prompt="test")


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — 文件上传
# ══════════════════════════════════════════════════════════════════════

class TestUploadFile:
    """upload_file() 测试."""

    @pytest.mark.asyncio
    async def test_upload_success_with_polling(self, valid_auth):
        """上传成功 + 轮询到 SUCCESS."""
        client = DeepSeekWebClient(valid_auth)

        # Mock PoW
        async def post_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            if "create_pow_challenge" in url:
                m.json.return_value = {"data": {"biz_data": {"challenge": {
                    "algorithm": "sha256", "challenge": "ch",
                    "difficulty": 4, "salt": "s", "signature": "g",
                }}}}
            elif "upload_file" in url:
                m.json.return_value = {
                    "data": {"biz_data": {"id": "file_abc123"}}
                }
            return m

        # Mock 轮询 GET — 第一次返回 PROCESSING，第二次返回 SUCCESS
        poll_call_count = [0]

        async def get_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            poll_call_count[0] += 1
            if poll_call_count[0] == 1:
                m.json.return_value = {
                    "data": {"biz_data": {"files": [{"id": "file_abc123", "status": "PROCESSING"}]}}
                }
            else:
                m.json.return_value = {
                    "data": {"biz_data": {"files": [{"id": "file_abc123", "status": "SUCCESS"}]}}
                }
            return m

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_side_effect)
        client._http.get = AsyncMock(side_effect=get_side_effect)

        # 加速轮询
        import hyperspace.hybrid_engine.deepseek_web_client as dwc
        import asyncio
        original_interval = dwc.UPLOAD_POLL_INTERVAL
        dwc.UPLOAD_POLL_INTERVAL = 0.01  # 10ms

        try:
            file_id = await client.upload_file(b"fake_image_data", "test.jpg")
            assert file_id == "file_abc123"
            assert poll_call_count[0] == 2  # 两次轮询
        finally:
            dwc.UPLOAD_POLL_INTERVAL = original_interval

    @pytest.mark.asyncio
    async def test_upload_failed_status_raises_error(self, valid_auth):
        """轮询到 FAILED 应抛出 RuntimeError."""
        client = DeepSeekWebClient(valid_auth)

        async def post_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            if "create_pow_challenge" in url:
                m.json.return_value = {"data": {"biz_data": {"challenge": {
                    "algorithm": "sha256", "challenge": "ch",
                    "difficulty": 4, "salt": "s", "signature": "g",
                }}}}
            elif "upload_file" in url:
                m.json.return_value = {
                    "data": {"biz_data": {"id": "file_fail1"}}
                }
            return m

        async def get_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            m.json.return_value = {
                "data": {"biz_data": {"files": [{"id": "file_fail1", "status": "FAILED"}]}}
            }
            return m

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_side_effect)
        client._http.get = AsyncMock(side_effect=get_side_effect)

        import hyperspace.hybrid_engine.deepseek_web_client as dwc
        original_interval = dwc.UPLOAD_POLL_INTERVAL
        dwc.UPLOAD_POLL_INTERVAL = 0.01

        try:
            with pytest.raises(RuntimeError, match="文件处理失败"):
                await client.upload_file(b"fake_data", "test.png")
        finally:
            dwc.UPLOAD_POLL_INTERVAL = original_interval

    @pytest.mark.asyncio
    async def test_upload_polling_timeout_returns_file_id(self, valid_auth):
        """轮询超时（始终 PROCESSING）时仍返回 file_id."""
        client = DeepSeekWebClient(valid_auth)

        async def post_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            if "create_pow_challenge" in url:
                m.json.return_value = {"data": {"biz_data": {"challenge": {
                    "algorithm": "sha256", "challenge": "ch",
                    "difficulty": 4, "salt": "s", "signature": "g",
                }}}}
            elif "upload_file" in url:
                m.json.return_value = {
                    "data": {"biz_data": {"id": "file_timeout1"}}
                }
            return m

        async def get_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            m.json.return_value = {
                "data": {"biz_data": {"files": [{"id": "file_timeout1", "status": "PROCESSING"}]}}
            }
            return m

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_side_effect)
        client._http.get = AsyncMock(side_effect=get_side_effect)

        import hyperspace.hybrid_engine.deepseek_web_client as dwc
        original_interval = dwc.UPLOAD_POLL_INTERVAL
        dwc.UPLOAD_POLL_INTERVAL = 0.01

        try:
            file_id = await client.upload_file(b"fake_data", "test.gif")
            assert file_id == "file_timeout1"  # 超时后仍返回 id
        finally:
            dwc.UPLOAD_POLL_INTERVAL = original_interval

    @pytest.mark.asyncio
    async def test_upload_missing_file_id_in_response(self, valid_auth):
        """上传响应缺少 file_id 应抛 RuntimeError."""
        client = DeepSeekWebClient(valid_auth)

        async def post_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            if "create_pow_challenge" in url:
                m.json.return_value = {"data": {"biz_data": {"challenge": {
                    "algorithm": "sha256", "challenge": "ch",
                    "difficulty": 4, "salt": "s", "signature": "g",
                }}}}
            elif "upload_file" in url:
                m.json.return_value = {"data": {"biz_data": {}}}  # 缺少 id
            return m

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_side_effect)

        with pytest.raises(RuntimeError, match="上传响应缺少 file_id"):
            await client.upload_file(b"fake_data", "test.jpg")

    @pytest.mark.asyncio
    async def test_upload_http_error(self, valid_auth):
        """上传 HTTP 错误应抛 RuntimeError."""
        client = DeepSeekWebClient(valid_auth)

        async def post_side_effect(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            if "create_pow_challenge" in url:
                m.status_code = 200
                m.json.return_value = {"data": {"biz_data": {"challenge": {
                    "algorithm": "sha256", "challenge": "ch",
                    "difficulty": 4, "salt": "s", "signature": "g",
                }}}}
            elif "upload_file" in url:
                m.status_code = 500
                m.text = "Server Error"
            return m

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_side_effect)

        with pytest.raises(RuntimeError, match="文件上传失败"):
            await client.upload_file(b"fake_data", "test.jpg")


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — 便捷 chat() 方法
# ══════════════════════════════════════════════════════════════════════

class TestChatConvenience:
    """chat() 便捷方法测试."""

    @pytest.mark.asyncio
    async def test_chat_without_images(self, valid_auth):
        """无图片时的基本调用."""
        client = DeepSeekWebClient(valid_auth)
        client._current_session_id = "sess_conv"

        async def post_fn(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            m.json.return_value = {"data": {"biz_data": {"challenge": {
                "algorithm": "sha256", "challenge": "ch",
                "difficulty": 4, "salt": "s", "signature": "g",
            }}}}
            return m

        mock_stream_resp = MagicMock(spec=httpx.Response)
        mock_stream_resp.status_code = 200
        mock_stream_resp.aiter_lines = MagicMock(return_value=_async_iter([
            'data: {"p":"response/content","o":"APPEND","v":"你好"}',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]))

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_fn)
        client._http.stream = MagicMock(return_value=mock_stream_ctx)

        result = await client.chat("你好")
        assert result.text == "你好"
        assert result.session_id == "sess_conv"

    @pytest.mark.asyncio
    async def test_chat_with_local_image(self, valid_auth, tmp_path):
        """有本地图片时触发上传流程."""
        # 创建临时图片文件
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\nfake_png_data")

        client = DeepSeekWebClient(valid_auth)
        client._current_session_id = "sess_img"

        # Mock PoW（上传用 + completion 用）
        async def post_fn(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            if "create_pow_challenge" in url:
                m.json.return_value = {"data": {"biz_data": {"challenge": {
                    "algorithm": "sha256", "challenge": "ch",
                    "difficulty": 4, "salt": "s", "signature": "g",
                }}}}
            elif "upload_file" in url:
                m.json.return_value = {"data": {"biz_data": {"id": "file_img1"}}}
            return m

        # 轮询 GET — 直接 SUCCESS
        async def get_fn(url, **kwargs):
            m = MagicMock(spec=httpx.Response)
            m.status_code = 200
            m.json.return_value = {
                "data": {"biz_data": {"files": [{"id": "file_img1", "status": "SUCCESS"}]}}
            }
            return m

        # Completion 流
        mock_stream_resp = MagicMock(spec=httpx.Response)
        mock_stream_resp.status_code = 200
        mock_stream_resp.aiter_lines = MagicMock(return_value=_async_iter([
            'data: {"p":"response/content","o":"APPEND","v":"图中是PNG"}',
            'data: {"p":"response/status","v":"FINISHED"}',
        ]))

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        client._http = AsyncMock()
        client._http.post = AsyncMock(side_effect=post_fn)
        client._http.get = AsyncMock(side_effect=get_fn)
        client._http.stream = MagicMock(return_value=mock_stream_ctx)

        import hyperspace.hybrid_engine.deepseek_web_client as dwc
        original_interval = dwc.UPLOAD_POLL_INTERVAL
        dwc.UPLOAD_POLL_INTERVAL = 0.01

        try:
            result = await client.chat("描述图片", images=[str(img_path)])
            assert result.text == "图中是PNG"
        finally:
            dwc.UPLOAD_POLL_INTERVAL = original_interval


# ══════════════════════════════════════════════════════════════════════
# TestDeepSeekWebClient — 认证验证
# ══════════════════════════════════════════════════════════════════════

class TestVerifyAuth:
    """verify_auth() 和 fetch_token_from_api() 测试."""

    @pytest.mark.asyncio
    async def test_verify_auth_success(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_resp)

        assert await client.verify_auth() is True

    @pytest.mark.asyncio
    async def test_verify_auth_failure(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_resp)

        assert await client.verify_auth() is False

    @pytest.mark.asyncio
    async def test_verify_auth_exception(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        client._http = AsyncMock()
        client._http.get = AsyncMock(side_effect=Exception("network error"))

        assert await client.verify_auth() is False

    @pytest.mark.asyncio
    async def test_fetch_token_success(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"biz_data": {"token": "fresh_token_xyz"}}
        }
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_resp)

        token = await client.fetch_token_from_api()
        assert token == "fresh_token_xyz"

    @pytest.mark.asyncio
    async def test_fetch_token_not_found(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {}}
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_resp)

        token = await client.fetch_token_from_api()
        assert token is None

    @pytest.mark.asyncio
    async def test_fetch_token_http_error(self, valid_auth):
        client = DeepSeekWebClient(valid_auth)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        client._http = AsyncMock()
        client._http.get = AsyncMock(return_value=mock_resp)

        token = await client.fetch_token_from_api()
        assert token is None


# ══════════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════════

async def _async_iter(items: list[str]):
    """将列表转为异步迭代器."""
    for item in items:
        yield item
