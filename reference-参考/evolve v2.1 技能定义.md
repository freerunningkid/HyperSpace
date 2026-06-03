# evolve v2.1 — 演化闭环

> 版本: v2.1 · 2026-06-02
> 升级: +三问门禁 +模式检测(减配) +轻量审计
> 运行位置: inline（主 Agent 上下文内执行）
> 源文件: `D:\Reasonix\skills\evolve.md`

---

## 触发条件

- 会话结束（用户说"好了/就这些/休息"等）
- 用户主动要求（"整理一下""记下来""保存"）
- 项目阶段完成（一次成功部署、一个 Issue 关闭）

---

## 流程概览

```
Step 1: 扫描对话 → 提取三类资产
Step 2: 【新增】三问写入门禁
Step 3: 写入对应 memory 文件
Step 4: 【增强】MEMORY.md 健康度 + 轻量审计
Step 5: 【新增】模式检测（减配版）
Step 6: 输出 EVOLVE REPORT
```

---

## Step 1：扫描对话

从当前会话中提取三类资产：

| 类型 | 检测信号 | 示例 |
|------|---------|------|
| 新知识（Knowledge） | 用户提供的事实、学到的新概念 | "MCP 用 stdio 传输" |
| 纠错记录（Correction） | 用户纠正、系统犯错、意外行为 | "路径应该是 scripts/lib/ 不是 scripts/" |
| 项目决策（Decision） | 选型、方案选择、边界划定 | "暂缓 GitHub MCP，用 gh CLI" |
| 【新增】模式线索（Pattern Clue） | 同类任务出现频次 | 第 3 次提到"整理 PDF" |

**过滤规则**：跳过临时对话（"帮我查一下天气"）、纯打招呼、已在 memory 中完全一致的条目。

---

## Step 2：三问写入门禁（新增）

对于 Step 1 提取的每条资产，在执行写入前依次问三个问题：

### 问题一：这是新增、修正、还是废弃？

| 类型 | 判定条件 | 写入动作 |
|------|---------|---------|
| `new` | memory 中不存在此内容 | 追加到对应文件 |
| `correction` | 已有内容但已被更新替代 | 更新原条目 + 记入 changelog |
| `deprecation` | 已有内容但已不再有效 | 标记原条目标为 `archived` + 记入 changelog |
| `skip` | 临时信息、无法归类 | 不写入 |

判定逻辑：
```
if 完全不存在于 memory → new
if 存在但内容矛盾（用户纠正、版本更新） → correction
if 存在但明确废弃（"不用这个方案了"） → deprecation
else → skip
```

### 问题二：置信度够吗？

| 置信度 | 条件 | 写入策略 |
|--------|------|---------|
| S 级 | 用户明确表述 | 立即写入，confidence = 0.9 |
| A 级 | 从用户行为推断，≥3 次 | 写入，confidence = 0.7 |
| B 级 | 系统经验，自己推导的 | 写入，confidence = 0.5 |
| C 级 | 单次观察，未验证 | 暂不写入，记录到 gaps.md |

判定逻辑：
```
if 用户直接说出口（"我喜欢简洁回复"） → S 级
if 从 3 次以上行为推断（每次都催"简洁点"） → A 级
if 从一次经验衍生（上次这样做成功了） → B 级
if 从一次观察推测（感觉用户可能喜欢） → C 级 → 不写入
```

### 问题三：与现有记忆冲突吗？

```
for 待写入条目的关键断言:
    search memory/ 中所有 status=active 的条目
    if 找到语义冲突:
        → 不覆盖写入
        → 写入 memory/meta/conflicts.md
        → 在 EVOLVE REPORT 中标记 "⚠️ 发现冲突"
```

**门禁总体决策**：

```
if 回答了三问且不是 skip:
    status = tentative | confirmed | stable
    write_type = new | correction | deprecation
    source_type = user_explicit | user_behavior | self_derived | external
    → 执行写入
else:
    → 跳过，不写入
```

### 三问门禁流程图

```
待写入资产
    │
    ├─→ Q1: 类型？──── new ──→ 继续
    │       │                │
    │       ├── correction ──→ 继续（记录旧→新变化）
    │       │                │
    │       ├── deprecation ─→ 继续（标记 archived）
    │       │                │
    │       └── skip ────────→ ✕ 丢弃，记入 changelog 统计
    │
    ├─→ Q2: 置信度？── S/A 级 ──→ 继续
    │               │
    │               ├── B 级 ───→ 继续（但 confidence = 0.5）
    │               │
    │               └── C 级 ───→ ✕ 不写入 → 写入 gaps.md 候选
    │
    └─→ Q3: 冲突？── 无冲突 ──→ 执行写入 ✅
                    │
                    └── 有冲突 ──→ 写入 conflicts.md → 标记 ⚠️
```

---

## Step 3：写入对应 memory 文件

根据 Q1 的类型执行写入：

### new —— 追加

根据内容类型写入对应文件：

| 资产类型 | 目标文件 | frontmatter 模板 |
|---------|---------|-----------------|
| 用户偏好 | `memory/profiles/preferences.md` | 见下方 |
| 项目决策 | `memory/decisions/decisions.md` | 见下方 |
| 领域知识 | `memory/knowledge/domain.md` | 见下方 |
| 错误教训 | `memory/lessons/errors.md` | 见下方 |
| 模式线索 | `memory/patterns/active.md` | 见下方 |

每条条目写入时携带 frontmatter：

```yaml
---
id: K-20260602-001              # K=Knowledge, L=Lesson, D=Decision, P=Pattern
status: tentative                # hypothesis | tentative | confirmed | stable | archived
write_type: new                  # new | correction | deprecation
confidence: 0.7                  # 0.0 ~ 1.0
source_type: user_explicit       # user_explicit | user_behavior | self_derived | external
source_session: "2026-06-02 CLI配置讨论"
observed_count: 1
ttl: 2026-07-02                  # 默认 30 天，S 级永久
---
```

### correction —— 更新

```
1. 定位原条目（search memory/ 中所有文件）
2. 在原条目的 changelog 中追加:
   - 2026-06-02: correction - {old_summary} → {new_summary}, 原因: {reason}
3. 更新原条目的正文内容
4. 将原条目 status 改为 confirmed（被修正说明曾被使用）
```

### deprecation —— 废弃

```
1. 定位原条目
2. 将原条目 status 标记为 archived
3. 在原条目的 changelog 追加:
   - 2026-06-02: deprecation - {summary}, 原因: {reason}
4. 不移除文件（保留决策链）
```

---

## Step 4：健康检查 + 轻量审计（增强）

### 4a MEMORY.md 行数健康度（已有逻辑，增强）

```
read MEMORY.md line_count
if > 200:
    立即拆分：将最旧的 50 行移至 memory/archive/
    追加 changelog: "MEMORY.md 行数 215→165，已拆分"
```

### 4b 轻量审计清单（新增）

每次 evolve 执行时，顺带检查以下 5 项（不是所有项，挑可自动检测的）：

```
[AUTO] MEMORY.md 行数 → [ok / >200 / >300 / >500]
[AUTO] 是否已超过 7 天未完整审计 → 最近一次审计日期 vs 当前日期
[AUTO] 是否有 unresolved 冲突 → search memory/meta/conflicts.md status=unresolved
[AUTO] 是否有 30 天未使用的 Skill → search skills/active/*.md last_used vs 当前日期
[AUTO] 是否有跨过阈值的 Pattern Candidate → search memory/patterns/active.md evidence_count >=5 && status=candidate
```

如果是完整审计（触发条件：用户主动要求 / 7 天未审计 / 本次审计有异常项），增加：

```
[MANUAL提示] 是否存在重复内容 → 提示用户（无语义模型时无法自动）
[MANUAL提示] 是否存在失效规则 → 提示用户确认
[MANUAL提示] 安全边界检查 → 提示用户审计 shellAllowed
```

### 审计结果输出

```
--- LIGHT AUDIT ---
MEMORY.md: 42 lines ✅
Last full audit: 2026-05-28 (5 days ago) ✅
Conflicts unresolved: 0 ✅
Skills unused >30d: 0 ✅
Pattern candidates ready: 1 → P-20260602-001 (evidences: 5) ⚠️
Skill proposals pending: 1 → SKILL-PROPOSAL-20260602-001
--- END ---
```

---

## Step 5：模式检测 — 减配版（新增）

### 原理

基于关键词频率检测，不依赖语义模型。在每次 evolve 的 Step 1 扫描对话时，对提取的资产进行关键词分类和计数。

### 5a 关键词分类

维护一个轻量分类表（硬编码在 Skill 中，随使用扩展）：

```
OCR相关: ocr, scan, 扫描, 识别, 图片文字, tesseract
PDF相关: 整理PDF, pdf, 表格提取, 多栏
MCP相关: mcp服务器, mcp配置, voice_server, filesystem
部署相关: 迁移, 部署, setup, 安装, 配置环境
测试相关: 调试, 测试, 报错, 失败, 排查
TTS相关: tts, 语音, speak, 朗读
同步相关: sync, git, push, pull, commit
```

### 5b 计数和阈值

```
memory/patterns/active.md 中已有记录 → 存量计数
本次检测到新出现 → 增量 +1
更新 observed_count
```

### 5c 阈值判断

```
if observed_count >= 10:
    → "这个工作流已稳定，建议升级为 Official Skill"
    → 写入 skills/proposals/ + 通知用户

elif observed_count >= 5:
    → "这个工作流出现了 5 次，可以开始考虑 Skill 化"
    → 写入 skills/proposals/（作为 Proposal） + 通知用户

elif observed_count >= 3:
    → "检测到重复任务，写入 patterns/active.md"
    → 在 patterns/active.md 中创建或更新条目
    → 在 EVOLVE REPORT 中列出

else:
    → 记数 +1，不做其他操作
```

### 5d 误报处理

```
if 用户对 Skill 建议明确说"不用"或"不是"：
    → patterns/active.md 对该条追加 FalseAlarm 标记
    → 同一模式不会再次建议（除非 observed_count 继续增长 5+）
    
if 用户对 Skill 建议说"我再想想"：
    → 不做标记，保持 candidate，下次 evolve 再次提示（但不超过 3 次）
```

### 5e 模式检测流程图

```
Step 1 提取的关键词
    │
    ├─→ 匹配分类表
    │       │
    │       ├── 命中已有分类 → 对应 ID 的 observed_count +1
    │       │
    │       └── 未命中 → 忽略（单次不成模式）
    │
    ├─→ 更新 patterns/active.md 中对应条目
    │
    └─→ 阈值判断 → <3: 仅计数
                   ≥3: 写入 patterns/active.md
                   ≥5: 写入 skills/proposals/
                   ≥10: 升级候选
```

---

## Step 6：输出 EVOLVE REPORT

```
═══════════════════════════════════════
 EVOLVE REPORT — v2.1
═══════════════════════════════════════

📦 新知识（New Knowledge）
  • K-20260602-001: [摘要] — [confidence: 0.9, source: S级]

🔧 纠错记录（Corrections）
  • L-20260602-001: [摘要] — 已更新 lessons.md

📋 项目决策（Decisions）
  • D-20260602-001: [摘要] — 已写入 decisions/

🔍 模式检测（Pattern Detection）
  ⚠ P-20260602-001: "用户频繁处理 PDF" — observed_count: 5/5
    → 已达到 Skill Proposal 阈值，建议创建新 Skill

📊 轻量审计（Health Check）
  MEMORY.md: 48 行 ✅
  Unresolved conflicts: 0 ✅
  Skills unused >30d: 0 ✅
  Last full audit: 2026-05-28 (5 days ago) ✅

📝 记忆变更日志
  +新增: memory/knowledge/domain.md (K-20260602-001)
  ~修正: memory/lessons/errors.md (L-20260520-003)
═══════════════════════════════════════
```

---

## 约束

- **禁止直接膨胀 MEMORY.md** — 正文写入对应详情文件，MEMORY.md 只保留指针
- **禁止重复写入** — 写入前必须 search memory/ 去重
- **禁止修改 CLAUDE.md** — 缓存全废
- **禁止猜测置信度** — 来源不明时走 C 级 → 不写入 → 记入 gaps.md
- **模式检测误报** — 用户否定后标记 FalseAlarm，同一模式 3 次以内不再建议

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 2026-05-xx | 初始版本 |
| v2 | 2026-06-02 | +纠错记录 +决策记录 |
| **v2.1** | **2026-06-02** | **+三问门禁 +模式检测(减配) +轻量审计** |

---

## 附：增量改动清单（从 v2 到 v2.1 具体改哪里）

| 改动点 | 位置 | 类型 |
|--------|------|------|
| Step 1 增加"模式线索"提取 | 检测信号部分 | 增加 |
| 新增 Step 2 三问门禁 | 新步骤 | 增加 |
| Step 3 frontmatter 增加 status/write_type/confidence/source_type | 写入模板 | 增加 |
| Step 4a MEMORY.md 行数检查增强 | 已有逻辑 | 增强 |
| Step 4b 轻量审计清单 | 新增步骤 | 增加 |
| Step 5 模式检测 | 新增步骤 | 增加 |
| EVOLVE REPORT 增加"模式检测"和"轻量审计"区块 | 输出 | 增加 |
| 约束增加"模式检测误报" | 约束 | 增加 |
