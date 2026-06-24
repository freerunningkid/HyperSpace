"""DeepSeek Web Provider —— 原生 Python 客户端适配器。

将现有 DeepSeekWebClient + ContextWindowManager 封装为 BaseProvider 接口。
不重写 PoW/SSE/文件上传逻辑，只做适配层。

对应设计文档 §8。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)

logger = logging.getLogger("hyperspace.providers.deepseek_web")


class DeepSeekWebProvider(BaseProvider):
    """DeepSeek Web 原生 Provider。

    内部委托给：
      - DeepSeekWebClient（HTTP + PoW + SSE）
      - ContextWindowManager（上下文追踪与压缩）

    能力：
      - text, vision_understanding, file_upload, web_search
      - streaming, planning, long_context
    """

    def __init__(
        self,
        web_client_factory=None,
        context_manager_factory=None,
        compress_fn=None,
    ):
        self.id = "deepseek_web"
        self.type = ProviderType.WEB
        self.capabilities = ProviderCapabilities(
            text=True,
            vision_understanding=True,
            file_upload=True,
            web_search=True,
            streaming=True,
            structured_output=False,
            planning=True,
            long_context=True,
        )
        self.cost_tier = CostTier.FREE

        self._web_client_factory = web_client_factory
        self._context_manager_factory = context_manager_factory
        self._compress_fn = compress_fn

        # 延迟初始化
        self._web_client = None
        self._ctx_mgr = None

    # ── 内部初始化 ──────────────────────────────────────────────

    def _ensure_clients(self):
        """确保 web_client 和 ctx_mgr 已初始化。"""
        if self._web_client is not None and self._ctx_mgr is not None:
            # 检查 auth 是否仍有效
            if hasattr(self._web_client, 'auth') and self._web_client.auth.is_valid():
                return

            # auth 过期，尝试重新加载
            try:
                from ..hybrid_engine import web_auth as web_auth_mod
                auth_data = web_auth_mod.load_saved_auth()
                if auth_data:
                    from ..hybrid_engine.deepseek_web_client import DeepSeekAuth
                    auth = DeepSeekAuth.from_dict(auth_data)
                    if auth.is_valid():
                        self._web_client.auth = auth
                        logger.info("DeepSeek Web auth 已刷新")
                        return
            except Exception as e:
                logger.warning(f"刷新 DeepSeek Web auth 失败: {e}")

        # 工厂注入（测试用）
        if self._web_client_factory and self._context_manager_factory:
            self._web_client = self._web_client_factory()
            self._ctx_mgr = self._context_manager_factory(
                web_client=self._web_client,
                compress_fn=self._compress_fn,
            )
            return

        # 从凭据文件初始化
        try:
            from ..hybrid_engine import web_auth as web_auth_mod
            auth_data = web_auth_mod.load_saved_auth()
            if not auth_data:
                raise RuntimeError("无 DeepSeek Web 凭据 (请先运行 web_auth --extract)")

            from ..hybrid_engine.deepseek_web_client import DeepSeekAuth, DeepSeekWebClient
            auth = DeepSeekAuth.from_dict(auth_data)
            if not auth.is_valid():
                raise RuntimeError("DeepSeek Web 凭据无效或已过期")

            self._web_client = DeepSeekWebClient(auth)

            from ..hybrid_engine.context_window_manager import ContextWindowManager
            self._ctx_mgr = ContextWindowManager(
                web_client=self._web_client,
                compress_fn=self._compress_fn,
            )
            logger.info("DeepSeek Web 客户端 + 上下文管理器已初始化")
        except ImportError as e:
            raise RuntimeError(f"DeepSeek Web 依赖不可用: {e}")
        except Exception as e:
            raise RuntimeError(f"DeepSeek Web 初始化失败: {e}")

    # ── 健康检查 ────────────────────────────────────────────────

    async def health_check(self) -> ProviderHealth:
        """轻量健康检查：使用 web_auth.is_auth_valid() 验证凭据。"""
        try:
            from ..hybrid_engine import web_auth as web_auth_mod
            auth_data = web_auth_mod.load_saved_auth()
            if not auth_data:
                return ProviderHealth(
                    status=ProviderStatus.UNAVAILABLE,
                    score=15.0,
                    message="无 DeepSeek Web 凭据文件 (需运行 web_auth --extract)",
                )

            # 检查关键字段
            required_fields = ("cookie", "bearer", "user_agent")
            missing = [f for f in required_fields if not auth_data.get(f)]
            if missing:
                return ProviderHealth(
                    status=ProviderStatus.UNAVAILABLE,
                    score=20.0,
                    message=f"凭据不完整，缺少字段: {', '.join(missing)}",
                )

            # 使用标准验证（DeepSeekAuth.is_valid 检查 bearer 长度 + cookie）
            from ..hybrid_engine.deepseek_web_client import DeepSeekAuth
            auth = DeepSeekAuth.from_dict(auth_data)
            if auth.is_valid():
                return ProviderHealth(
                    status=ProviderStatus.AVAILABLE,
                    score=87.0,
                    message="DeepSeek Web 凭据有效",
                )
            else:
                return ProviderHealth(
                    status=ProviderStatus.DEGRADED,
                    score=40.0,
                    message="凭据文件存在但验证未通过，可能需要重新提取",
                )

        except ImportError:
            return ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=10.0,
                message="DeepSeek Web 依赖模块不可用",
            )
        except Exception as e:
            return ProviderHealth(
                status=ProviderStatus.UNAVAILABLE,
                score=0.0,
                message=f"健康检查失败: {e}",
                last_error=str(e)[:200],
            )

    # ── 核心调用 ────────────────────────────────────────────────

    async def chat(self, request: ProviderRequest) -> ProviderResponse:
        """通过 ContextWindowManager 发送 chat 请求。

        参数映射：
          - request.prompt + request.context → 合并 prompt
          - request.images → images
          - request.files → files（暂由 ctx_mgr 处理上传）
          - request.session_id → session_key
          - request.web_mode → web_mode
          - request.search_enabled → search_enabled
        """
        try:
            self._ensure_clients()
        except Exception as e:
            return ProviderResponse(
                answer="",
                provider_id=self.id,
                provider_type=self.type,
                error=str(e),
            )

        if not self._web_client or not self._ctx_mgr:
            return ProviderResponse(
                answer="",
                provider_id=self.id,
                provider_type=self.type,
                error="DeepSeek Web 客户端未初始化",
            )

        # 合并 context 和 prompt
        if request.context:
            full_prompt = f"{request.context}\n\n{request.prompt}"
        else:
            full_prompt = request.prompt

        # 处理文件上传
        files = request.files or []
        images = request.images or []

        try:
            # 如果有文件需要上传，先上传并获取 ref_file_ids
            if files:
                # 合并 images 和 files
                all_attachments = list(dict.fromkeys(images + files))
                resp = await self._ctx_mgr.chat(
                    session_key=request.session_id or "",
                    prompt=full_prompt,
                    images=all_attachments,
                    web_mode=request.web_mode or "auto",
                    search_enabled=request.search_enabled if request.search_enabled is not None else True,
                    thinking_enabled=True,
                )
            elif images:
                resp = await self._ctx_mgr.chat(
                    session_key=request.session_id or "",
                    prompt=full_prompt,
                    images=images,
                    web_mode=request.web_mode or "auto",
                    search_enabled=request.search_enabled if request.search_enabled is not None else True,
                    thinking_enabled=True,
                )
            else:
                resp = await self._ctx_mgr.chat(
                    session_key=request.session_id or "",
                    prompt=full_prompt,
                    images=None,
                    web_mode=request.web_mode or "auto",
                    search_enabled=request.search_enabled if request.search_enabled is not None else True,
                    thinking_enabled=True,
                )
        except RuntimeError as e:
            if "连续失败" in str(e):
                raise  # 让 Router 层触发 fallback
            return ProviderResponse(
                answer="",
                provider_id=self.id,
                provider_type=self.type,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"DeepSeek Web chat 失败: {e}")
            return ProviderResponse(
                answer="",
                provider_id=self.id,
                provider_type=self.type,
                error=str(e),
            )

        # 合并 thinking + answer
        if resp.thinking:
            full_text = f"{resp.thinking}\n\n{resp.text}"
        else:
            full_text = resp.text

        return ProviderResponse(
            answer=full_text,
            provider_id=self.id,
            provider_type=self.type,
            model="deepseek-chat",
            raw_metadata={
                "web_mode": request.web_mode or "auto",
                "search_enabled": request.search_enabled,
                "session_id": request.session_id or "",
            },
        )

    async def upload_file(self, request: ProviderRequest) -> Any:
        """上传文件到 DeepSeek Web。"""
        try:
            self._ensure_clients()
        except Exception as e:
            return {"error": str(e)}

        if not self._web_client:
            return {"error": "客户端未初始化"}

        try:
            result = await self._web_client.upload_file(
                files=request.files or [],
            )
            return result
        except Exception as e:
            return {"error": str(e)}

    async def close_session(self, session_id: str) -> None:
        """关闭 DeepSeek Web 会话（如有必要）。"""
        if self._web_client and hasattr(self._web_client, 'close_session'):
            try:
                await self._web_client.close_session(session_id)
            except Exception:
                pass
