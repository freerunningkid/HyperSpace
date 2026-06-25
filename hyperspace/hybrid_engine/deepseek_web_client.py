"""DeepSeek Web Client —— 直接调用 chat.deepseek.com 内部 API.

核心流程:
  1. 使用存储的 Cookie + Bearer Token 认证
  2. 创建 PoW 挑战 (SHA256 / DeepSeekHashV1 via WASM)
  3. 求解 PoW
  4. 创建聊天会话
  5. 发送 Chat Completion 请求 (SSE 流)
  6. 解析流式响应, 提取最终文本 + 思维链

依赖: httpx, hashlib (标准库), wasmtime (DeepSeekHashV1 PoW)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger("hyperspace.deepseek_web")

# ── 常量 ──

BASE_URL = "https://chat.deepseek.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
POW_TIMEOUT_NONCE = 1_000_000  # 最多尝试 1M 次 nonce
CHAT_TIMEOUT = 120.0            # Chat 请求超时 (秒)
UPLOAD_POLL_INTERVAL = 1.0     # 上传文件轮询间隔 (秒)
UPLOAD_MAX_POLLS = 30          # 最多轮询 30 次

# ── 数据结构 ──

@dataclass
class PowChallenge:
    """PoW 挑战."""
    algorithm: str          # "sha256" | "DeepSeekHashV1"
    challenge: str
    difficulty: int
    salt: str
    signature: str
    expire_at: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "PowChallenge":
        return cls(
            algorithm=d.get("algorithm", "sha256"),
            challenge=d.get("challenge", ""),
            difficulty=d.get("difficulty", 4),
            salt=d.get("salt", ""),
            signature=d.get("signature", ""),
            expire_at=d.get("expire_at", 0),
        )

    def with_answer(self, answer: int, target_path: str) -> str:
        """生成 x-ds-pow-response header 值 (base64 JSON)."""
        payload = {
            "algorithm": self.algorithm,
            "challenge": self.challenge,
            "difficulty": self.difficulty,
            "salt": self.salt,
            "signature": self.signature,
            "answer": answer,
            "target_path": target_path,
        }
        import base64
        return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


@dataclass
class DeepSeekWebResponse:
    """标准化的 DeepSeek Web 响应."""
    text: str = ""
    thinking: str = ""        # 思维链 (R1 模式)
    session_id: str = ""
    message_id: str = ""      # 当前消息 ID (用于多轮对话 parent_message_id)
    finish_reason: str = ""


@dataclass
class DeepSeekAuth:
    """认证凭据."""
    cookie: str = ""
    bearer: str = ""
    user_agent: str = DEFAULT_USER_AGENT
    saved_at: float = 0.0

    def is_valid(self) -> bool:
        """快速检查凭据是否看起来有效."""
        # Bearer token 优先 (新版认证方式)
        if self.bearer and len(self.bearer) > 20:
            return True
        # 旧版 d_id Cookie
        return bool(self.cookie) and ("d_id=" in self.cookie or "ds_session_id=" in self.cookie)

    def to_dict(self) -> dict:
        return {
            "cookie": self.cookie,
            "bearer": self.bearer,
            "user_agent": self.user_agent,
            "saved_at": self.saved_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DeepSeekAuth":
        return cls(
            cookie=d.get("cookie", ""),
            bearer=d.get("bearer", ""),
            user_agent=d.get("user_agent", DEFAULT_USER_AGENT),
            saved_at=d.get("saved_at", 0.0),
        )


# ── 默认头 ──

def _default_headers(auth: DeepSeekAuth) -> dict[str, str]:
    """构建 DeepSeek Web API 请求头."""
    headers = {
        "User-Agent": auth.user_agent or DEFAULT_USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Referer": "https://chat.deepseek.com/",
        "Origin": "https://chat.deepseek.com",
        "x-client-platform": "web",
        "x-client-version": "1.7.0",
        "x-app-version": "20241129.1",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
    }
    if auth.cookie:
        headers["Cookie"] = auth.cookie
    if auth.bearer:
        headers["Authorization"] = f"Bearer {auth.bearer}"
    return headers


# ── PoW 求解 ──

# DeepSeekHashV1 WASM 模块 (延迟加载)
_WASM_MODULE = None
_WASM_ENGINE = None


def _get_wasm_solver():
    """获取 WASM PoW 求解器 (单例)."""
    global _WASM_MODULE, _WASM_ENGINE
    if _WASM_MODULE is not None:
        return _WASM_MODULE, _WASM_ENGINE

    import os as _os
    try:
        import wasmtime
    except ImportError:
        logger.warning("wasmtime 未安装, DeepSeekHashV1 PoW 不可用")
        return None, None

    # 查找 WASM 文件
    wasm_paths = [
        _os.path.join(_os.path.dirname(__file__), "sha3_wasm.wasm"),
        _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "data", "sha3_wasm.wasm"),
    ]
    wasm_bytes = None
    for p in wasm_paths:
        if _os.path.exists(p):
            with open(p, "rb") as f:
                wasm_bytes = f.read()
            break

    if not wasm_bytes:
        logger.warning("sha3_wasm.wasm 未找到, DeepSeekHashV1 PoW 不可用")
        return None, None

    engine = wasmtime.Engine()
    module = wasmtime.Module(engine, wasm_bytes)
    _WASM_MODULE = module
    _WASM_ENGINE = engine
    return module, engine


def solve_sha256_pow(challenge: PowChallenge) -> int:
    """求解 SHA256 PoW: 找到 nonce 使 sha256(salt + challenge + str(nonce)) 的前导零位 >= difficulty."""
    prefix = challenge.salt + challenge.challenge
    target_bits = challenge.difficulty

    # 如果 difficulty 很大 (>1000), 说明是概率格式, 取 log2
    if target_bits > 1000:
        import math
        target_bits = int(math.log2(target_bits))

    for nonce in range(POW_TIMEOUT_NONCE):
        data = f"{prefix}{nonce}".encode()
        hash_hex = hashlib.sha256(data).hexdigest()
        zero_bits = _count_leading_zero_bits(hash_hex)
        if zero_bits >= target_bits:
            return nonce

    raise RuntimeError(f"SHA256 PoW 超时: 尝试了 {POW_TIMEOUT_NONCE} 次 nonce")


def solve_deepseek_hash_v1(challenge: PowChallenge) -> int:
    """求解 DeepSeekHashV1 PoW (通过 WASM).

    算法: SHA3-256(challenge + "_" + salt + "_" + expire_at + "_" + str(nonce))
    返回满足 difficulty 要求的 nonce.
    """
    module, engine = _get_wasm_solver()
    if module is None:
        raise RuntimeError("DeepSeekHashV1 PoW 不可用: wasmtime 或 sha3_wasm.wasm 缺失")

    import wasmtime

    store = wasmtime.Store(engine)
    instance = wasmtime.Instance(store, module, [])

    memory = instance.exports(store)["memory"]
    wasm_solve_fn = instance.exports(store)["wasm_solve"]
    malloc = instance.exports(store)["__wbindgen_export_0"]
    stack_ptr_fn = instance.exports(store)["__wbindgen_add_to_stack_pointer"]

    def _write_to_mem(data: bytes) -> int:
        ptr = malloc(store, len(data), 1)
        mem = memory.data_ptr(store)
        for i, b in enumerate(data):
            mem[ptr + i] = b
        return ptr

    # 构建 prefix: salt_expireAt_
    prefix = f"{challenge.salt}_{challenge.expire_at}_"

    stack_ptr = stack_ptr_fn(store, -16)

    ch_bytes = challenge.challenge.encode("utf-8")
    ch_ptr = _write_to_mem(ch_bytes)

    pf_bytes = prefix.encode("utf-8")
    pf_ptr = _write_to_mem(pf_bytes)

    wasm_solve_fn(
        store, stack_ptr,
        ch_ptr, len(ch_bytes),
        pf_ptr, len(pf_bytes),
        float(challenge.difficulty),
    )

    # 读取结果
    import struct
    mem = memory.data_ptr(store)
    status = struct.unpack("<i", bytes(mem[stack_ptr : stack_ptr + 4]))[0]
    answer = struct.unpack("<d", bytes(mem[stack_ptr + 8 : stack_ptr + 16]))[0]

    if status == 0:
        raise RuntimeError(f"DeepSeekHashV1 PoW 无解: challenge={challenge.challenge[:20]}...")

    return int(answer)


def solve_pow(challenge: PowChallenge) -> int:
    """根据算法类型自动选择 PoW 求解器."""
    algo = challenge.algorithm
    if algo == "DeepSeekHashV1":
        return solve_deepseek_hash_v1(challenge)
    elif algo == "sha256":
        return solve_sha256_pow(challenge)
    else:
        raise RuntimeError(f"不支持的 PoW 算法: {algo}")


def _count_leading_zero_bits(hex_str: str) -> int:
    """计算 hex 字符串的前导零位数."""
    count = 0
    for c in hex_str:
        val = int(c, 16)
        if val == 0:
            count += 4
        else:
            # 该 nibble 的前导零位数 = 4 - bit_length
            count += 4 - val.bit_length()
            break
    return count


# ── DeepSeek Web API 客户端 ──

class DeepSeekWebClient:
    """DeepSeek Web 内部 API 客户端.

    使用存储的认证凭据直接调用 chat.deepseek.com 的内部 API.
    """

    def __init__(self, auth: DeepSeekAuth):
        self._auth = auth
        self._http = httpx.AsyncClient(timeout=CHAT_TIMEOUT, follow_redirects=True)
        self._current_session_id: str | None = None

    async def close(self):
        """关闭 HTTP 客户端."""
        await self._http.aclose()

    # ── 认证 ──

    @property
    def auth(self) -> DeepSeekAuth:
        return self._auth

    @auth.setter
    def auth(self, new_auth: DeepSeekAuth):
        self._auth = new_auth

    async def verify_auth(self) -> bool:
        """通过 GET /api/v0/users/current 验证认证是否有效."""
        try:
            resp = await self._http.get(
                f"{BASE_URL}/api/v0/users/current",
                headers=_default_headers(self._auth),
            )
            if resp.status_code != 200:
                return False
            data = resp.json()
            return data.get("code") == 0
        except Exception:
            return False

    async def fetch_token_from_api(self) -> str | None:
        """从 /api/v0/users/current 响应中提取 Bearer token."""
        try:
            resp = await self._http.get(
                f"{BASE_URL}/api/v0/users/current",
                headers=_default_headers(self._auth),
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            token = (
                data.get("data", {})
                .get("biz_data", {})
                .get("token", "")
            )
            return token or None
        except Exception:
            return None

    # ── PoW 挑战 ──

    async def create_pow_challenge(self, target_path: str) -> PowChallenge:
        """创建 PoW 挑战."""
        headers = _default_headers(self._auth)
        resp = await self._http.post(
            f"{BASE_URL}/api/v0/chat/create_pow_challenge",
            headers=headers,
            json={"target_path": target_path},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"PoW 挑战失败 (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        # 尝试多种可能的响应路径
        challenge_data = (
            data.get("data", {}).get("biz_data", {}).get("challenge")
            or data.get("data", {}).get("challenge")
            or data.get("challenge")
        )
        if not challenge_data:
            raise RuntimeError(f"PoW 响应结构异常: {json.dumps(data, ensure_ascii=False)[:300]}")

        return PowChallenge.from_dict(challenge_data)

    # ── 聊天会话 ──

    async def create_chat_session(self) -> str:
        """创建新的聊天会话, 返回 session_id."""
        headers = _default_headers(self._auth)
        resp = await self._http.post(
            f"{BASE_URL}/api/v0/chat_session/create",
            headers=headers,
            json={},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"创建会话失败 (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        biz_data = data.get("data", {}).get("biz_data", {})
        session_id = biz_data.get("id") or biz_data.get("chat_session_id", "")
        if not session_id:
            raise RuntimeError(f"会话创建响应缺少 id: {json.dumps(data, ensure_ascii=False)[:300]}")

        self._current_session_id = session_id
        return session_id

    # ── Chat Completion (流式) ──

    async def chat_completion(
        self,
        prompt: str,
        session_id: str | None = None,
        parent_message_id: str | None = None,
        ref_file_ids: list[str] | None = None,
        thinking_enabled: bool = True,
        search_enabled: bool = True,
    ) -> DeepSeekWebResponse:
        """发送 Chat Completion 请求, 返回解析后的响应.

        内部流程:
          1. 创建/复用聊天会话
          2. 创建 PoW 挑战
          3. 求解 PoW
          4. POST chat/completion
          5. 解析 SSE 流
        """
        # 确保有会话
        if not session_id:
            if not self._current_session_id:
                session_id = await self.create_chat_session()
            else:
                session_id = self._current_session_id

        target_path = "/api/v0/chat/completion"

        # PoW
        challenge = await self.create_pow_challenge(target_path)
        answer = solve_pow(challenge)
        pow_response = challenge.with_answer(answer, target_path)

        # 构建请求
        headers = _default_headers(self._auth)
        headers["x-ds-pow-response"] = pow_response

        body = {
            "chat_session_id": session_id,
            "parent_message_id": parent_message_id,
            "prompt": prompt,
            "ref_file_ids": ref_file_ids or [],
            "thinking_enabled": thinking_enabled,
            "search_enabled": search_enabled,
        }

        # 发送请求并处理流式响应
        result = DeepSeekWebResponse(session_id=session_id)
        async with self._http.stream(
            "POST",
            f"{BASE_URL}/api/v0/chat/completion",
            headers=headers,
            json=body,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise RuntimeError(
                    f"Chat completion 失败 (HTTP {response.status_code}): "
                    f"{error_text[:300].decode('utf-8', errors='replace')}"
                )

            await self._parse_sse_stream(response, result)

        return result

    async def _parse_sse_stream(
        self,
        response: httpx.Response,
        result: DeepSeekWebResponse,
    ):
        """解析新版 DeepSeek SSE 流 (path-based patch 格式).

        格式特点:
          - 首个 data 设定 path+op: {"p": "response/...", "o": "APPEND", "v": "..."}
          - 后续 data 只含 v, 追加到同一 path: {"v": "..."}
          - 路径切换时再次带 p+o

        路径语义:
          - R1 模式: response/thinking_content (思考) + response/content (回答)
          - V3 模式: response/fragments/<id>/content (回答, 可能含思考)
          - 结束: response/status -> "FINISHED"
        """
        # 按路径分组缓冲
        path_buffers: dict[str, list[str]] = {}
        current_path = ""
        finished = False

        async for raw_line in response.aiter_lines():
            line = raw_line.strip()

            # 跳过 event 行
            if line.startswith("event:"):
                continue

            # 只处理 data 行
            if not line.startswith("data:"):
                continue

            data_str = line[5:].strip()
            if not data_str or data_str == "{}":
                continue

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            value = event.get("v", "")

            # 嵌套 dict (初始对象) — 捕获 message_id
            if isinstance(value, dict):
                msg_id = value.get("response", {}).get("message_id", "")
                if msg_id:
                    result.message_id = str(msg_id)
                continue

            # 路径切换
            if "p" in event:
                current_path = event["p"]

            # 收集内容到对应路径
            if isinstance(value, str) and value and current_path:
                if current_path not in path_buffers:
                    path_buffers[current_path] = []
                path_buffers[current_path].append(value)

            # 检测结束
            if current_path == "response/status" and str(value) == "FINISHED":
                finished = True

            # 兼容旧版 type-based 格式
            event_type = event.get("type", "")
            content = event.get("content", "") or event.get("delta", "") or ""
            if event_type == "error":
                raise RuntimeError(f"DeepSeek API 错误: {content}")

        # ── 从缓冲区分派 thinking 和 text ──
        thinking_content = ""
        text_content = ""

        # R1 模式: 有独立的 response/content (回答) 和 response/thinking_content (思考)
        has_thinking = "response/thinking_content" in path_buffers
        has_answer = "response/content" in path_buffers

        if has_thinking:
            thinking_content = "".join(path_buffers["response/thinking_content"])

        if has_answer:
            text_content = "".join(path_buffers["response/content"])
        elif not has_thinking:
            # V3 模式或无思考模式: fragments 就是回答 (不含 thinking_content)
            for path, parts in path_buffers.items():
                if "content" in path and "status" not in path and "thinking" not in path:
                    text_content = "".join(parts)
                    break
        # else: 只有 thinking 没有 answer → thinking 已设置, text 留空

        result.text = text_content
        result.thinking = thinking_content
        if finished:
            result.finish_reason = "finished"

    # ── 文件上传 ──

    async def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str | None = None,
    ) -> str:
        """上传文件 (如图片), 返回 file_id."""
        target_path = "/api/v0/file/upload_file"

        challenge = await self.create_pow_challenge(target_path)
        answer = solve_pow(challenge)
        pow_response = challenge.with_answer(answer, target_path)

        headers = _default_headers(self._auth)
        headers.pop("Content-Type", None)
        headers["x-ds-pow-response"] = pow_response
        headers["x-file-size"] = str(len(file_data))

        # 构建 multipart 请求
        files = {"file": (file_name, file_data, content_type or "image/jpeg")}

        resp = await self._http.post(
            f"{BASE_URL}/api/v0/file/upload_file",
            headers=headers,
            files=files,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"文件上传失败 (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        file_id = data.get("data", {}).get("biz_data", {}).get("id", "")
        if not file_id:
            raise RuntimeError(f"上传响应缺少 file_id: {json.dumps(data, ensure_ascii=False)[:300]}")

        # 轮询等待处理完成
        for _ in range(UPLOAD_MAX_POLLS):
            await asyncio.sleep(UPLOAD_POLL_INTERVAL)
            poll_resp = await self._http.get(
                f"{BASE_URL}/api/v0/file/fetch_files",
                headers=_default_headers(self._auth),
                params={"file_ids": file_id},
            )
            if poll_resp.status_code != 200:
                continue

            poll_data = poll_resp.json()
            files_list = (
                poll_data.get("data", {})
                .get("biz_data", {})
                .get("files", [])
            )
            if not files_list:
                continue

            file_status = files_list[0].get("status", "")
            if file_status == "SUCCESS":
                return file_id
            elif file_status == "FAILED":
                raise RuntimeError(f"文件处理失败: {file_id}")

        # 超时返回 (可能成功, 但不确定)
        return file_id

    async def prepare_ref_file_ids(self, files: list[str] | None) -> list[str]:
        """上传本地/URL/data URI 文件, 返回 DeepSeek Web ref_file_ids."""
        if not files:
            return []

        ref_file_ids: list[str] = []
        for item in files:
            try:
                file_data, file_name, content_type = await self._load_file_item(item)
                file_id = await self.upload_file(file_data, file_name, content_type)
                ref_file_ids.append(file_id)
            except Exception as e:
                logger.warning(f"DeepSeek Web 文件准备失败: {item[:80]} — {e}")
        return ref_file_ids

    async def _load_file_item(self, item: str) -> tuple[bytes, str, str]:
        """加载本地路径、URL 或 data URI 文件."""
        if item.startswith("data:"):
            return self._load_data_uri(item)
        if item.startswith(("http://", "https://")):
            return await self._download_url_file(item)

        path = Path(item)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {item}")
        if not path.is_file():
            raise RuntimeError(f"不是文件: {item}")
        data = path.read_bytes()
        return data, path.name, self._guess_content_type(path.name, data)

    async def _download_url_file(self, url: str) -> tuple[bytes, str, str]:
        """下载 URL 文件."""
        parsed = urlparse(url)
        file_name = Path(unquote(parsed.path)).name or "download"
        resp = await self._http.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"URL 下载失败 (HTTP {resp.status_code}): {url}")
        data = resp.content
        return data, file_name, resp.headers.get("content-type") or self._guess_content_type(file_name, data)

    def _load_data_uri(self, data_uri: str) -> tuple[bytes, str, str]:
        """解析 data URI."""
        header, encoded = data_uri.split(",", 1)
        meta = header.split(";", 1)[0].split(":", 1)[1]
        content_type = meta.split(";", 1)[0] or "application/octet-stream"
        extension = mimetypes.guess_extension(content_type) or ".bin"
        raw = base64.b64decode(encoded)
        return raw, f"upload{extension}", content_type

    def _guess_content_type(self, file_name: str, data: bytes) -> str:
        """根据文件名和文件头猜测 MIME 类型."""
        guessed = mimetypes.guess_type(file_name)[0]
        if guessed:
            return guessed
        if data.startswith(b"%PDF"):
            return "application/pdf"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith((b"\xff\xd8", b"\xff\xd9")):
            return "image/jpeg"
        return "application/octet-stream"

    # ── 便捷方法 ──

    async def chat(
        self,
        prompt: str,
        images: list[str] | None = None,
        search_enabled: bool = True,
        web_mode: str = "auto",
    ) -> DeepSeekWebResponse:
        """便捷 Chat 方法: 流式对话 (逐句拼接)."""
        ref_file_ids = await self.prepare_ref_file_ids(images)
        if ref_file_ids:
            search_enabled = False  # 有图片/文件时默认禁用搜索
        thinking_enabled = web_mode != "quick"

        return await self.chat_completion(
            prompt=prompt,
            ref_file_ids=ref_file_ids or None,
            search_enabled=search_enabled,
            thinking_enabled=thinking_enabled,
        )
