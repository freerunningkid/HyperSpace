# Agent Protocol v0.1 — 2B 双引擎接口标准

> **定位**: 接口约定，非共享代码库。约束输入输出，不约束实现。
> **实现方**: Reasonix (Python/Go) · Claude Code (Node.js)
> **维护**: 两份独立实现，按协议对齐，各自演进。
> **版本**: v0.1 · 2026-06-09 · **Review**: ClaudeCode 2B ✅ (3 blockers resolved)

---

## 设计原则

1. **只定接口，不定实现** — 像 USB-C：两端实现不同，但插上就能用
2. **推荐实现，非强制规范** — 不实现不报错，只是能力声明
3. **核心对齐，差异保留** — 文件编辑/工具调用/记忆读写对齐；语气/优化策略/专属工具各自保留
4. **向后兼容** — 新增字段不破坏旧字段

---

## 1. 文件编辑接口

### edit_file

```
edit_file(path: str, old_string: str, new_string: str) -> EditResult
```

| 字段 | 类型 | 说明 |
|------|------|------|
| path | string | 绝对路径或工作区相对路径 |
| old_string | string | 精确匹配的原文（必须唯一） |
| new_string | string | 替换文本（空字符串 = 删除） |

**EditResult**:
```json
{
  "status": "ok" | "error",
  "path": "...",
  "diff": "...",       // unified diff
  "error": "..."       // 仅 status=error 时
}
```

**行为约束**:
- old_string 匹配失败 → status=error，不做部分修改
- 多文件修改必须用 multi_edit 或其他原子化方式
- 实现方可附加验证步骤（lsp_diagnostics / 重新读取确认）

---

### multi_edit

```
multi_edit(path: str, edits: Edit[]) -> MultiEditResult
```

| 字段 | 类型 | 说明 |
|------|------|------|
| path | string | 目标文件 |
| edits | Edit[] | 有序编辑列表，每步看到上一步的结果 |

**Edit**:
```json
{
  "old_string": "原文",
  "new_string": "替换文",
  "replace_all": false  // 可选，true=替换所有出现
}
```

**MultiEditResult**:
```json
{
  "status": "ok" | "partial" | "error",
  "path": "...",
  "applied": 3,          // 成功应用的编辑数
  "failed_at": 2,        // 失败的编辑序号（1-based），status=error/partial 时
  "diff": "..."
}
```

**关键行为**: 第 N 步失败 → 整批回滚，文件不变。原子性保障。

---

### write_file（新建/覆盖写入）

```
write_file(path: str, content: str) -> WriteResult
```

**WriteResult**:
```json
{
  "status": "ok" | "error",
  "path": "...",
  "bytes_written": 5700,
  "error": "..."
}
```

**行为约束**:
- 新建文件或覆盖已有文件
- 父目录不存在时自动创建
- 写入后应验证（重新读取确认内容正确）

---

### delete_file（删除文件/符号）

```
delete_file(path: str) -> DeleteResult
```

**DeleteResult**:
```json
{
  "status": "ok" | "error",
  "path": "...",
  "error": "..."
}
```

---

### 读文件

```
read_file(path: str, offset?: int, limit?: int) -> ReadResult
```

**ReadResult**:
```json
{
  "status": "ok" | "error",
  "path": "...",
  "content": "...",        // 带行号前缀
  "total_lines": 500,
  "offset": 0,
  "limit": 200
}
```

---

### 搜索接口

```
grep(pattern: str, path?: str, glob?: str) -> GrepResult
glob(pattern: str, path?: str) -> GlobResult
```

**GrepResult**:
```json
{
  "status": "ok" | "error",
  "pattern": "def main",
  "matches": [
    { "path": "src/main.py", "line": 42, "text": "def main():" }
  ],
  "total": 3,
  "truncated": false
}
```

**GlobResult**:
```json
{
  "status": "ok" | "error",
  "pattern": "**/*.py",
  "paths": ["src/main.py", "lib/utils.py"],
  "total": 2
}
```

---

### Shell 执行

```
bash(command: str, timeout?: int, run_in_background?: bool) -> BashResult
```

**BashResult**:
```json
{
  "status": "ok" | "error" | "timeout",
  "command": "pytest -q",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "..."
}
```

**约定**:
- 超时默认 60s，最大 300s
- 危险命令（rm -rf / del /f / format 等）需确认
- stdout 截断到 50,000 chars

---

## 2. 工具调用接口

### 工具定义（Tool Schema）

```json
{
  "name": "tool_name",
  "description": "一句话描述，Agent 决策用",
  "inputSchema": {
    "type": "object",
    "properties": {
      "param": { "type": "string", "description": "..." }
    },
    "required": ["param"]
  }
}
```

**约定**:
- name 使用 snake_case（两边统一）
- description 面向 Agent 决策，不面向人类文档
- inputSchema 遵循 JSON Schema 规范

---

### 工具调用结果（Tool Result）

```json
{
  "status": "ok" | "error" | "timeout",
  "tool": "tool_name",
  "output": "...",          // 人类可读的输出
  "error": "..."            // status=error/timeout 时
}
```

**约定**:
- output 长度建议 ≤ 10,000 chars（超长内容用截断+摘要）
- 时间戳、临时路径等每次变化的噪声 → 摘要化（如 `[截图] 1920x1080 (base64 已省略 500KB)`）

---

## 3. 记忆读写接口

### 记忆文件格式

记忆存储于 `memory/` 目录下的 Markdown 文件。

**最低约定格式**（两边必须兼容）:

```markdown
---
id: K-YYYYMMDD-NNN    // 可选，唯一标识
type: <见下方映射表>
status: active | archived | tentative
confidence: 0.0-1.0   // 可选
---
# 标题

正文内容（Markdown）
```

#### type 枚举映射表（两边枚举不同，按此互译）

| Reasonix type | Claude Code type | 语义 |
|--------------|-----------------|------|
| `knowledge` | `reference` | 技术知识、事实 |
| `preference` | `user` | 用户偏好、习惯 |
| `decision` | `project` | 架构决策、项目约束 |
| `correction` | `feedback` | 纠错记录、反馈 |

**约定**:
- 每条记忆一个 .md 文件
- 必须有的 frontmatter 字段: `type`, `status`
- 可选 frontmatter: `id`, `confidence`, `created`, `last_updated`
- 正文自由格式
- 两边写入用各自枚举，读取时按映射表翻译。不改已有文件。

---

### 记忆操作

```
remember(type, title, body) -> MemoryResult
forget(name) -> MemoryResult
search(query) -> MemoryResult[]
```

**MemoryResult**:
```json
{
  "status": "ok" | "error",
  "name": "memory-slug",
  "path": "memory/xxx.md",
  "type": "knowledge",
  "title": "..."
}
```

**约定**:
- 两边可独立实现 remember/forget 的存储逻辑
- 但文件格式必须兼容（上面的 frontmatter 约定）
- 搜索实现自由（全文 grep / 语义向量 / FTS5 / 都可以）

---

## 4. 记忆互读通道

### 共享记忆目录

```
D:\Reasonix\memory\    ← 主记忆库（Git 同步）
```

**约定**:
- 两边都**读**这个目录
- 写操作各自走自己的 remember/forget，但写入文件格式遵循 §3
- 通过 Git pull/push 保持两边同步
- 冲突时以 `memory/meta/conflicts.md` 记录，不做自动合并

---

## 5. 工具能力声明

每个 Agent 实例应在启动时声明自己的能力矩阵。

```json
{
  "agent": "reasonix-2b",
  "protocol_version": "0.1",
  "capabilities": {
    "file_edit": true,        // edit_file / multi_edit / read_file / write_file / delete_file
    "search": true,           // grep / glob / find_file
    "shell": true,            // bash (命令执行)
    "subagent": true,         // task / dispatch
    "memory": true,           // remember / forget / search
    "permissions": true,       // 权限分层（Reasonix 已实现，CC 已实现）
    "workflow": true,          // 管道/循环/预算（CC 已实现）
    "cache_optimization": true // 缓存前缀优化
  },
  "tools": [
    // 可选，列出专属工具（不要求对齐）
    "execute_ahk",
    "execute_pywinauto"
  ]
}
```

---

## 版本演进

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1-draft | 2026-06-09 | 初始草案：文件编辑 + 工具调用 + 记忆读写 + 能力声明 |
| **v0.1** | **2026-06-09** | **Review 通过：+write_file +delete_file +grep +glob +bash +type枚举映射 +能力声明修正** |
| v0.2 | 未来 | + session override 权限层 + Workflow 编排接口详情 |
