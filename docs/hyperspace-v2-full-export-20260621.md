# HyperSpace v2.0 — 完整技术导出文档

> **生成日期**: 2026-06-21  
> **项目路径**: `D:\Reasonix\HyperSpace\`  
> **会话内容**: DeepSeek Web 原生客户端实现 + 混合推理引擎 + 上下文窗口管理

---

## 一、架构总览

### 1.1 设计目标

构建以 **DeepSeek 生态为绝对主力**的三层推理架构：
- 🥇 **DeepSeek Web** (原生 Python 客户端, 零 Token 成本) — 规划/搜索/识图/长文本
- 🥈 **DeepSeek API** (OpenAI 兼容 API, 低成本) — 代码/翻译/结构化输出
- 🥉 **智谱 GLM** (免费 API 兜底) — 前两者都不可用时的保险

### 1.2 核心创新

**不依赖 OpenClaw / FreeLLMAPI 等外部服务**。  
我们独立实现了 DeepSeek Web 的内部 API 调用（PoW 挑战求解、会话管理、流式对话、文件上传），Python 代码自包含，零外部依赖。

### 1.3 架构图

```
Agent (Reasonix / Claude Code / VS Code / ZCode桥接)
   │ MCP stdio (hyperspace_query)
   ▼
HyperSpace MCP Server (server.py)
   │
   ├── auto / force_web / force_api / force_zhipu
   │   └── HybridRouter
   │       ├── TaskAnalyzer (特征分析)
   │       ├── HealthChecker (健康探测)
   │       └── ContextWindowManager ← session 上下文管理
   │           ├── DeepSeekWebClient → chat.deepseek.com (PoW + SSE)
   │           └── [压缩摘要] → DeepSeek API / Zhipu
   │
   └── free_text / cheap_capable / free_vision / premium (legacy)
       └── select_tier → Executor → OpenAICompatProvider
```

### 1.4 降级链

```
DeepSeek Web (原生) → DeepSeek API → 智谱 GLM → 友好错误提示
```

### 1.5 路由优先级

| 优先级 | 条件 | 路由 | 理由 |
|--------|------|------|------|
| 1 | `has_image` | DeepSeek Web | 原生识图 |
| 2 | `needs_search` | DeepSeek Web | 联网搜索 |
| 3 | `needs_planning` | DeepSeek Web | 长文本规划 |
| 4 | `is_long` (>5000字) | DeepSeek Web | 1M 上下文 |
| 5 | `needs_coding` | DeepSeek API | 代码输出稳定 |
| 6 | `needs_translation` | DeepSeek API | 标准化翻译 |
| 7 | `needs_structured_output` | DeepSeek API | JSON 模式 |
| 8 | 默认 | DeepSeek Web | 经济优先 |

---

## 二、项目结构

```
D:\Reasonix\HyperSpace\
├── hyperspace/
│   ├── server.py                              # MCP 服务端入口
│   ├── config.py                              # 配置加载
│   ├── router.py / executor.py / cost.py / tiers.py / summary.py / info.py
│   ├── providers/
│   │   ├── base.py                            # 异常类型
│   │   └── openai_compat.py                   # OpenAI 兼容 client
│   ├── experimental/                          # (严格隔离)
│   └── hybrid_engine/                         # ← 核心混合引擎
│       ├── __init__.py
│       ├── task_analyzer.py                   # 任务特征分析
│       ├── health_checker.py                  # 服务健康探测
│       ├── deepseek_web_client.py             # ★ DeepSeek Web 原生客户端
│       ├── web_auth.py                        # ★ 浏览器凭据提取
│       ├── context_window_manager.py          # ★ 上下文窗口管理
│       ├── hybrid_router.py                   # 核心路由决策
│       ├── result_processor.py                # 结果后处理
│       └── fallback.py                        # 降级管理
├── config/
│   ├── providers.yaml / routing.yaml          # 旧路由配置
│   └── hybrid_config.yaml                     # ★ 混合引擎配置
├── tests/
│   ├── test_router.py / test_providers.py     # 旧测试 (25)
│   └── test_hybrid_engine.py                  # ★ 混合引擎测试 (39)
├── docs/
│   └── architecture.md
├── .mcp.json                                   # Claude Code
├── .vscode/mcp.json                            # VS Code Copilot
├── README.md / pyproject.toml / LICENSE
└── data/
    ├── hyperspace_cost.log                    # 成本日志
    └── deepseek_web_auth.json                 # Web 凭据
```

---

## 三、核心模块源码

### 3.1 `deepseek_web_client.py` — DeepSeek Web API 客户端

```python
\"\"\"DeepSeek Web Client —— 直接调用 chat.deepseek.com 内部 API.

核心流程:
  1. 使用存储的 Cookie + Bearer Token 认证
  2. 创建 PoW 挑战 (SHA256)
  3. 求解 PoW
  4. 创建聊天会话
  5. 发送 Chat Completion 请求 (SSE 流)
  6. 解析流式响应, 提取最终文本 + 思维链

依赖: httpx, hashlib (Python 标准库)
\"\"\"

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx

logger = logging.getLogger(\"hyperspace.deepseek_web\")

# ── 常量 ──

BASE_URL = \"https://chat.deepseek.com\"
DEFAULT_USER_AGENT = (
    \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) \"
    \"AppleWebKit/537.36 (KHTML, like Gecko) \"
    \"Chrome/131.0.0.0 Safari/537.36\"
)
POW_TIMEOUT_NONCE = 1_000_000  # 最多尝试 1M 次 nonce
CHAT_TIMEOUT = 120.0            # Chat 请求超时 (秒)
UPLOAD_POLL_INTERVAL = 1.0     # 上传文件轮询间隔 (秒)
UPLOAD_MAX_POLLS = 30          # 最多轮询 30 次


@dataclass
class PowChallenge:
    \"\"\"PoW 挑战.\"\"\"
    algorithm: str          # \"sha256\" | \"DeepSeekHashV1\"
    challenge: str
    difficulty: int
    salt: str
    signature: str
    expire_at: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> \"PowChallenge\":
        return cls(
            algorithm=d.get(\"algorithm\", \"sha256\"),
            challenge=d.get(\"challenge\", \"\"),
            difficulty=d.get(\"difficulty\", 4),
            salt=d.get(\"salt\", \"\"),
            signature=d.get(\"signature\", \"\"),
            expire_at=d.get(\"expire_at\", 0),
        )

    def with_answer(self, answer: int, target_path: str) -> str:
        \"\"\"生成 x-ds-pow-response header 值 (base64 JSON).\"\"\"
        payload = {
            \"algorithm\": self.algorithm,
            \"challenge\": self.challenge,
            \"difficulty\": self.difficulty,
            \"salt\": self.salt,
            \"signature\": self.signature,
            \"answer\": answer,
            \"target_path\": target_path,
        }
        import base64
        return base64.b64encode(json.dumps(payload, separators=(\",\", \":\")).encode()).decode()


@dataclass
class DeepSeekWebResponse:
    \"\"\"标准化的 DeepSeek Web 响应.\"\"\"
    text: str = \"\"
    thinking: str = \"\"        # 思维链 (R1 模式)
    session_id: str = \"\"
    finish_reason: str = \"\"


@dataclass
class DeepSeekAuth:
    \"\"\"认证凭据.\"\"\"
    cookie: str = \"\"
    bearer: str = \"\"
    user_agent: str = DEFAULT_USER_AGENT
    saved_at: float = 0.0

    def is_valid(self) -> bool:
        return bool(self.cookie) and (
            \"d_id=\" in self.cookie or \"ds_session_id=\" in self.cookie
        )

    def to_dict(self) -> dict:
        return {
            \"cookie\": self.cookie,
            \"bearer\": self.bearer,
            \"user_agent\": self.user_agent,
            \"saved_at\": self.saved_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> \"DeepSeekAuth\":
        return cls(
            cookie=d.get(\"cookie\", \"\"),
            bearer=d.get(\"bearer\", \"\"),
            user_agent=d.get(\"user_agent\", DEFAULT_USER_AGENT),
            saved_at=d.get(\"saved_at\", 0.0),
        )


# ── 默认头 ──

def _default_headers(auth: DeepSeekAuth) -> dict[str, str]:
    headers = {
        \"User-Agent\": auth.user_agent or DEFAULT_USER_AGENT,
        \"Content-Type\": \"application/json\",
        \"Accept\": \"*/*\",
        \"Referer\": \"https://chat.deepseek.com/\",
        \"Origin\": \"https://chat.deepseek.com\",
        \"x-client-platform\": \"web\",
        \"x-client-version\": \"1.7.0\",
        \"x-app-version\": \"20241129.1\",
        \"x-client-locale\": \"zh_CN\",
        \"x-client-timezone-offset\": \"28800\",
    }
    if auth.cookie:
        headers[\"Cookie\"] = auth.cookie
    if auth.bearer:
        headers[\"Authorization\"] = f\"Bearer {auth.bearer}\"
    return headers


# ── PoW 求解 ──

def solve_sha256_pow(challenge: PowChallenge) -> int:
    \"\"\"求解 SHA256 PoW.\"\"\"
    prefix = challenge.salt + challenge.challenge
    target_bits = challenge.difficulty
    if target_bits > 1000:
        import math
        target_bits = int(math.log2(target_bits))

    for nonce in range(POW_TIMEOUT_NONCE):
        data = f\"{prefix}{nonce}\".encode()
        hash_hex = hashlib.sha256(data).hexdigest()
        zero_bits = _count_leading_zero_bits(hash_hex)
        if zero_bits >= target_bits:
            return nonce
    raise RuntimeError(f\"SHA256 PoW 超时: 尝试了 {POW_TIMEOUT_NONCE} 次 nonce\")


def _count_leading_zero_bits(hex_str: str) -> int:
    count = 0
    for c in hex_str:
        val = int(c, 16)
        if val == 0:
            count += 4
        else:
            count += 4 - val.bit_length()
            break
    return count


# ── DeepSeek Web API 客户端 ──

class DeepSeekWebClient:
    \"\"\"DeepSeek Web 内部 API 客户端.\"\"\"

    def __init__(self, auth: DeepSeekAuth):
        self._auth = auth
        self._http = httpx.AsyncClient(timeout=CHAT_TIMEOUT, follow_redirects=True)
        self._current_session_id: str | None = None

    async def close(self):
        await self._http.aclose()

    @property
    def auth(self) -> DeepSeekAuth:
        return self._auth

    @auth.setter
    def auth(self, new_auth: DeepSeekAuth):
        self._auth = new_auth

    async def verify_auth(self) -> bool:
        try:
            resp = await self._http.get(
                f\"{BASE_URL}/api/v0/users/current\",
                headers=_default_headers(self._auth),
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def fetch_token_from_api(self) -> str | None:
        try:
            resp = await self._http.get(
                f\"{BASE_URL}/api/v0/users/current\",
                headers=_default_headers(self._auth),
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            token = data.get(\"data\", {}).get(\"biz_data\", {}).get(\"token\", \"\")
            return token or None
        except Exception:
            return None

    async def create_pow_challenge(self, target_path: str) -> PowChallenge:
        headers = _default_headers(self._auth)
        resp = await self._http.post(
            f\"{BASE_URL}/api/v0/chat/create_pow_challenge\",
            headers=headers,
            json={\"target_path\": target_path},
        )
        if resp.status_code != 200:
            raise RuntimeError(f\"PoW 挑战失败 (HTTP {resp.status_code}): {resp.text[:200]}\")
        data = resp.json()
        challenge_data = (
            data.get(\"data\", {}).get(\"biz_data\", {}).get(\"challenge\")
            or data.get(\"data\", {}).get(\"challenge\")
            or data.get(\"challenge\")
        )
        if not challenge_data:
            raise RuntimeError(f\"PoW 响应结构异常: {json.dumps(data, ensure_ascii=False)[:300]}\")
        return PowChallenge.from_dict(challenge_data)

    async def create_chat_session(self) -> str:
        headers = _default_headers(self._auth)
        resp = await self._http.post(
            f\"{BASE_URL}/api/v0/chat_session/create\",
            headers=headers,
            json={},
        )
        if resp.status_code != 200:
            raise RuntimeError(f\"创建会话失败 (HTTP {resp.status_code}): {resp.text[:200]}\")
        data = resp.json()
        biz_data = data.get(\"data\", {}).get(\"biz_data\", {})
        session_id = biz_data.get(\"id\") or biz_data.get(\"chat_session_id\", \"\")
        if not session_id:
            raise RuntimeError(f\"会话创建响应缺少 id: {json.dumps(data, ensure_ascii=False)[:300]}\")
        self._current_session_id = session_id
        return session_id

    async def chat_completion(self, prompt, session_id=None, parent_message_id=None,
                              ref_file_ids=None, thinking_enabled=True, search_enabled=True):
        \"\"\"发送 Chat Completion 请求 (SSE 流), 返回解析后的响应.\"\"\"
        if not session_id:
            if not self._current_session_id:
                session_id = await self.create_chat_session()
            else:
                session_id = self._current_session_id

        target_path = \"/api/v0/chat/completion\"
        challenge = await self.create_pow_challenge(target_path)
        answer = solve_sha256_pow(challenge)
        pow_response = challenge.with_answer(answer, target_path)

        headers = _default_headers(self._auth)
        headers[\"x-ds-pow-response\"] = pow_response
        body = {
            \"chat_session_id\": session_id,
            \"parent_message_id\": parent_message_id,
            \"prompt\": prompt,
            \"ref_file_ids\": ref_file_ids or [],
            \"thinking_enabled\": thinking_enabled,
            \"search_enabled\": search_enabled,
        }

        result = DeepSeekWebResponse(session_id=session_id)
        async with self._http.stream(
            \"POST\", f\"{BASE_URL}/api/v0/chat/completion\",
            headers=headers, json=body,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise RuntimeError(
                    f\"Chat completion 失败 (HTTP {response.status_code}): \"
                    f\"{error_text[:300].decode('utf-8', errors='replace')}\"
                )
            await self._parse_sse_stream(response, result)
        return result

    async def _parse_sse_stream(self, response, result):
        accumulated_text, accumulated_thinking = [], []
        async for line in response.aiter_lines():
            line = line.strip()
            if not line or not line.startswith(\"data: \"):
                continue
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            event_type = event.get(\"type\", \"\")
            content = event.get(\"content\", \"\") or event.get(\"delta\", \"\") or \"\"
            if event_type == \"thinking\":
                accumulated_thinking.append(content)
            elif event_type == \"text\":
                accumulated_text.append(content)
            elif event_type == \"finished\":
                result.finish_reason = content or \"finished\"
            elif event_type == \"error\":
                raise RuntimeError(f\"DeepSeek API 错误: {content}\")
        result.text = \"\".join(accumulated_text)
        result.thinking = \"\".join(accumulated_thinking)

    async def upload_file(self, file_data: bytes, file_name: str, content_type=None) -> str:
        target_path = \"/api/v0/file/upload_file\"
        challenge = await self.create_pow_challenge(target_path)
        answer = solve_sha256_pow(challenge)
        pow_response = challenge.with_answer(answer, target_path)
        headers = _default_headers(self._auth)
        headers[\"x-ds-pow-response\"] = pow_response
        headers[\"x-file-size\"] = str(len(file_data))
        files = {\"file\": (file_name, file_data, content_type or \"image/jpeg\")}
        resp = await self._http.post(
            f\"{BASE_URL}/api/v0/file/upload_file\", headers=headers, files=files,
        )
        if resp.status_code != 200:
            raise RuntimeError(f\"文件上传失败 (HTTP {resp.status_code}): {resp.text[:200]}\")
        data = resp.json()
        file_id = data.get(\"data\", {}).get(\"biz_data\", {}).get(\"id\", \"\")
        if not file_id:
            raise RuntimeError(f\"上传响应缺少 file_id\")
        for _ in range(UPLOAD_MAX_POLLS):
            await asyncio.sleep(UPLOAD_POLL_INTERVAL)
            poll_resp = await self._http.get(
                f\"{BASE_URL}/api/v0/file/fetch_files\",
                headers=_default_headers(self._auth),
                params={\"file_ids\": file_id},
            )
            if poll_resp.status_code != 200:
                continue
            poll_data = poll_resp.json()
            files_list = poll_data.get(\"data\", {}).get(\"biz_data\", {}).get(\"files\", [])
            if not files_list:
                continue
            status = files_list[0].get(\"status\", \"\")
            if status == \"SUCCESS\":
                return file_id
            elif status == \"FAILED\":
                raise RuntimeError(f\"文件处理失败: {file_id}\")
        return file_id

    async def chat(self, prompt, images=None, search_enabled=True):
        \"\"\"便捷 Chat 方法.\"\"\"
        ref_file_ids = []
        if images:
            for img in images:
                if img.startswith((\"http://\", \"https://\", \"data:\")):
                    continue
                img_path = Path(img)
                if img_path.exists():
                    file_data = img_path.read_bytes()
                    file_id = await self.upload_file(file_data, img_path.name)
                    ref_file_ids.append(file_id)
        if ref_file_ids:
            search_enabled = False
        return await self.chat_completion(
            prompt=prompt, ref_file_ids=ref_file_ids or None,
            search_enabled=search_enabled, thinking_enabled=True,
        )
```

### 3.2 `context_window_manager.py` — 上下文窗口管理

```python
\"\"\"ContextWindowManager —— DeepSeek Web 对话上下文窗口管理.

核心职责:
  1. 追踪每个对话 session 的状态 (消息数 / 估算 token / 上下文上限)
  2. 判断上下文窗口是否接近满 (≥85%)
  3. 满时自动压缩历史 → 创建新 session → 注入摘要
  4. 报错时自动故障恢复 → 压缩 + 新 session
  5. 保证多轮对话记忆不因窗口满而断开
\"\"\"

import asyncio, logging, time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .deepseek_web_client import DeepSeekWebClient, DeepSeekWebResponse

logger = logging.getLogger(\"hyperspace.context_window\")

DEFAULT_CONTEXT_LIMIT = 64_000
COMPRESS_THRESHOLD = 0.85
MAX_CONSECUTIVE_FAILURES = 3
TOKEN_EST_RATIO = 0.3

_COMPRESS_PROMPT = \"\"\"你是对话摘要助手。请阅读以下对话记录，提取所有关键信息，包括：
- 用户的需求和问题
- 你给出的回答要点
- 已做的决策和结论
- 待办事项
- 重要上下文（代码片段、配置、路径等）

用简洁的中文压缩到 300 字以内。只输出摘要，不要额外说明。

对话记录：
{history}
\"\"\"


@dataclass
class SessionState:
    session_id: str
    message_count: int = 0
    estimated_tokens: int = 0
    context_limit: int = DEFAULT_CONTEXT_LIMIT
    summary: str = \"\"
    created_at: float = 0.0
    last_active: float = 0.0
    consecutive_failures: int = 0


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) * TOKEN_EST_RATIO))


class ContextWindowManager:
    \"\"\"DeepSeek Web 对话上下文管理器.\"\"\"

    def __init__(
        self,
        web_client: DeepSeekWebClient,
        compress_fn: Callable[[str], Awaitable[str]] | None = None,
        context_limit: int = DEFAULT_CONTEXT_LIMIT,
    ):
        self._web = web_client
        self._compress_fn = compress_fn
        self._context_limit = context_limit
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def chat(self, session_key: str, prompt: str, images=None,
                   search_enabled: bool = True) -> DeepSeekWebResponse:
        \"\"\"发送消息, 自动管理上下文窗口.\"\"\"
        async with self._lock:
            if not session_key:
                return await self._new_session_chat(session_key, prompt, images, search_enabled)

            state = self._sessions.get(session_key)
            if state is None:
                return await self._first_message(session_key, prompt, images, search_enabled)

            if self._should_compress(state, prompt):
                return await self._compress_and_restart(
                    session_key, prompt, images, search_enabled
                )

            try:
                resp = await self._web.chat_completion(
                    prompt=prompt, session_id=state.session_id,
                    search_enabled=search_enabled, thinking_enabled=True,
                )
                self._update_state(state, prompt, resp.text)
                state.consecutive_failures = 0
                return resp
            except Exception as e:
                state.consecutive_failures += 1
                if state.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(\"DeepSeek Web 连续调用失败, 触发降级\")
                return await self._compress_and_restart(
                    session_key, prompt, images, search_enabled
                )

    def _should_compress(self, state: SessionState, new_prompt: str) -> bool:
        new_est = state.estimated_tokens + _estimate_tokens(new_prompt)
        threshold = int(state.context_limit * COMPRESS_THRESHOLD)
        return new_est >= threshold

    async def _compress_and_restart(self, session_key, prompt, images, search_enabled):
        state = self._sessions.get(session_key)
        summary = state.summary if state else \"\"

        if self._compress_fn and state:
            try:
                history_text = await self._build_history_text(state)
                new_summary = await self._compress_fn(
                    _COMPRESS_PROMPT.format(history=history_text)
                )
                summary = new_summary.strip() if new_summary and len(new_summary) > 10 else summary
            except Exception as e:
                logger.warning(f\"压缩失败: {e}\")
                if not summary:
                    summary = \"[对话历史摘要已丢失]\"

        new_session_id = await self._web.create_chat_session()
        await self._web.chat_completion(
            prompt=f\"[上下文摘要] 之前对话的关键信息：{summary}\",
            session_id=new_session_id, thinking_enabled=False,
        )
        resp = await self._web.chat_completion(
            prompt=prompt, session_id=new_session_id, searching=search_enabled,
            thinking_enabled=True,
        )
        new_state = SessionState(
            session_id=new_session_id, message_count=2,
            estimated_tokens=_estimate_tokens(summary) + _estimate_tokens(prompt) + _estimate_tokens(resp.text),
            context_limit=self._context_limit, summary=summary,
            created_at=time.time(), last_active=time.time(),
        )
        if session_key:
            self._sessions[session_key] = new_state
        return resp

    async def _first_message(self, session_key, prompt, images, search_enabled):
        state = self._sessions.get(session_key)
        full_prompt = prompt
        if state and state.summary:
            full_prompt = f\"[上下文摘要] {state.summary}\\n\\n{prompt}\"
        return await self._new_session_chat(session_key, full_prompt, images, search_enabled)

    async def _new_session_chat(self, session_key, prompt, images, search_enabled):
        session_id = await self._web.create_chat_session()
        resp = await self._web.chat_completion(
            prompt=prompt, session_id=session_id,
            search_enabled=search_enabled, thinking_enabled=True,
        )
        state = SessionState(
            session_id=session_id, message_count=1,
            estimated_tokens=_estimate_tokens(prompt) + _estimate_tokens(resp.text),
            context_limit=self._context_limit, created_at=time.time(), last_active=time.time(),
        )
        old = self._sessions.get(session_key)
        if old and old.summary:
            state.summary = old.summary
        if session_key:
            self._sessions[session_key] = state
        return resp

    def _update_state(self, state, prompt, response):
        state.message_count += 1
        state.estimated_tokens += _estimate_tokens(prompt) + _estimate_tokens(response)
        state.last_active = time.time()

    async def _build_history_text(self, state):
        parts = [f\"消息数: {state.message_count}\", f\"Token: {state.estimated_tokens}\"]
        if state.summary:
            parts.append(f\"已有摘要: {state.summary}\")
        return \"\\n\".join(parts)

    def get_session(self, session_key): return self._sessions.get(session_key)
    def list_sessions(self): return dict(self._sessions)
    def clear_session(self, key): self._sessions.pop(key, None)
    def clear_all(self): self._sessions.clear()
    @property
    def active_count(self): return len(self._sessions)
```

### 3.3 `web_auth.py` — 浏览器凭据提取

```python
\"\"\"Web Auth —— 从 Chrome 浏览器提取 DeepSeek Web 登录凭据.\"\"\"

import asyncio, json, logging, os, sys, time
from pathlib import Path

logger = logging.getLogger(\"hyperspace.web_auth\")
_PKG_DIR = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PKG_DIR / \"data\"
_AUTH_FILE = _DATA_DIR / \"deepseek_web_auth.json\"


def load_saved_auth() -> dict | None:
    path = _AUTH_FILE
    if not path.exists():
        return None
    try:
        with path.open(\"r\", encoding=\"utf-8\") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_auth(auth: dict) -> None:
    _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    auth[\"saved_at\"] = time.time()
    with _AUTH_FILE.open(\"w\", encoding=\"utf-8\") as f:
        json.dump(auth, f, ensure_ascii=False, indent=2)
    logger.info(f\"凭据已保存\")


def is_auth_valid(auth: dict | None = None) -> bool:
    if auth is None:
        auth = load_saved_auth()
    if not auth:
        return False
    cookie = auth.get(\"cookie\", \"\")
    return bool(cookie) and (\"d_id=\" in cookie or \"ds_session_id=\" in cookie)


async def extract_from_browser(cdp_port: int = 9222, timeout: float = 300.0) -> dict:
    \"\"\"连接到 Chrome CDP, 提取 DeepSeek 凭据.\"\"\"
    import playwright.async_api as pw
    cdp_url = f\"http://127.0.0.1:{cdp_port}\"

    ws_url = None
    for i in range(10):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f\"{cdp_url}/json/version\")
                if resp.status_code == 200:
                    ws_url = resp.json().get(\"webSocketDebuggerUrl\")
                    if ws_url:
                        break
        except Exception:
            pass
        await asyncio.sleep(0.5)

    if not ws_url:
        raise RuntimeError(f\"无法连接到 Chrome CDP (端口 {cdp_port})\")

    async with await pw.chromium.connect_over_cdp(ws_url) as browser:
        context = browser.contexts[0] or await browser.new_context()
        page = None
        for p in context.pages:
            if \"deepseek.com\" in p.url:
                page = p
                await p.bring_to_front()
                break
        if not page:
            page = await context.new_page()

        existing_cookies = await context.cookies([\"https://chat.deepseek.com\", \"https://deepseek.com\"])
        cookie_str = \"; \".join(f\"{c.name}={c.value}\" for c in existing_cookies) if existing_cookies else \"\"
        has_session = (\"d_id=\" in cookie_str or \"ds_session_id=\" in cookie_str) and len(cookie_str) > 10
        bearer = \"\"
        user_agent = \"\"

        if has_session:
            logger.info(\"发现已有 DeepSeek 会话\")
            user_agent = await page.evaluate(\"navigator.userAgent\")
            try:
                resp = await page.request.get(
                    \"https://chat.deepseek.com/api/v0/users/current\",
                    headers={\"Cookie\": cookie_str},
                )
                if resp.ok:
                    data = await resp.json()
                    bearer = data.get(\"data\", {}).get(\"biz_data\", {}).get(\"token\", \"\")
            except Exception:
                pass
            return {\"cookie\": cookie_str, \"bearer\": bearer, \"user_agent\": user_agent}

        logger.info(\"未检测到登录, 导航到 DeepSeek 等待登录...\")
        await page.goto(\"https://chat.deepseek.com\")
        user_agent = await page.evaluate(\"navigator.userAgent\")
        print(\"\\n[web_auth] 请在打开的 Chrome 窗口中登录 DeepSeek 账号\\n\", flush=True)

        captured_bearer = []
        resolved = asyncio.Event()

        async def on_request(request):
            url = request.url
            if \"/api/v0/\" in url:
                auth_h = request.headers.get(\"authorization\", \"\")
                if auth_h.startswith(\"Bearer \") and not captured_bearer:
                    captured_bearer.append(auth_h[7:])
                    resolved.set()

        page.on(\"request\", on_request)
        try:
            await asyncio.wait_for(resolved.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(\"登录等待超时 (5 分钟)\")

        final_cookies = await context.cookies([\"https://chat.deepseek.com\", \"https://deepseek.com\"])
        final_cookie_str = \"; \".join(f\"{c.name}={c.value}\" for c in final_cookies) if final_cookies else \"\"
        return {\"cookie\": final_cookie_str, \"bearer\": captured_bearer[0] if captured_bearer else bearer, \"user_agent\": user_agent}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=\"DeepSeek Web 凭据管理\")
    parser.add_argument(\"--extract\", action=\"store_true\", help=\"从浏览器提取凭据\")
    parser.add_argument(\"--status\", action=\"store_true\", help=\"查看凭据状态\")
    parser.add_argument(\"--cdp-port\", type=int, default=9222, help=\"Chrome CDP 端口\")
    args = parser.parse_args()

    if args.status:
        auth = load_saved_auth()
        if auth and is_auth_valid(auth):
            print(f\"凭据状态: 有效\")
        else:
            print(\"无有效凭据, 请运行 --extract\")
    elif args.extract:
        auth = asyncio.run(extract_from_browser(cdp_port=args.cdp_port))
        if auth and auth.get(\"cookie\"):
            save_auth(auth)
            print(f\"凭据已保存\")
        else:
            print(\"凭据提取失败\")
    else:
        parser.print_help()

if __name__ == \"__main__\":
    main()
```

### 3.4 `hybrid_router.py` — 核心路由决策引擎

(完整源码见项目文件 `hyperspace/hybrid_engine/hybrid_router.py`)

关键接口：

```python
class HybridRouter:
    async def execute(self, prompt, images=None, context=None, mode="auto", session_key="") -> ProcessedResult

    def _route(self, profile, mode) -> RoutingDecision:
        # 8 级优先级规则匹配

    async def _call_web(self, prompt, images, context, session_key="") -> tuple[str, str]:
        # 通过 ContextWindowManager 调用 DeepSeek Web

    async def _compress_via_api(self, text) -> str:
        # 用 DeepSeek API 或 Zhipu 做上下文压缩摘要
```

### 3.5 `task_analyzer.py` — 任务特征分析

判定维度:
- `has_image`: images 非空
- `is_long`: 字符 > 5000
- `needs_search`: 搜索相关关键词 (搜索/查找/最新/search/find/latest)
- `needs_planning`: 规划相关 (计划/方案/步骤/大纲/plan/strategy)
- `needs_coding`: 代码相关 (```/def /class /function /import /算法/排序等)
- `needs_translation`: 翻译相关 (翻译/译成/translate)
- `needs_structured_output`: 结构化输出 (JSON/表格/CSV/XML/YAML)

### 3.6 `fallback.py` — 降级管理

- 降级链: `DeepSeek Web → DeepSeek API → 智谱 GLM → 友好错误`
- 指数退避重试: 100ms → 200ms → 400ms
- 异常分类: timeout / ratelimit / connection / auth / empty_response

### 3.7 `health_checker.py` — 健康检查

- DeepSeek Web: 检查 `deepseek_web_auth.json` 凭据有效性
- DeepSeek API: HTTP 探测 `api.deepseek.com/v1/models`
- Zhipu: 始终视为可用 (直接 API 调用)
- 缓存 60 秒

### 3.8 `result_processor.py` — 结果后处理

- 提取 `<thinking>` / `<details>` / `[思考]` 标签作为思维链
- 分离思维链与最终回答

---

## 四、配置文件

### 4.1 `config/hybrid_config.yaml`

```yaml
routing:
  default_executor: "deepseek_web"
  fallback_order: ["deepseek_web", "deepseek_api", "zhipu"]
  rules:
    - condition: "has_image"           -> "deepseek_web"
    - condition: "needs_search"        -> "deepseek_web"
    - condition: "needs_planning"      -> "deepseek_web"
    - condition: "is_long"             -> "deepseek_web"
    - condition: "needs_coding"        -> "deepseek_api"
    - condition: "needs_translation"   -> "deepseek_api"
    - condition: "needs_structured_output" -> "deepseek_api"

executors:
  deepseek_web:
    model: "deepseek-chat"
    timeout: 120
    search_enabled: true
    thinking_enabled: true
  deepseek_api:
    provider: "deepseek"
    base_url: "https://api.deepseek.com"
    model: "deepseek-chat"
    timeout: 60
  zhipu:
    provider: "zhipu"
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4.7-flash"
    timeout: 30
```

### 4.2 `config/providers.yaml` (旧路由)

```yaml
free_text:
  - { provider: zhipu, base_url: "https://open.bigmodel.cn/api/paas/v4/", model: "glm-4.7-flash", key_env: "ZHIPU_API_KEY" }
free_vision:
  - { provider: zhipu, base_url: "https://open.bigmodel.cn/api/paas/v4/", model: "glm-4.6v-flash", key_env: "ZHIPU_API_KEY" }
cheap_capable:
  - { provider: deepseek, base_url: "https://api.deepseek.com", model: "deepseek-chat", key_env: "DEEPSEEK_API_KEY" }
```

---

## 五、MCP 接入配置

### 5.1 Reasonix — `D:\Reasonix\.mcp.json`

```json
{
  "cline.mcpServers": {
    "hyperspace": {
      "command": "python",
      "args": ["D:\\Reasonix\\HyperSpace\\hyperspace\\server.py"],
      "env": { "PYTHONIOENCODING": "utf-8" },
      "autoApprove": ["*"]
    }
  }
}
```

### 5.2 Claude Code — `HyperSpace\.mcp.json`

```json
{
  "mcpServers": {
    "hyperspace": {
      "command": "python",
      "args": ["D:\\Reasonix\\HyperSpace\\hyperspace\\server.py"],
      "env": { "PYTHONIOENCODING": "utf-8" },
      "autoApprove": ["*"]
    }
  }
}
```

### 5.3 VS Code Copilot — `HyperSpace\.vscode\mcp.json`

```json
{
  "mcpServers": {
    "hyperspace": {
      "command": "python",
      "args": ["D:\\Reasonix\\HyperSpace\\hyperspace\\server.py"],
      "env": { "PYTHONIOENCODING": "utf-8" },
      "autoApprove": ["*"]
    }
  }
}
```

### 5.4 ZCode

ZCode 为独立 Electron 桌面应用，不支持 MCP 协议。通过 Reasonix zcode-bridge (AHK + pywinauto) 桥接。

---

## 六、`hyperspace_query` 工具签名

```json
{
  "name": "hyperspace_query",
  "parameters": {
    "prompt": "string (必填)",
    "images": "string[] (可选, 本地路径/URL/base64)",
    "context": "string (可选, system message)",
    "mode": "auto | free_text | free_vision | cheap_capable | premium | force_web | force_api | force_zhipu",
    "session_id": "string (可选, 多轮对话标识)"
  }
}
```

### 响应格式

```
[最终回答文本]

---
[hyperspace] 引擎: deepseek_web/deepseek-chat  规划: (思维链摘要)
```

### 使用示例

| 场景 | prompt | mode | session_id |
|------|--------|------|------------|
| 简单问答 | "你好" | auto (默认) | — |
| 多轮对话 第1轮 | "帮我规划项目" | auto | "chat-001" |
| 多轮对话 第2轮 | "细节再展开" | auto | "chat-001" ← 自动续上下文 |
| 强制 Web | 同上 | force_web | — |
| 代码生成 | "写快排" | auto (自动路由到 API) | — |

---

## 七、测试

```bash
# 运行全部测试
cd D:\Reasonix\HyperSpace
python -m pytest tests/ -v

# 结果: 64 passed (25 旧 + 39 新混合引擎)
```

测试覆盖:
- `TestTaskAnalyzer` (13): 各类特征判定
- `TestHybridRouter` (14): 路由决策、force 模式、优先级
- `TestFallbackManager` (5): 降级链、重试、异常分类
- `TestResultProcessor` (7): 思维链提取、纯文本、空响应
- 旧测试 `test_router.py` (16) + `test_providers.py` (9)

---

## 八、使用流程

### 8.1 首次设置

```bash
# 1. 安装依赖
pip install mcp openai pyyaml python-dotenv httpx

# 2. (可选) 安装 Playwright 用于浏览器凭据提取
pip install playwright
playwright install chromium

# 3. 配置 .env
echo ZHIPU_API_KEY=你的key > .env
echo DEEPSEEK_API_KEY=你的key >> .env

# 4. 提取 DeepSeek Web 凭据
#    先启动 Chrome 调试模式:
#    chrome.exe --remote-debugging-port=9222
#    登录 chat.deepseek.com 后运行:
python -m hyperspace.hybrid_engine.web_auth --extract

# 5. 查看凭据状态
python -m hyperspace.hybrid_engine.web_auth --status
```

### 8.2 日常使用

Agent 调用 `hyperspace_query` 工具即可。DeepSeek Web 端自动使用已保存的凭据。

### 8.3 会话管理

- **传 `session_id`** → 多轮对话, 上下文窗口满时自动压缩 + 新 session
- **不传 `session_id`** → 每次新建 session (无状态模式, 适合单次问答)

---

## 九、关键决策记录

| 决策 | 方案 | 理由 |
|------|------|------|
| 不求助于 OpenClaw/FreeLLMAPI | 自研 DeepSeek Web 客户端 | 无外部依赖, 全 Python 实现 |
| PoW 算法 | SHA256 (自实现) | DeepSeek 主用 SHA256; DeepSeekHashV1 需 WASM 暂不实现 |
| API 调用方式 | httpx.AsyncClient | 项目已有 httpx 依赖, 流式支持好 |
| Auth 提取 | Playwright CDP | 已有 playwright 可选依赖, 比手动填 Cookie 更可靠 |
| 上下文管理 | ContextWindowManager | 85% 阈值触发压缩 + 摘要注入 |
| 降级链 | Web → API → Zhipu → Error | 优先级: 零成本 > 低成本 > 免费兜底 > 失败 |
| MCP 配置 | 三份独立 .mcp.json | 四种 Agent 有不同的配置键名和文件路径 |

---

*本导出文档由会话内容自动生成，覆盖 HyperSpace v2.0 全部技术细节。*
