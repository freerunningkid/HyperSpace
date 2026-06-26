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
def _load_hybrid_config() -> dict[str, Any]:
    """加载 hybrid_config.yaml (单一配置源)."""
    hybrid_path = CONFIG_DIR / "hybrid_config.yaml"
    if hybrid_path.exists():
        with hybrid_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _providers_from_hybrid_config(hybrid: dict[str, Any]) -> dict[str, list[ProviderCandidate]]:
    """从 hybrid_config.yaml 的 executors 段提取 provider 候选.

    deepseek_web 使用 Web 凭据 (非 API key), 绑定到永存 env var 免被过滤.
    """
    executors = hybrid.get("executors", {})
    providers: dict[str, list[ProviderCandidate]] = {}

    def _mk(provider: str, model: str, base_url: str = "", key_env: str = "PATH") -> ProviderCandidate:
        return ProviderCandidate(provider=provider, base_url=base_url, model=model, key_env=key_env)

    # 按新 executor 名映射到旧 tier 体系
    # 所有免费 web/api 候选归入 free_text, deepseek_web 同时归入 free_vision
    free_text: list[ProviderCandidate] = []
    free_vision: list[ProviderCandidate] = []
    cheap_capable: list[ProviderCandidate] = []

    for name, cfg in executors.items():
        if not isinstance(cfg, dict):
            continue
        provider = cfg.get("provider", name)
        model = cfg.get("model", name)
        base_url = cfg.get("base_url", "")
        key_env = cfg.get("key_env", "")

        if name == "deepseek_web":
            # Web 凭据认证, 不依赖 API key — 用永存的 env var
            cand = _mk(provider, model, "https://chat.deepseek.com", "PATH")
            free_text.append(cand)
            free_vision.append(cand)
        elif key_env:
            cand = ProviderCandidate(provider=provider, base_url=base_url, model=model, key_env=key_env)
            free_text.append(cand)
            # zhipu 也加一层便宜备选
            if name == "zhipu":
                cheap_capable.append(cand)

    providers["free_text"] = free_text
    providers["free_vision"] = free_vision
    providers["cheap_capable"] = cheap_capable
    providers["premium"] = []
    return providers


def _routing_from_hybrid_config(hybrid: dict[str, Any]) -> RoutingRules:
    """从 hybrid_config.yaml 的 routing 段提取路由规则."""
    routing_raw = hybrid.get("routing", {})
    return RoutingRules(
        code_markers=["```", "def ", "class ", "import ", "function "],
        complex_keywords=["代码", "bug", "调试", "优化", "架构"],
        length_threshold=800,
        escalation_chain=routing_raw.get("fallback_order",
            ["free_text", "free_vision", "cheap_capable", "premium"]),
    )


def load_config() -> Config:
    """加载 .env + providers/routing 配置.

    优先读取 providers.yaml / routing.yaml;
    缺失时从 hybrid_config.yaml 提取 (单一配置源).
    """
    _ensure_dirs()
    load_dotenv(ENV_FILE)  # 缺失不报错

    hybrid = _load_hybrid_config() if (not PROVIDERS_FILE.exists() or not ROUTING_FILE.exists()) else None

    # ── providers ──
    if PROVIDERS_FILE.exists():
        providers_raw: dict[str, Any] = {}
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
    else:
        providers = _providers_from_hybrid_config(hybrid or {})
        import logging
        logging.getLogger("hyperspace").info("providers.yaml 缺失, 已从 hybrid_config.yaml 提取 %d tiers", len(providers))

    # ── routing ──
    if ROUTING_FILE.exists():
        routing = RoutingRules()
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
    else:
        routing = _routing_from_hybrid_config(hybrid or {})
        import logging
        logging.getLogger("hyperspace").info("routing.yaml 缺失, 已从 hybrid_config.yaml 提取")

    return Config(providers=providers, routing=routing)
