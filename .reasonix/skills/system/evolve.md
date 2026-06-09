---
name: evolve
description: 进化闭环 v3.0：铁律化 + 必选默契简报 + 假设验证 + 自动调 learn-from-experience → 写入嵌套 memory/
last_used: 2026-06-04
---
# evolve v3.0 — 演化闭环

> 🚨 **会话末铁律（不可跳过）**：每次会话最后一步 = 运行 evolve。遗忘 = 进化停滞 = 事故。优先级仅低于 TTS。
>
> 版本: v3.0 · 2026-06-09
> 升级: +铁律化 +必选默契简报 +假设验证(tentative交叉验证) +自动调learn-from-experience
> 运行位置: inline（主 Agent 上下文内执行）

## 运行模式

- **mode**: inline
- **trigger**: 🚨 会话结束（铁律，不可跳过） / 用户主动要求 / 项目阶段完成
- **约束**: 必须在主会话上下文中运行

## 设计原则

- 认知与维护解耦：主会话负责思考，evolve 负责沉淀
- 禁止直接膨胀 MEMORY.md（MEMORY.md 只放索引，详情放 `memory/*/` 子目录）

---

## Step 1：扫描对话，提取四类资产

从当前会话中识别：

| 类型 | 检测信号 | 示例 |
|------|---------|------|
| 新知识（Knowledge） | 用户提供的事实、学到的新概念 | "MCP 用 stdio 传输" |
| 纠错记录（Correction） | 用户纠正、系统犯错、意外行为 | "路径应该是 scripts/lib/" |
| 项目决策（Decision） | 选型、方案选择、边界划定 | "暂缓 GitHub MCP，用 gh CLI" |
| 模式线索（Pattern Clue） | 同类任务出现频次 | 第 3 次提到"整理 PDF" |

**过滤规则**：跳过临时对话、纯打招呼、已在 memory 中完全一致的条目。

---

## Step 1.5：思维洞察 + 默契简报（必选）

**必须完成**。即使没有新的 tentative 条目写入，也必须更新 `memory/meta/health.md` 中的默契简报。

### 1.5a 提炼思维洞察

从当前会话中提炼 **至少 1 条**关于小金东思维方式的洞察：

| 类型 | 检测信号 | 写入目标 |
|------|---------|---------|
| 决策风格 | 他在多个选项间如何选择 | `memory/profiles/thinking-style.md` |
| 信任触发 | 他什么时候说"对""就是这样" | 同上 |
| 不耐烦信号 | 跳过/沉默/直接给答案 | 同上 |
| 沟通节奏 | 他主动展开 vs 等指令 | 同上 |

**约束**：
- 有足够证据 → confidence ≥ 0.7，写入 thinking-style.md，标记 `status: tentative`
- 证据不足 → 不强行写入 thinking-style.md，但**默契简报必须填写**（见下）
- 与现有条目冲突时追加为"待验证对立假设"而非覆盖

### 1.5b 填写默契简报（必填）

无论是否有新洞察写入，**必须更新** `memory/meta/health.md` 中的「默契简报」段（在 Step 4 执行时写入）。

填写规则：
- 默契度方向：基于本次会话中的纠正次数、预判命中/未中比例判断（↑/→/↓）
- 亮点：本次会话中小金东说"对""就是这样"或明显满意的点
- 盲区：本次会话中猜错、被纠正、需要多次确认的方向
- 假设验证摘要：引用 Step 1.6 的结果

---

## Step 1.6：假设验证（tentative 条目交叉验证）

**必须完成**。检查所有 `status: tentative` 的记忆条目，用本次会话的观察交叉验证。

### 检查范围

- `memory/profiles/thinking-style.md` — 所有 `status: tentative` 条目
- `memory/knowledge/domain.md` — 所有 `status: tentative` 条目
- `memory/lessons/errors.md` — 所有 `status: tentative` 条目
- 其他 `memory/` 子目录中的 tentative 条目

### 验证动作

| 本次会话观察 | 动作 |
|-------------|------|
| 新证据**支持**该假设 | `observed_count += 1`；若 confidence 因此 ≥0.9 则 `status → confirmed` |
| 新证据**反驳**该假设 | 记录在条目 changelog；confidence -= 0.2；若 confidence <0.5 则 `status → disputed` |
| 无相关观察 | 记录 `last_checked: <日期>`, 无变更 |

### 输出

在 EVOLVE REPORT 中报告：
- 检查了 N 条 tentative 条目
- M 条获得新证据（含支持/反驳）
- 是否有条目从 tentative → confirmed

---

## Step 2：三问写入门禁

对于 Step 1 提取的每条资产，依次过三关后写入。

### Q1：新增、修正、还是废弃？

| 类型 | 判定 | 动作 |
|------|------|------|
| `new` | memory 中不存在 | 追加到对应文件 |
| `correction` | 已有但需更新 | 更新原条目 + 记 changelog |
| `deprecation` | 已有但已失效 | 标 `archived` + 记 changelog |
| `skip` | 临时/无法归类 | 不写入 |

### Q2：置信度够吗？

| 级别 | 条件 | confidence | 动作 |
|------|------|-----------|------|
| S 级 | 用户明确表述 | 0.9 | 立即写入 |
| A 级 | 行为推断 ≥3 次 | 0.7 | 写入 |
| B 级 | 系统经验推导 | 0.5 | 写入（标 tentative） |
| C 级 | 单次未验证 | — | 不写入 → `memory/meta/gaps.md` |

### Q3：与现有记忆冲突吗？

搜索 `memory/` 下 `status=active` 的条目：
- 无冲突 → 写入
- 有冲突 → 不覆盖，写入 `memory/meta/conflicts.md`，REPORT 标 ⚠️

---

## Step 3：写入对应文件（带 frontmatter）

| 资产类型 | 目标文件 |
|---------|---------|
| 用户偏好 | `memory/profiles/preferences.md` |
| 技术经验 | `memory/knowledge/domain.md` |
| 错误教训 | `memory/lessons/errors.md` |
| 架构决策 | `memory/decisions/decisions.md` |
| 模式线索 | `memory/patterns/active.md` |

每条写入携带 frontmatter：

```yaml
id: K-YYYYMMDD-NNN
status: tentative
write_type: new
confidence: 0.7
source_type: user_explicit
observed_count: 1
```

### correction/deprecation 特殊处理

- correction → 定位原条目 → changelog 追加变更 → status → confirmed
- deprecation → 定位原条目 → status → archived → changelog 追加

---

## Step 4：健康检查 + 轻量审计

### 4a MEMORY.md 行数

≤180 ✅ / 181-200 ⚠️ / >200 🔴 立即拆分

### 4b 轻量审计（5 项自动检查）

- MEMORY.md 行数
- 连续未审计天数（检查 `memory/meta/health.md` last_audit）
- Unresolved 冲突数（search `memory/meta/conflicts.md`）
- 30 天未使用的 Skill（检查 `.reasonix/skills/*.md` 中各 skill 的 `last_used` 字段）
- Pattern Candidates 就绪（search `memory/patterns/active.md` evidence_count ≥5）

写入 `memory/meta/health.md`。

### 4c Skill last_used 更新

扫描当前会话中调用过的 Skill（通过 `run_skill` / slash 命令或显式触发检测），更新对应 `.reasonix/skills/<name>.md` 的 `last_used` frontmatter 字段为当前日期。

未在本会话调用的 Skill 保持原有 `last_used` 不变。

---

## Step 5：模式检测（减配版）

### 关键词分类表

```
OCR/文档: ocr, scan, 扫描, 识别
MCP 工具: mcp服务器, mcp配置, voice_server
部署运维: 迁移, 部署, setup, 安装
测试调试: 调试, 测试, 报错, 排查
TTS 语音: tts, 语音, speak, 朗读
同步: sync, git, push, commit
```

### 阈值

- <3 仅计数
- ≥3 → `patterns/active.md`
- ≥5 → 自动调用 `run_skill("learn-from-experience", "模式: <描述> · 证据数: <N> · 实例: <列举>")` → 由子代理判断是否创建 Skill
- ≥10 → 建议创建 Official Skill（写入 `.reasonix/skills/`）

### 误报

用户说"不用" → 标记 FalseAlarm，不重复建议
用户说"再想想" → 保持 candidate，最多提示 3 次

---

## Step 6：EVOLVE REPORT

```
═══════════════════════════════════════
 EVOLVE REPORT — v3.0
═══════════════════════════════════════

📦 新知识
  • K-YYYYMMDD-NNN: [摘要] — S级

🔧 纠错
  • L-YYYYMMDD-NNN: [摘要] → lessons/errors.md

📋 决策
  • D-YYYYMMDD-NNN: [摘要] → decisions/decisions.md

🧠 默契简报
  本周默契度：[↑/→/↓]
  亮点：[...]
  盲区：[...]

🔬 假设验证
  检查 tentative 条目: N 条
  获新证据: M 条（支持 X / 反驳 Y）
  状态升级: [从 tentative → confirmed 的条目]

🔍 模式检测
  ⚠ P-YYYYMMDD-NNN: "[描述]" — N/N 达到阈值
  🤖 自动触发 learn-from-experience: [是/否]

📊 健康审计
  MEMORY.md: N 行 ✅
  Conflicts: 0 ✅ / Skills unused: 0 ✅

📝 变更日志
  +新增: [文件] ([ID])
  ~修正: [文件] ([ID])
═══════════════════════════════════════
```

每次写入后追加 `memory/meta/changelog.md`。

---

## 约束

- ❌ 禁止直接膨胀 MEMORY.md
- ❌ 禁止重复写入（写前 search 去重）
- ❌ 禁止修改 CLAUDE.md（缓存全废）
- ❌ 禁止猜测置信度（不明 → C 级 → gaps.md）
- ⚠️ 误报后标记 FalseAlarm，不重复建议

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 2026-05 | 初始版本 |
| v2 | 2026-06-02 | +纠错 +决策 |
| v2.1 | 2026-06-02 | +三问门禁 +模式检测 +轻量审计 +frontmatter |
| v2.2 | 2026-06-04 | +last_used跟踪 +路径修复 +审计指标可计量化 |
| **v3.0** | **2026-06-09** | **+铁律化 +必选默契简报 +假设验证 +自动调learn-from-experience** |
