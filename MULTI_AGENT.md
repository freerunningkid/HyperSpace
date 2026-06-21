# Reasonix 多 Agent 共享中枢

`D:\Reasonix` 是所有 Agent 的共享配置、记忆、工具中枢。任何部署在 `D:\Reasonix` 工作区下的 Agent 都能访问以下共享资源。

## 共享目录

| 目录 | 用途 | 多 Agent 访问方式 |
|------|------|------------------|
| `memory/` | 共享记忆（用户画像、知识、经验、决策） | 所有 Agent 读写同一套记忆，实现经验共享 |
| `.reasonix/skills/` | 共享 Skills（coding / planning / system / tools） | 所有 Agent 按需调用 `run_skill()` |
| `scripts/lib/` | 通用工具库（Python CLI 工具） | 所有 Agent 直接 `python scripts/lib/<tool>.py` |
| `config/` | 共享配置（模型提供商、Agent 模板） | 配置文件化，Agent 启动时加载 |
| `reference-参考/` | 参考文档（官方文档、规则、架构记录） | 所有 Agent 按需读取 |
| `knowledge-知识库/` | 知识笔记 | 所有 Agent 读写共享知识 |
| `learning-学习/` | 学习资料（考试、技能等） | 所有 Agent 按需读取 |
| `bridge/` | Agent 间通信（任务交接） | 任意 Agent 读写，通过文件桥接力 |

## 接入一个新 Agent

1. **设置工作区**到 `D:\Reasonix`
2. **配置 Agent** 引用 `D:\Reasonix\REASONIX.md` 作为主项目指南
3. **选择模型** — 参考 `config/model_providers.template.json` 和 `scripts/lib/switch_model.py`
4. **加载记忆** — 系统自动读取 `memory/` 下的所有记忆文件
5. **使用 Skills** — 非平凡任务前扫 `.reasonix/skills/` 索引
6. **通信** — 通过 `bridge-to-2b.md` 或其他桥文件与其他 Agent 交接任务

## 环境变量约定

敏感信息（API Key）统一通过环境变量注入，不在代码中硬编码：

| 环境变量 | 用途 |
|---------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API |
| `AGNES_API_KEY` | Agnes AI API |
| `ZHIPU_API_KEY` | 智谱AI (GLM) API |

> 其他 Agent 新增模型时，也请遵循此约定：API Key 走环境变量，配置参考 `config/model_providers.template.json`

## 通信协议

Agent 间通过 `bridge/` 目录下的 Markdown 桥文件通信：

```
bridge/
├── handoff-to-2b.md    ← 其他 Agent → 2B 的任务交接
└── result-from-2b.md   ← 2B → 其他 Agent 的结果回复
```

格式：
```markdown
## Handoff: <任务标题>
**From**: <来源 Agent>
**To**: <目标 Agent>
**Task**: <任务描述>
**Context**: <上下文/文件路径>

## Result: <任务标题>
**From**: <执行 Agent>
**Status**: done / failed / partial
**Output**: <结果摘要>
```
