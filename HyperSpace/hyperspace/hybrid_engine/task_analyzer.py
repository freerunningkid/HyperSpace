"""TaskProfile —— 任务特征分析与判定.

Analyze prompt + context to build a structured profile used by HybridRouter
to decide which executor should handle the request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TaskProfile:
    """分析后的任务特征画像."""

    is_long: bool = False               # prompt > 5000 chars
    needs_search: bool = False          # 需要联网搜索
    needs_planning: bool = False         # 需要规划/大纲
    needs_coding: bool = False           # 需要代码生成
    needs_translation: bool = False      # 需要翻译
    needs_structured_output: bool = False  # 需要 JSON/表格
    has_image: bool = False              # 包含图片

    def __bool__(self) -> bool:
        """至少一个特征为 True."""
        return any((
            self.is_long, self.needs_search, self.needs_planning,
            self.needs_coding, self.needs_translation,
            self.needs_structured_output, self.has_image,
        ))

    @property
    def complexity_score(self) -> int:
        """特征计数 (粗略复杂度)"""
        return sum(map(int, (
            self.is_long, self.needs_search, self.needs_planning,
            self.needs_coding, self.needs_translation,
            self.needs_structured_output, self.has_image,
        )))


# ── 关键词 / 正则规则 ───────────────────────────────────────────────

# 搜索信号
_SEARCH_PATTERNS = [
    r"搜索", r"查找", r"最新",
    r"search", r"find", r"latest",
    r"新闻", r"news", r"news?",
    r"当前", r"今天", r"today",
    r"实时", r"realtime",
]

# 规划信号
_PLANNING_PATTERNS = [
    r"计划", r"方案", r"步骤", r"大纲",
    r"策划", r"规划",
    r"plan", r"strategy", r"steps", r"outline",
    r"架构", r"设计", r"architecture", r"design",
    r"路线图", r"roadmap",
    r"框架", r"framework",
]

# 编码信号 (含代码围栏)
_CODE_PATTERNS = [
    r"```",                       # 代码围栏
    r"def\s+\w+\s*\(",            # Python 函数定义
    r"class\s+\w+",               # 类定义
    r"function\s+\w+\s*\(",       # JS 函数定义
    r"import\s+\w+",              # 导入
    r"const\s+\w+\s*=",           # JS 变量
    r"let\s+\w+\s*=",             # JS 变量
    r"var\s+\w+\s*=",             # 旧 JS
    r"#include",                  # C/C++
    r"fn\s+\w+",                  # Rust
    r"代码", r"函数", r"debug",
    r"实现", r"implement",
    r"编写", r"写一个", r"写个",
    r"修复", r"fix", r"bug",
    r"重构", r"refactor",
    r"调试",
    r"algorithm",                 # 算法
    r"sort\b",                    # 排序
    r"write\s+(a|an|the)\s+\w+",  # write a function/class/program
    r"create\s+(a|an|the)\s+\w+", # create a function/class
    r"build\s+(a|an|the)\s+\w+",  # build a ...
    r"generate\s+\w+",            # generate code/number
    r"\w+\.py\b",                 # .py file reference
    r"\w+\.js\b",                 # .js file reference
]

# 翻译信号
_TRANSLATION_PATTERNS = [
    r"翻译", r"译成",
    r"translate", r"translate\s+(to|into)",
    r"翻译为", r"翻译成",
]

# 结构化输出
_STRUCTURED_PATTERNS = [
    r"JSON", r"json",
    r"表格", r"table",
    r"结构化", r"structured",
    r"CSV", r"csv",
    r"XML", r"xml",
    r"YAML", r"yaml",
    r"列表", r"list",
    r"格式化为", r"format",
]

# 长度阈值
_LONG_THRESHOLD = 5000


def analyze_task(
    prompt: str,
    images: list[str] | None = None,
    context: str | None = None,
) -> TaskProfile:
    """分析 prompt + context, 返回 TaskProfile."""

    profile = TaskProfile()

    # ── 图片判定 ──
    profile.has_image = bool(images and len(images) > 0)

    # 合并正文 (prompt + context) 用于文本分析
    body = prompt
    if context:
        body = context + "\n" + prompt

    # ── 长度判定 ──
    profile.is_long = len(body) > _LONG_THRESHOLD

    # ── 关键词/正则匹配 (大小写不敏感) ──
    low = body.lower()

    profile.needs_search = _any_match(_SEARCH_PATTERNS, body, low)
    profile.needs_planning = _any_match(_PLANNING_PATTERNS, body, low)
    profile.needs_coding = _any_match(_CODE_PATTERNS, body, low)
    profile.needs_translation = _any_match(_TRANSLATION_PATTERNS, body, low)
    profile.needs_structured_output = _any_match(_STRUCTURED_PATTERNS, body, low)

    return profile


def _any_match(
    patterns: list[str],
    body: str,
    low: str,
) -> bool:
    """任一模式匹配 body (先原文, 再小写)."""
    for pat in patterns:
        try:
            if re.search(pat, body):
                return True
            if pat.isascii() and re.search(pat, low):
                return True
        except re.error:
            # 不合法的正则就当普通子串
            if pat in body or pat in low:
                return True
    return False
