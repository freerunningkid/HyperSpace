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
    has_file: bool = False               # 包含图片/文件/上传意图
    suggested_web_mode: str = "auto"    # quick / expert / vision / auto
    explicit_web_mode: str | None = None

    def __bool__(self) -> bool:
        """至少一个特征为 True."""
        return any((
            self.is_long, self.needs_search, self.needs_planning,
            self.needs_coding, self.needs_translation,
            self.needs_structured_output, self.has_image, self.has_file,
        ))

    @property
    def complexity_score(self) -> int:
        """特征计数 (粗略复杂度)"""
        return sum(map(int, (
            self.is_long, self.needs_search, self.needs_planning,
            self.needs_coding, self.needs_translation,
            self.needs_structured_output, self.has_image, self.has_file,
        )))


# ── 关键词 / 正则规则 ───────────────────────────────────────────────

# 搜索信号
_SEARCH_PATTERNS = [
    r"搜索", r"查找", r"最新",
    r"search", r"find", r"latest",
    r"新闻", r"news", r"news?",
    r"当前", r"今天", r"today",
    r"实时", r"realtime",
    r"查一下", r"搜一下", r"帮我搜",
    r"最近", r"近期", r"最近有",
    r"发生了什么", r"动态", r"进展",
    r"热点", r"热门", r"趋势", r"trend",
    r"有什么新的", r"有没有新",
]

# 规划信号
_PLANNING_PATTERNS = [
    r"计划", r"方案", r"步骤", r"大纲",
    r"策划", r"规划",
    r"plan", r"strategy", r"steps", r"outline",
    r"架构", r"设计", r"architecture", r"design",
    r"路线图", r"roadmap",
    r"框架", r"framework",
    r"安排", r"制定", r"拟定",
    r"攻略", r"指南", r"教程",
    r"流程", r"方法论", r"策略",
    r"怎么做", r"如何做", r"从零",
    r"学习路线", r"成长路线",
    r"项目管理", r"时间安排",
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
    r"帮我写", r"写段", r"写个脚本",
    r"改一下", r"优化", r"优化一下",
    r"报错", r"出错了", r"不工作",
    r"怎么改", r"如何修改",
    r"性能", r"效率", r"加速",
    r"正则", r"regex", r"爬虫", r"爬取",
    r"接口", r"API", r"api",
    r"部署", r"deploy", r"上线",
    r"测试", r"testing", r"单元测试",
    r"SQL", r"数据库", r"database", r"查询",
    r"命令行", r"CLI", r"终端",
    r"Git", r"git", r"分支", r"合并",
    r"Docker", r"容器", r"container",
    r"配置", r"config", r"配置文件",
    r"环境变量", r"env",
]

# 翻译信号
_TRANSLATION_PATTERNS = [
    r"翻译", r"译成",
    r"translate", r"translate\s+(to|into)",
    r"翻译为", r"翻译成",
    r"中译英", r"英译中", r"日译中",
    r"用中文", r"用英文", r"用日语",
    r"转成中文", r"转成英文",
    r"翻一下", r"帮我翻",
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
    r"输出为", r"导出", r"生成表格",
    r"Markdown", r"markdown", r"md",
    r"清单", r"总结成", r"汇总",
    r"整理成", r"按格式",
]

# 显式 DeepSeek Web 模式
_EXPLICIT_WEB_MODE_PATTERNS = [
    (r"快速模式|快速回答|简单回答|短回答|别思考|不要思考", "quick"),
    (r"专家模式|深度分析|认真推理|仔细推理|慢慢想|多思考", "expert"),
    (r"识图模式|看图|看截图|截图模式", "vision"),
]

# 文件/上传意图
_FILE_PATTERNS = [
    r"上传", r"附件", r"文件", r"文档", r"截图", r"图片",
    r"PDF", r"Word", r"Excel", r"PPT",
    r"\.(pdf|docx?|xlsx?|pptx?|txt|md|py|js|ts|java|c|cpp|go|rs|json|yaml|yml|csv)\b",
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
    profile.has_file = profile.has_image or _any_match(_FILE_PATTERNS, body, low)
    profile.explicit_web_mode = _detect_explicit_web_mode(body, low)
    profile.suggested_web_mode = _suggest_web_mode(profile, prompt)

    return profile


def _detect_explicit_web_mode(body: str, low: str) -> str | None:
    """识别用户显式要求的 DeepSeek Web 模式."""
    for pattern, mode in _EXPLICIT_WEB_MODE_PATTERNS:
        if _any_match([pattern], body, low):
            return mode
    return None


def _suggest_web_mode(profile: TaskProfile, prompt: str = "") -> str:
    """根据任务画像推荐 DeepSeek Web 产品模式."""
    if profile.explicit_web_mode:
        return profile.explicit_web_mode
    if profile.has_image or profile.has_file:
        return "vision"
    if profile.needs_search:
        # 搜索任务: 复杂搜索(多特征/规划意图/分析词) → expert, 简单搜索 → quick
        is_complex_search = (
            profile.complexity_score >= 2
            or profile.needs_planning
            or _contains_analysis_intent(prompt)
        )
        return "expert" if is_complex_search else "quick"
    if profile.needs_planning or profile.is_long or profile.needs_coding:
        return "expert"
    if profile.needs_translation or profile.needs_structured_output:
        return "quick"
    return "quick"


_ANALYSIS_PATTERNS = [
    r"分析", r"评估", r"解读", r"报告", r"综述", r"总结", r"归纳",
    r"比较", r"对比", r"评价", r"研究",
    r"analyze", r"evaluate", r"report", r"review",
    r"trend", r"trends", r"insight", r"insights",
]


def _contains_analysis_intent(prompt: str) -> bool:
    """检测 prompt 是否包含分析/报告/深度解读意图."""
    low = prompt.lower()
    return _any_match(_ANALYSIS_PATTERNS, prompt, low)


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
