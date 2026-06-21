"""配置加载 —— providers.yaml / routing.yaml + .env.

定位策略: 相对包自身的 ../config 与 ../data, 保证从任意 cwd 启动都能找到文件
(配合 .mcp.json 以绝对路径 args 启动 server.py, cwd 不可控).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# ── 路径 ──
# server.py 在 hyperspace/, config 在 ../config/, data 在 ../data/
_PKG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _PKG_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

PROVIDERS_FILE = CONFIG_DIR / "providers.yaml"
ROUTING_FILE = CONFIG_DIR / "routing.yaml"
ENV_FILE = PROJECT_ROOT / ".env"
COST_LOG = DATA_DIR / "hyperspace_cost.log"


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ProviderCandidate:
    """一个 provider 候选 (tier 下的一条)."""

    provider: str          # zhipu / deepseek / kimi / openrouter
    base_url: str
    model: str
    key_env: str           # 读取哪个环境变量作 api_key

    @property
    def api_key(self) -> str | None:
        """从环境读取 key; 缺失返回 None (调用方据此跳过该候选)."""
        return os.environ.get(self.key_env)


@dataclass
class RoutingRules:
    """路由规则 (廉价判定)."""

    code_markers: list[str] = field(default_factory=list)
    complex_keywords: list[str] = field(default_factory=list)
    length_threshold: int = 800
    escalation_chain: list[str] = field(
        default_factory=lambda: ["free_text", "free_vision", "cheap_capable", "premium"]
    )


@dataclass
class Config:
    """运行时配置单例."""

    providers: dict[str, list[ProviderCandidate]] = field(default_factory=dict)
    routing: RoutingRules = field(default_factory=RoutingRules)

    def candidates_for(self, tier: str) -> list[ProviderCandidate]:
        """取某 tier 的候选列表 (只保留已配置 key 的)."""
        return [c for c in self.providers.get(tier, []) if c.api_key]

    def escalation_after(self, tier: str) -> list[str]:
        """tier 失败后的升档序列 (不含自身)."""
        chain = self.routing.escalation_chain
        try:
            idx = chain.index(tier)
        except ValueError:
            return []
        return chain[idx + 1 :]


# ── 加载 ──
def load_config() -> Config:
    """加载 .env + 两份 yaml. 启动时调用一次."""
    _ensure_dirs()
    load_dotenv(ENV_FILE)  # 缺失不报错

    providers_raw: dict[str, Any] = {}
    if PROVIDERS_FILE.exists():
        with PROVIDERS_FILE.open(encoding="utf-8") as f:
            providers_raw = yaml.safe_load(f) or {}

    providers: dict[str, list[ProviderCandidate]] = {}
    for tier, lst in providers_raw.items():
        if not isinstance(lst, list):
            continue
        providers[tier] = [
            ProviderCandidate(
                provider=item["provider"],
                base_url=item["base_url"],
                model=item["model"],
                key_env=item["key_env"],
            )
            for item in lst
            if isinstance(item, dict) and {"provider", "base_url", "model", "key_env"} <= item.keys()
        ]

    routing = RoutingRules()
    if ROUTING_FILE.exists():
        with ROUTING_FILE.open(encoding="utf-8") as f:
            r = yaml.safe_load(f) or {}
        c = r.get("complexity", {}) or {}
        routing.code_markers = c.get("code_markers", []) or []
        routing.complex_keywords = c.get("complex_keywords", []) or []
        routing.length_threshold = c.get("length_threshold", 800)
        routing.escalation_chain = r.get(
            "escalation_chain",
            ["free_text", "free_vision", "cheap_capable", "premium"],
        ) or ["free_text", "free_vision", "cheap_capable", "premium"]

    return Config(providers=providers, routing=routing)
