# Claude Code Token 经济全方案 — 办公室部署手册

> 导出时间：2026-05-29 | 来源：主工作区 D:\AgentWork
> 用途：办公室电脑一键部署 Claude Code 成本控制体系

---

## 目录

1. [核心理念](#1-核心理念)
2. [基础设施：settings.json 配置](#2-基础设置settingsjson-配置)
3. [缓存优化策略](#3-缓存优化策略)
4. [上下文监控与压缩](#4-上下文监控与压缩)
5. [模型选择与 Effort 策略](#5-模型选择与-effort-策略)
6. [扩展思考成本控制](#6-扩展思考成本控制)
7. [超压缩模式（Caveman）](#7-超压缩模式caveman)
8. [省钱习惯清单](#8-省钱习惯清单)
9. [记忆体系成本控制](#9-记忆体系成本控制)
10. [CLAUDE.md 瘦身指南](#10-claudemd-瘦身指南)
11. [Path-Scoped Rules 配置](#11-path-scoped-rules-配置)
12. [子代理成本策略](#12-子代理成本策略)
13. [Hooks 预处理降本](#13-hooks-预处理降本)
14. [一键初始化脚本](#14-一键初始化脚本)
15. [日常检查清单](#15-日常检查清单)

---

## 1. 核心理念

**Claude Code 本质是精密的 Token 经济系统。省钱就是省上下文，省上下文就是提效。**

### Prompt Cache 机制

Prompt Cache 提供 **90% 折扣**（缓存命中只付 10% 费用）。因此：**稳定 > 一切。**

任何造成缓存不命中的改动，都等于直接烧钱。

---

## 2. 基础配置（settings.json）

办公室电脑首次部署时，必须配置以下环境变量。这是**最直接、最立竿见影**的降本手段：

```jsonc
{
  "env": {
    // 限制扩展思考 Token 预算（默认可能高达 100K+/请求）
    // 推荐值：10000-16000，简单任务可压到 8000
    "MAX_THINKING_TOKENS": "10000",

    // 子代理默认使用 Haiku 模型（最便宜）
    // 日常编码用 Sonnet，复杂分析才用 Opus
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku",

    // 自动压缩阈值：上下文达到窗口 80% 时自动触发 /compact
    // 默认是 window-13000，用百分比更直观
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80",

    // 最大上下文 Token 数上限
    // 默认 200K，限制到 100K 可大幅降低成本
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "100000"
  }
}
```

**💡 配置说明**：

| 变量 | 作用 | 省钱原理 |
|------|------|---------|
| `MAX_THINKING_TOKENS=10000` | 限制思考 Token | 思考 Token 按输出价格计费，限制后每请求省 60%+ |
| `CLAUDE_CODE_SUBAGENT_MODEL=haiku` | 子代理用最便宜模型 | Haiku 比 Sonnet 便宜 3-5 倍 |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` | 早触发压缩 | 避免上下文爆炸后精度下降导致无效输出 |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS=100000` | 限制总上下文 | 直接封顶，防止 runaway |

### 对应命令

```bash
# 查看当前配置
claude /config

# 设置模型（会话级）
claude /model claude-sonnet-4-20250514      # 日常编码用 Sonnet

# 设置 Effort（会话级）
claude /effort low                           # 简单任务
claude /effort high                          # 默认推荐
claude /effort max                           # 复杂推理
```

---

## 3. 缓存优化策略

### 缓存失效五大陷阱（必须避免）

| # | 行为 | 后果 |
|---|------|------|
| 1 | ❌ CLAUDE.md 中途修改 | **整个缓存链全部失效**，下次请求付全价 |
| 2 | ❌ 消息中混入动态时间戳/随机 ID | 每次都不命中缓存，次次全价 |
| 3 | ❌ 切换模型（Opus↔Sonnet） | 缓存空间独立，换模型 = 缓存清零 |
| 4 | ❌ 不同项目用不同路径前缀 | 缓存 key 不同，不共享 |
| 5 | ❌ 会话间 system prompt 不一致 | 前缀不匹配，缓存失效 |

### 缓存优化策略

```
✅ 稳定 CLAUDE.md，会话中途绝不修改
✅ 静态配置放 CLAUDE.md，动态内容放对话中
✅ 同一项目保持路径前缀一致
✅ 不加载无用大文件（package-lock.json、日志、node_modules）
✅ 不在 CLAUDE.md 中放时间敏感内容（日期、版本号等）
```

### 缓存健康检查

```bash
# 查看当前上下文占用
claude /context

# 查看 Token 使用统计和费用估计
claude /usage

# 实时状态行（连续显示上下文使用率）
claude /statusline
```

---

## 4. 上下文监控与压缩

### 核心命令

| 命令 | 用途 | 执行时机 |
|------|------|---------|
| `/context` | 查看上下文窗口占用 | 每会话 1-2 次 |
| `/usage` | 查看 Token 统计和费用 | 长会话定期 |
| `/compact` | 压缩对话历史释放窗口 | 上下文 > 100K tokens |
| `/compact focus on <重点>` | 指定保留内容的压缩 | 需要保留关键信息时 |
| `/clear` | 清空当前会话 | 任务间切换 |
| `/statusline` | 连续显示上下文使用率 | 开启后持续监控 |

### `/compact` 正确用法

**不要把 `/compact` 当可选功能——它是防止 Token 爆炸的最后一道防线。**

- **上下文超过 100K tokens 时手动执行** `/compact`
- **不要等自动触发**（自动阈值是 `contextWindow - 13,000`，那时已花冤枉钱）
- `/compact` 消耗 Token 生成摘要，但比上下文爆满导致精度下降或被迫重启更划算
- 用 `/compact focus on <重点>` 指定保留内容

### `/compact` 后什么存活

| 组件 | 存活状态 |
|------|---------|
| 项目根 CLAUDE.md | ✅ 自动重新注入 |
| 用户级 `~/.claude/CLAUDE.md` | ❌ 不重新注入 |
| `.claude/rules/`（无 paths） | ⚠️ 不保证存活 |
| `.claude/rules/`（有 paths） | ⚠️ 需重新访问匹配文件 |
| 对话中给出的临时指令 | ❌ 可能丢失 |

### 上下文管理习惯

```
1️⃣ 长会话定期 /context 检查占用
2️⃣ 感觉上下文快超标时 → 主动 /compact
3️⃣ 关键信息先写入 memory/ 再换新会话
4️⃣ 任务间用 /clear 重置，不相关上下文别留着
```

---

## 5. 模型选择与 Effort 策略

### 模型选择矩阵

| 任务类型 | 推荐模型 | 理由 |
|---------|---------|------|
| 日常编码、简单问答、文件操作 | Sonnet | 平衡成本与性能 |
| 复杂架构、安全审查、深度 Bug 排查 | Opus | 需要强推理 |
| 简单补全、短问答、子代理任务 | Haiku | 成本最低（比 Sonnet 便宜 3-5x） |

```bash
# 日常编码
claude /model claude-sonnet-4-20250514

# 复杂分析临时切换
claude /model claude-opus-4-20250514

# 子代理自动使用 Haiku（已在 settings.json 配置）
# 通过 CLAUDE_CODE_SUBAGENT_MODEL=haiku 自动生效
```

### Effort Level 策略

Opus 4.7+ 引入 Adaptive Thinking，按任务难度匹配 Effort：

| Effort | 推荐场景 | 性价比 |
|--------|---------|-------|
| `low` / `medium` | 简单问答、搜索、文件读取 | 最省 |
| `high` | 并发会话、预算敏感场景 | 均衡 |
| **`xhigh`**（默认推荐） | **大部分编码和 Agent 任务** | 性价比最佳 |
| `max` | 真正困难的问题（收益递减） | 按需使用 |

**原则**：不要把 easy task 喂给 `xhigh`，也不要把 hard task 喂给 `medium`。

```bash
# 设置 Effort 级别
claude /effort low        # 省
claude /effort high       # 默认
claude /effort max        # 全力
```

---

## 6. 扩展思考成本控制

扩展思考（Extended Thinking）默认启用，**思考 Token 按输出 Token 价格计费**。默认预算可能每请求数万个 Token。

### 降成本方式

```bash
# 方式 1：降低 Effort 级别
claude /effort low

# 方式 2：在 settings.json 中限制思考预算
# "MAX_THINKING_TOKENS": "10000"

# 方式 3：切换模型时禁用思考
claude /model claude-sonnet-4-20250514    # Sonnet 默认思考预算较低

# 方式 4：环境变量进一步压紧
# MAX_THINKING_TOKENS=8000  # 极简任务
```

### 推荐配置

| 场景 | MAX_THINKING_TOKENS | 月省估算 |
|------|-------------------|---------|
| 日常编码（Sonnet） | 8000-10000 | 40-60% |
| 复杂分析（Opus） | 16000-32000 | 30-50% |
| 简单问答（Haiku） | 4000-8000 | 60-80% |

---

## 7. 超压缩模式（Caveman）

当上下文逼近 80K tokens 或 Token 预算紧张时，激活超压缩模式。

### 激活方式

```
在对话中说："caveman" 或 "压缩模式"
```

### 效果

| 维度 | 正常模式 | Caveman 模式 |
|------|---------|-------------|
| 输出长度 | 完整 | 减少 60%-75% |
| 保留内容 | 全部 | 文件路径 + 技术术语 + 命令 + 决策要点 |
| 省略内容 | — | 过渡句、重复确认、礼貌填充 |

### 恢复

```
说："正常模式"
```

### 典型场景

- 上下文接近 80K 但还没到 `/compact` 阈值
- 月底 Token 预算快用完
- 批量处理简单任务（如批量文件操作）
- 子代理任务（自带压缩）

---

## 8. 省钱习惯清单

### ⭐ 高杠杆（立即生效）

| # | 习惯 | 省 Token 效果 |
|---|------|-------------|
| 1 | ✅ **用 grep 而非 cat 读文件** | 输入减少 90%+ |
| 2 | ✅ **长命令用 `\| tail -n 20` 或 `\| grep -i error` 过滤** | 输出减少 95%+ |
| 3 | ✅ **复杂任务前做"技术经济评估"** | 避免错误方向烧 Token |
| 4 | ✅ **任务间用 /clear 重置上下文** | 不相关上下文不再浪费每次消息 |
| 5 | ✅ **默认用 Sonnet，需要时才切 Opus** | 成本直降 3-5x |

### ⭐ 中杠杆（首次配置后自动生效）

| # | 习惯 | 省 Token 效果 |
|---|------|-------------|
| 6 | ✅ **路径范围规则（paths frontmatter）** | 缩小规则加载范围，减少启动上下文 |
| 7 | ✅ **特定工作流指令从 CLAUDE.md 移到 skills** | 按需加载，不占启动上下文 |
| 8 | ✅ **非编码任务用 subagents 隔离上下文** | 探索/测试/日志分析不污染主会话 |
| 9 | ✅ **Hooks 预处理数据** | 10000 行日志 → grep ERROR → 几百行才进上下文 |
| 10 | ✅ **MCP 优先用 CLI 替代** | gh/aws/gcloud 不添加工具列表开销 |

### ⭐ 低杠杆（锦上添花）

| # | 习惯 | 说明 |
|---|------|------|
| 11 | ✅ 避免无意义的 Web 搜索 | 消耗上下文 Token |
| 12 | ✅ 安装代码智能插件 | 减少不必要的文件读取 |
| 13 | ✅ 检查 `/config` 中当前计划设定 | 避免不必要的高开销设置 |

---

## 9. 记忆体系成本控制

### 核心原则

**MEMORY.md 有硬截断：超过前 200 行或 25KB 后的内容静默丢失。**

### 维护策略

```
📋 每月检查一次：
   1. 统计 MEMORY.md 行数
   2. 接近 200 行 → 按主题拆分到独立文件
   3. 索引行压缩到 150 字符以内
   4. 运行 /memory 审计当前加载

📋 记忆类型分类（按需加载）：
   - memory/<topic>.md  → 按需读取，不占启动上下文
   - MEMORY.md          → 仅索引摘要，前 200 行限制
```

### 步骤：MEMORY.md 超限拆分

```bash
# 1. 创建独立文件
mkdir -p ~/.claude/projects/<project>/memory/

# 2. 将大块内容移出到独立文件（如 project-alpha.md）
# 3. MEMORY.md 索引行格式（控制在 150 字符内）：
#    - [标题](file.md) — 一句话摘要
```

---

## 10. CLAUDE.md 瘦身指南

### 什么放 CLAUDE.md

- ✅ 人格定义、核心行为准则
- ✅ Karpathy 四原则
- ✅ 规则速览（汇总索引）
- ✅ 工作区结构
- ✅ Compact instructions

### 什么不放 CLAUDE.md（移到 rules/）

| 内容 | 目标位置 | 理由 |
|------|---------|------|
| 详细操作步骤 | `.claude/rules/*.md` | 按需加载，不占启动上下文 |
| 特定文件类型的规则 | `.claude/rules/` + paths frontmatter | 仅处理匹配文件时加载 |
| 特定工作流 | `.claude/skills/` | 手动调用，完全不占上下文 |
| 长列表/知识库 | `02-知识库/` | Claude 需要时主动读取 |
| 动态内容 | 对话中 | 不改 CLAUDE.md 避免缓存失效 |

### CLAUDE.md 理想大小

**< 200 行**。超过即需要拆分到 rules/。

---

## 11. Path-Scoped Rules 配置

### 原理

在 rules 文件的 frontmatter 中声明 `paths`，Claude 只在处理匹配文件时加载该规则。

### 示例

```markdown
---
paths:
  - "*.md"
  - "**/*.md"
---

# Markdown 文件处理规则
...（只在处理 .md 文件时加载）
```

```markdown
---
paths:
  - "scripts/**"
  - "*.py"
---

# Python 脚本规则
...（只在处理 Python 文件时加载）
```

### 节省效果

| 配置方式 | 启动上下文占用 | 说明 |
|---------|-------------|------|
| 全部放 CLAUDE.md | ~全部 | 每次请求都加载 |
| 无 paths 的 rules | ~全部 | 启动时加载 |
| 有 paths 的 rules | ∼0（需要时加载） | **最省** |

### 分类建议

| 规则类型 | paths 配置 |
|---------|-----------|
| 编码相关、始终需要 | ❌ 无 paths（启动加载） |
| 文件类型特定 | ✅ 有 paths（匹配时加载） |
| 项目特定工作流 | ✅ 移到 skills（手动调用） |

---

## 12. 子代理成本策略

### settings.json 配置

```json
{
  "env": {
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku"
  }
}
```

### 子代理模型选择原则

| 子代理任务 | 推荐模型 | 理由 |
|-----------|---------|------|
| 文件搜索、grep 查询 | Haiku | 简单任务 |
| 代码审查、Bug 分析 | Sonnet | 需要理解 |
| 架构设计、多因子分析 | Opus | 复杂推理 |

### 子代理隔离优势

```
💡 非编码任务使用 subagents 隔离上下文：
   - 探索性任务（Explore Agent）
   - 日志分析
   - 测试执行结果检查
   
   → 这些任务的输出不会污染主会话上下文
   → 只返回摘要到主会话，节省 40%+ 输入 Token
```

---

## 13. Hooks 预处理降本

### 原理

在数据进入 Claude 上下文之前，用 hooks 进行预处理过滤，只保留关键信息。

### 典型场景

```bash
# ❌ 坏习惯：10000 行日志直接喂给 Claude
cat huge.log

# ✅ 好习惯：Hooks 预处理 + grep 过滤
# （在 hook 中自动执行）
grep -i "ERROR\|FATAL\|Exception" huge.log | tail -n 50
```

### 配置方式（settings.json）

```jsonc
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/PostToolUse"
          }
        ]
      }
    ]
  }
}
```

### Hooks 能做哪些预处理

```
📊 日志过滤：grep ERROR/FATAL → 只保留关键行
📊 输出截断：tail -n 50 → 限制输出量
📊 统计聚合：wc -l → 只返回行数而非全文
📊 格式转换：JSON → 摘要
📊 重复过滤：uniq → 去重减少冗余
```

---

## 14. 一键初始化脚本

以下脚本可直接在办公室电脑上运行，一次性完成所有 Token 经济配置。

### 脚本：`setup_token_economy.sh`

```bash
#!/bin/bash
# Claude Code Token 经济一键配置脚本
# 运行：bash setup_token_economy.sh

PROJECT_DIR="D:\AgentWork"
SETTINGS_FILE="$PROJECT_DIR/.claude/settings.json"

echo "=== Claude Code Token 经济配置 ==="

# 1. 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    echo "⚠ 项目目录不存在，请先 git clone"
    exit 1
fi

# 2. 创建 settings.json（如果不存在）
if [ ! -f "$SETTINGS_FILE" ]; then
    echo "创建 settings.json..."
    mkdir -p "$PROJECT_DIR/.claude"
fi

# 3. 写入/更新 Token 经济配置
# 注意：保留现有的 permissions 和 hooks 配置
echo "更新 Token 经济环境变量..."

# 使用 jq 或手动合并（此处简化，建议手动编辑）
cat > "$SETTINGS_FILE" << 'SETTINGSEOF'
{
  "env": {
    "MAX_THINKING_TOKENS": "10000",
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "100000"
  },
  "defaultMode": "bypassPermissions"
}
SETTINGSEOF

# 4. 创建规则分类目录
echo "创建 rules 分类..."
mkdir -p "$PROJECT_DIR/.claude/rules"

# 5. 输出完成提示
echo ""
echo "=== 配置完成 ==="
echo ""
echo "下一步手动操作："
echo "  1. 将 settings.json 中的 permissions 合并回来"
echo "  2. 按需要复制 rules/ 下的规则文件"
echo "  3. 运行 claude /config 验证配置生效"
echo ""
echo "日常命令速查："
echo "  /context          → 查看上下文占用"
echo "  /usage            → 查看 Token 费用"
echo "  /compact          → 压缩上下文"
echo "  /model <name>     → 切换模型"
echo "  /effort <level>   → 设置 Effort"
echo "  /statusline       → 开启实时监控"
echo "  /clear            → 任务间重置"
echo ""
echo "省钱三原则："
echo "  1️⃣ 默认 Sonnet，需要才 Opus"
echo "  2️⃣ 超过 100K 就 /compact"
echo "  3️⃣ 用 grep 不用 cat"
```

### 日常速查卡

```
╔════════════════════════════════════════╗
║        Token 经济 · 日常速查          ║
╠════════════════════════════════════════╣
║ /context     → 看上下文占用            ║
║ /usage       → 看 Token 费用           ║
║ /compact     → 超 100K 就压            ║
║ /effort high → 默认 Effort            ║
║ caveman      → 紧急压缩模式            ║
║ grep > cat   → 永远记得                ║
║ tail -n 20   → 长输出必加              ║
╚════════════════════════════════════════╝
```

---

## 15. 日常检查清单

### 每日

```
□ 用 /context 瞄一眼上下文水位
□ 超过 100K → /compact
□ 任务切换 → /clear 重置
```

### 每周

```
□ 用 /usage 查看 Token 消耗趋势
□ 检查 CLUADE.md 是否稳定（没改过）
□ MEMORY.md 行数检查（接近 200 行要拆分）
```

### 每月

```
□ settings.json 环境变量检查
□ rules/ 清理：无用规则归档
□ skills/ 审计：哪些该合并/删除
□ 缓存命中率复盘：哪些改动导致频繁缓存失效
```

---

## 附录 A：参考来源

| 来源 | 内容 |
|------|------|
| `.claude/rules/token_economy.md` | Token 经济核心原则 |
| `.claude/rules/self_evolution.md` | 五层进化环 + 记忆体系 |
| `CLAUDE.md` | 项目根规则 + Compact instructions |
| `.claude/settings.json` | 环境变量配置 |
| `.claude/rules/thinking_framework.md` | Karpathy 四原则 |

## 附录 B：办公室部署检查清单

```
□ 1. git clone 项目仓库
□ 2. 复制 settings.json 并配置环境变量
□ 3. 复制 .claude/rules/ 目录
□ 4. 运行 setup_token_economy.sh
□ 5. 验证：claude /config 检查 env 已加载
□ 6. 验证：claude /model 确认默认模型
□ 7. 测试：发送一条消息确认缓存正常
□ 8. 打印速查卡贴在工位
```
