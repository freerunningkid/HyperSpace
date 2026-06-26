<p align="center">
  <img src="Logo.png" alt="HyperSpace" width="480">
</p>

<p align="center">
  <strong>DeepSeek Web (¥0) 主力引擎 · 四级免费降级链 · Agent Skill + CLI</strong>
</p>

<p align="center">
  <a href="https://github.com/freerunningkid/HyperSpace/actions/workflows/tests.yml"><img src="https://github.com/freerunningkid/HyperSpace/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="license"></a>
  <br>
  <a href="#"><img src="https://img.shields.io/badge/cost-¥0-free?color=success" alt="cost"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-225%20passed-brightgreen" alt="tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-Win%20%7C%20Mac%20%7C%20Linux-lightgrey" alt="platform"></a>
</p>

---

## ✨ 是什么

HyperSpace 让你的 AI Agent 推理成本降到 **¥0**。

薄薄的智能路由层：Agent 协调决策（少量 token），推理/搜索/规划/识图转发 **DeepSeek Web（免费）**。

```bash
hyperspace ask "帮我规划一个学习路线"
# → DeepSeek Web 出计划 → 成本 ¥0
```

---

## 🎮 5 秒体验

```bash
git clone https://github.com/freerunningkid/HyperSpace.git && cd HyperSpace
pip install -e ".[web]"
cp .env.example .env && vim .env           # 填 ZHIPU_API_KEY
hyperspace ask "你好"                       # 首次自动开浏览器登录
```

```
────────────────────────────────────────────────────────────
[HyperSpace] 🌐 DeepSeek Web (¥0) · deepseek-v4-flash | 31tk · ¥0
────────────────────────────────────────────────────────────
你好！我是 DeepSeek，很高兴为你服务 😊
────────────────────────────────────────────────────────────
```

---

## 🧠 智能模式 + 模型标签

自动判定模式并显示实际使用的模型：

| 你说的话 | 判定 | 模式 | 显示标签 |
|---------|------|------|----------|
| "写个快速排序" | 代码 | `expert` | `deepseek-v4-pro · deep thinking` |
| "帮我规划学习路线" | 规划 | `expert` | `deepseek-v4-pro · deep thinking` |
| "搜索今天的 AI 新闻" | 搜索 | `quick` | `deepseek-v4-flash` |
| "这张图里有什么" | 图片 | `vision` | `deepseek-v4-pro` |
| "翻译成英文" | 翻译 | `quick` | `deepseek-v4-flash` |
| "你好" | 问候 | `quick` | `deepseek-v4-flash` |

> 手动覆盖：`--web-mode expert` `--search` `--mode force_zhipu`

---

## 🛡️ 四级降级链

```
hyperspace ask "你的问题"
  │
  ├─ 1️⃣ DeepSeek Web     主力 · 问答/搜索/识图/规划
  ├─ 2️⃣ GitHub GPT-4o    备胎
  ├─ 3️⃣ 智谱 GLM         兜底
  └─ 4️⃣ Agnes Flash      最后防线
```

---

## 🔐 凭据生命周期

| 阶段 | 行为 |
|------|------|
| 首次使用 | 自动开浏览器 → 登录 → Bearer 保存 |
| 日常调用 | Bearer 有效，零延迟 |
| Bearer 过期 | 自动清除 → 立即后台刷新 (`_refresh_web_auth`) |
| 并发刷新 | `asyncio.Lock` 保护，同一时间只刷新一次 |

---

## 💬 多轮对话记忆

85% 上下文满时自动压缩：提取历史摘要 → 新 session → 注入摘要。对话记忆不丢失。

**滚动历史缓冲**：保留最近 15 轮真实对话内容，API 压缩时基于实际对话生成摘要（非空壳）。

---

## 🎯 任务感知系统指令

自动按任务特征注入最小化系统指令，精准控制 Web 行为：

| 触发 | 注入 |
|------|------|
| 代码 | "编程助手 — 输出正确代码，不编造 API" |
| 翻译 | "翻译引擎 — 只输出译文" |
| 规划 | "技术规划师 — 具体可执行步骤" |
| 搜索 | "研究助手 — 不确定就标注" |

手动覆盖：`hyperspace ask "..." --context "你的指令"`

---

## 🤖 Agent Skill 集成

| 你问 | Agent 行动 |
|------|-----------|
| 外部知识 / 搜索 | → `hyperspace ask ... --search` |
| 复杂推理 / 规划 | → `hyperspace ask ... --web-mode expert` |
| 截图问问题 | → `hyperspace ask ... --image <path>` |
| 写代码 / 翻译 | → `hyperspace ask ...` |
| 改本地代码 / git | → 不触发，本地处理 |

---

## 🏗️ 架构

```
┌──────────────────────────────────────────────────────┐
│                    HyperSpace                        │
│                                                      │
│   User / Agent                                       │
│       │                                              │
│       ▼                                              │
│   ┌─────────┐    ┌──────────────┐                   │
│   │  CLI    │◄───│ TaskAnalyzer │ 零 token 判定      │
│   └────┬────┘    └──────────────┘                   │
│        │                                              │
│        ▼                                              │
│   ┌──────────────┐    ┌─────────────────┐            │
│   │ HybridRouter │───►│ _build_system_  │ 任务感知    │
│   └──────┬───────┘    │ context()       │ 系统指令    │
│          │            └─────────────────┘            │
│   ┌──────┼──────┬──────────┬──────────┐              │
│   ▼      ▼      ▼          ▼          ▼              │
│  Web   GitHub  Zhipu     Agnes      API              │
│  ¥0     ¥0      ¥0        ¥0        ¥2-6/M          │
│                                                      │
│   Web 引擎: PoW → asyncio.to_thread (非阻塞)          │
│              Bearer → Lock + 自动刷新                  │
│              Context → 滚动历史 + 压缩摘要继承         │
└──────────────────────────────────────────────────────┘
```

---

## 🆕 最近更新 (v2.2)

- **任务感知系统指令**：自动注入最小化 context，精准控制 Web 行为
- **模型标签**：显示实际使用的模型 (`deepseek-v4-pro · deep thinking` / `deepseek-v4-flash`)
- **上下文压缩修复**：滚动历史缓冲 → 真实对话摘要 → 新 session 继承
- **PoW 线程池化**：`asyncio.to_thread` + 30s 超时，不阻塞事件循环
- **Bearer 自动刷新**：`asyncio.Lock` 保护，过期立即后台刷新
- **serve 命令修复**：`os.execvp` → 直接 import；参数透传
- **config fallback**：`providers.yaml`/`routing.yaml` 缺失时从 `hybrid_config.yaml` 提取

---

## 📁 核心模块

```
HyperSpace/
├── hyperspace/
│   ├── cli.py                      # CLI (ask/chat/info/summary/serve)
│   ├── config.py                   # 配置 fallback + hybrid_config 提取
│   └── hybrid_engine/
│       ├── hybrid_router.py        # 路由 + 系统指令 + 自动刷新
│       ├── deepseek_web_client.py  # PoW(线程池) + SSE + 文件上传
│       ├── task_analyzer.py        # 零 token 模式判定
│       ├── context_window_manager.py  # 压缩 + 滚动历史 + 继承
│       ├── web_auth.py             # CDP → Playwright → Chrome
│       ├── health_checker.py       # 健康探测 (60s 缓存)
│       ├── fallback.py             # 指数退避降级
│       └── result_processor.py
├── config/hybrid_config.yaml
├── tests/                          # 225 测试 (零网络)
└── pyproject.toml
```

---

## 🔧 开发

```bash
pip install -e ".[dev]"
pytest tests/ -v           # 225 passed
```

---

<p align="center">
  <sub>MIT · <a href="https://github.com/freerunningkid">freerunningkid</a></sub>
</p>
