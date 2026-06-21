---
name: sync
description: 远程同步：检查仓库 → 分析变更 → 智能生成 commit 摘要 → git add/commit/push
last_used: 2026-06-04
---
# sync — 远程同步器

> 将本地状态安全推送到远程仓库 GitHub。

## 运行模式

- **mode**: inline
- **trigger**: 用户手动调用

---

## 执行流程

### Step 1: 检查仓库状态

```bash
git status
```

### Step 2: 分析变更

输出变更摘要：

```
新增: N 个文件
修改: N 个文件
删除: N 个文件
```

### Step 3: 自动生成 Commit 摘要

根据变更内容推断类型：

| 类型 | 适用场景 |
|------|---------|
| `docs:` | 更新 memory/、knowledge-知识库/、reference-参考/ |
| `feat:` | 新增 Skill、脚本、工具 |
| `refactor:` | 重命名、移动文件、结构调整 |
| `fix:` | 修复 Bug、更正错误 |
| `chore:` | 配置更新、清理、归档 |

格式：`<type>: <简短摘要>`

示例：
```
docs: update memory after session
feat: add evolve skill
refactor: reorganize archive structure
```

### Step 4: 提交

```
git add -A
git commit -m "<type>: <summary>"
```

### Step 5: 推送

```
git push
```

---

## 失败恢复

若 `git push` 失败（网络问题/冲突）：

1. 记录错误信息
2. 输出：

```
⚠️ 远程同步失败
错误: <具体错误信息>
建议: 检查网络连接，稍后重试
```

3. **不要反复重试**（避免浪费 Token）

---

## 成功标准

- [ ] working tree clean
- [ ] commit 已创建
- [ ] remote 已更新

## 输出格式

```
✅ Sync 完成
Commit: <type>: <summary>
推送: 成功
```
