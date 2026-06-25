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
  <a href="#"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs"></a>
  <a href="#"><img src="https://img.shields.io/badge/Agent-Skill-7C3AED" alt="skill"></a>
  <br>
  <a href="#"><img src="https://img.shields.io/badge/cost-¥0-free?color=success" alt="cost"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-225%20passed-brightgreen" alt="tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-Win%20%7C%20Mac%20%7C%20Linux-lightgrey" alt="platform"></a>
</p>

---

## ✨ 是什么

HyperSpace 让你的 AI Agent 的**推理成本降到 ¥0**。

它不是另一个 LLM 框架，而是一个薄薄的智能路由层：Agent 负责协调和决策（用少量 token），实际的推理、搜索、规划、识图全部转发给 **DeepSeek Web（免费）**。

```bash
你说 "帮我规划一个学习路线"
  → Agent 判定复杂度 → 自动调 hyperspace ask → DeepSeek Web 出计划 → 展示给你
  → 成本：¥0
```

---

## 🎮 5 秒体验

```bash
git clone https://github.com/freerunningkid/HyperSpace.git && cd HyperSpace
pip install -e ".[web]"                     # 含 Playwright，自动凭据提取
cp .env.example .env && vim .env           # 填 ZHIPU_API_KEY（免费兜底）
hyperspace ask "你好"                       # 首次自动开浏览器登录，之后全自动
```

```
────────────────────────────────────────────────────────────
[HyperSpace] 🌐 DeepSeek Web (¥0) · deepseek-chat | 31tk · ¥0
────────────────────────────────────────────────────────────
你好！我是 DeepSeek，很高兴为你服务 😊
────────────────────────────────────────────────────────────
```

> 首次运行会自动安装 Playwright Chromium（~150MB），然后打开浏览器引导你登录 chat.deepseek.com。
> **不需要装 Chrome**——任何浏览器都行，Playwright 自带。

---

## 🧠 智能模式选择

你只管说话，CLI 自动选模式和开关：

| 你说的话 | 自动判定 | 模式 | 🧠深度思考 | 🌐联网搜索 |
|---------|---------|------|----------|----------|
| "写个快速排序" | 代码生成 | `expert` | ✅ | ❌ |
| "帮我规划学习路线" | 规划+长文本 | `expert` | ✅ | ❌ |
| "搜索今天的 AI 新闻" | 搜索关键词 | `quick` | ❌ | ✅ |
| "这张图里有什么" | 图片输入 | `vision` | ✅ | ❌ |
| "翻译成英文" | 翻译 | `quick` | ❌ | ❌ |
| "你好" | 简单问候 | `quick` | ❌ | ❌ |

> ⚠️ Expert 模式不支持搜索——需要搜索自动走 quick
> 手动覆盖：`--web-mode expert` `--search` `--mode force_zhipu`

---

## 🛡️ 四级降级链

一条挂了自动切下一条，全部 **¥0**：

```
hyperspace ask "你的问题"
  │
  ├─ 1️⃣ DeepSeek Web     主力 · 问答/搜索/识图/规划
  ├─ 2️⃣ GitHub GPT-4o    备胎 · OCR 极强
  ├─ 3️⃣ 智谱 GLM         兜底 · 稳定可靠
  └─ 4️⃣ Agnes Flash      最后防线
```

手动指定：`--mode force_web` `--mode force_github` `--mode force_zhipu` `--mode force_agnes`

---

## 🔐 凭据全自动

| 阶段 | 行为 |
|------|------|
| 首次使用 | 自动开浏览器 → 你登录 DeepSeek → Bearer 自动保存 |
| 日常使用 | Bearer 有效直接调用，零延迟 |
| Bearer 过期 | API 报错自动清除 → 下次自动刷新 |
| 需要验证码 | 等你 5 分钟，不提前关浏览器 |

---

## 🤖 Agent Skill 集成

安装后 Agent 自动感知。你说自然语言，它自动判断是否需要调 HyperSpace：

| 你问 | Agent 行动 |
|------|-----------|
| 外部知识 / 搜索 | → `hyperspace ask ... --search` |
| 复杂推理 / 规划 | → `hyperspace ask ... --web-mode expert` |
| 截图问问题 | → `hyperspace ask ... --image <path>` |
| 写代码 / 翻译 | → `hyperspace ask ...` |
| 改本地代码 / git | → 不触发，本地处理 |

> 支持 Claude Code · CodeWhale · Reasonix

---

## 🏗️ 架构

```
┌──────────────────────────────────────────────────────┐
│                    HyperSpace                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│   User / Agent                                       │
│       │                                              │
│       ▼                                              │
│   ┌─────────┐    ┌──────────────┐                   │
│   │  CLI    │◄───│ TaskAnalyzer │ 零 token 判定      │
│   └────┬────┘    └──────────────┘                   │
│        │                                              │
│        ▼                                              │
│   ┌──────────────┐                                   │
│   │ HybridRouter │  路由 · 降级 · 健康和检查         │
│   └──────┬───────┘                                   │
│          │                                            │
│   ┌──────┼──────┬──────────┬──────────┐              │
│   ▼      ▼      ▼          ▼          ▼              │
│  Web   GitHub  Zhipu     Agnes      API              │
│  ¥0     ¥0      ¥0        ¥0        ¥2-6/M          │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 📊 对比

| | HyperSpace | 直接调 API | 其他路由工具 |
|:---|:---:|:---:|:---:|
| 主力引擎成本 | **¥0** | ¥2-6/M | 看配置 |
| 备用引擎数 | 4 个免费 | 0 | 1-2 |
| 自动模式选择 | ✅ | ❌ | ❌ |
| 自动凭据刷新 | ✅ | ❌ | ❌ |
| Agent Skill | ✅ | ❌ | ❌ |
| 图片识别 | ✅ | 看模型 | |
| 联网搜索 | ✅ | 看模型 | |
| 配置复杂度 | 1 个 Key | N 个 Key | 多配置 |
| 零外部依赖 | ✅ | ❌ | |

---

## 📁 项目结构

```
HyperSpace/
├── hyperspace/
│   ├── cli.py                      # CLI (ask/chat/info/summary)
│   └── hybrid_engine/
│       ├── deepseek_web_client.py  # PoW + SSE + 文件上传
│       ├── hybrid_router.py        # 四级降级路由
│       ├── task_analyzer.py        # 智能模式 (零 token)
│       ├── web_auth.py             # 自动凭据 (Playwright)
│       ├── health_checker.py       # 健康探测
│       ├── fallback.py             # 指数退避降级
│       ├── context_window_manager.py
│       └── result_processor.py
├── config/hybrid_config.yaml       # 降级链配置
├── tests/                          # 225 测试 (零网络)
└── pyproject.toml
```

---

## 🔧 开发

```bash
pip install -e ".[dev]"    # 含测试依赖
pytest tests/ -v           # 225 全绿
```

---

<p align="center">
  <sub>MIT · <a href="https://github.com/freerunningkid">freerunningkid</a> · PRs welcome ✨</sub>
</p>
