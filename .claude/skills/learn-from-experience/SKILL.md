---
name: learn-from-experience
description: 从成功的多步骤任务中自动提取可复用 Skill，写入 .reasonix/skills/。Hermes 式经验→技能闭环
last_used: 2026-06-04
---
# learn-from-experience — 自动技能提取

> 定位：**子代理（subagent）**
> 灵感：Hermes Agent 的自动技能创建机制——复杂任务完成后自动提取可复用的 Playbook

## 触发时机

由主 Agent 在以下场景调用：
- 会话结束时（复杂任务已成功完成）
- 用户说"记住这个做法""以后遇到类似的..."
- `evolve` 检测到模式计数 ≥5 时

## 用法

```
run_skill("learn-from-experience", "<任务描述>")
```

任务描述格式：
```
任务摘要: <刚才做了什么>
成功关键: <哪些步骤是关键的、可复用的>
场景特征: <什么场景下未来可能会再用>
文件路径: <涉及的文件>
工具/命令: <用到的关键命令>
```

## 子代理工作流程

### Step 1：分析经验价值

判断是否值得抽成 Skill：
- ✅ 任务涉及 ≥3 步操作
- ✅ 步骤可标准化（不是一次性操作）
- ✅ 未来有复用可能
- ❌ 简单的单步操作 → 不创建，返回"不值得"
- ❌ 纯探索性操作 → 不创建

### Step 2：提取 Skill 骨架

参考现有 Skill 的 frontmatter 格式，生成：

```markdown
---
name: <kebab-case-name>
description: <一句话描述>
last_used: <当前日期>
---
# <Skill 名称>

> 自动提取自 [任务摘要]

## 使用场景

<什么情况下用>

## 步骤

1. <步骤 1>
2. <步骤 2>
...

## 验证方法

<如何验证成功>
```

### Step 3：写入 Skills 目录

写入 `D:\Reasonix\.reasonix\skills\<name>.md`

### Step 4：返回报告

```
══════════════════════════
 LEARN-FROM-EXPERIENCE REPORT
══════════════════════════
🟢 已创建新 Skill: <name>
📖 路径: .reasonix/skills/<name>.md
📝 摘要: <描述>
💡 下次遇到类似场景，直接 /<name> 或 run_skill("<name>", ...)
══════════════════════════
```

## 铁律

- **不重复创建** — 写前检查名字是否已存在，存在则更新 `last_used`
- **只写可复用的** — 一次性操作不写
- **质量门禁** — 步骤少于 3 步或无法标准化 → 跳过
- **不强行提取** — 没有找到有价值的模式就如实报告"没有值得提取的 Skill"
