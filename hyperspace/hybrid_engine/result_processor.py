"""ResultProcessor —— 横向统一格式处理.

标准化来自不同执行器的返回格式:
- OpenClaw (DeepSeek Web): 可含 <thinking> 思维链标签
- FreeLLMAPI (DeepSeek API): 标准 OpenAI 格式
- 智谱 GLM: 标准 OpenAI 格式
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ProcessedResult:
    """标准化后的执行结果."""

    answer: str                     # 最终回复 (过滤掉思维链)
    plan: str = ""                  # 思维链 / 计划 (如有)
    raw_response: str = ""          # 原始完整响应
    used_executor: str = ""         # 实际执行的引擎
    used_model: str = ""            # 实际使用的模型


class ResultProcessor:
    """统一的后处理: 提取思维链, 分离最终回答."""

    # OpenClaw 可能返回的思维链标签
    THINKING_PATTERNS = [
        (r"<thinking>(.*?)</thinking>", re.DOTALL),
        (r"<details>(.*?)</details>", re.DOTALL),
        (r"\[思考\](.*?)\[/思考\]", re.DOTALL),
    ]

    # 对 FreeLLMAPI/智谱, 尝试提取思维链 (如 链式思考 CoT)
    COT_PATTERNS = [
        (r"步骤\d+[：:](.*?)(?=步骤\d|$)", re.DOTALL),
        (r"首先，(.*?)(?=其次|然后|最后|$)", re.DOTALL),
    ]

    @classmethod
    def process(
        cls,
        raw_text: str,
        executor_name: str = "",
        model_name: str = "",
    ) -> ProcessedResult:
        """处理原始响应, 返回标准化结果."""
        result = ProcessedResult(
            answer="",
            raw_response=raw_text,
            used_executor=executor_name,
            used_model=model_name,
        )

        if not raw_text:
            result.answer = ""
            return result

        # 1. 尝试提取思维链标签
        plan_parts = []
        remaining = raw_text

        for pattern, flags in cls.THINKING_PATTERNS:
            matches = list(re.finditer(pattern, raw_text, flags))
            for m in matches:
                plan_parts.append(m.group(1).strip())
                # 从 remaining 中移除思维链内容
                remaining = remaining.replace(m.group(0), "")

        if plan_parts:
            result.plan = "\n".join(plan_parts)

        # 2. 清理后的剩余文本作为答案
        answer = remaining.strip()
        # 去除可能残留的空行/分隔符
        answer = re.sub(r"\n{3,}", "\n\n", answer)
        answer = answer.strip()

        # 3. 如果没有思维链标签, 尝试 CoT 模式
        if not plan_parts and executor_name in ("deepseek_api", "zhipu"):
            cot_plan = cls._extract_cot(answer)
            if cot_plan:
                result.plan = cot_plan

        result.answer = answer if answer else (plan_parts[0] if plan_parts else raw_text)
        return result

    @classmethod
    def _extract_cot(cls, text: str) -> str:
        """尝试提取 Chain-of-Thought 风格的步骤."""
        parts = []
        for pattern, flags in cls.COT_PATTERNS:
            matches = list(re.finditer(pattern, text, flags))
            for m in matches:
                parts.append(m.group(1).strip())
        return "\n".join(parts) if parts else ""
