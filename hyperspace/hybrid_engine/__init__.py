"""Hybrid Engine —— 混合推理引擎 v2.0 (原生 DeepSeek Web 实现).

三层: DeepSeek Web (原生 Python 客户端) × DeepSeek API → 智谱 GLM (兜底).
"""

from __future__ import annotations

from .hybrid_router import HybridRouter

__all__ = ["HybridRouter"]
