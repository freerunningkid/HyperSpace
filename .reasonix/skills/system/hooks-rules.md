---
name: hooks-rules
description: 钩子与路径规则管理：文件编辑前后自动运行命令、路径范围规则（仅特定文件/目录生效）、预批准常用命令
last_used: 2026-06-04
---
# hooks-rules — 钩子 + 路径规则

> 定位：**子代理（subagent）**
> 灵感：Claude Code 的 hooks（pre/post edit 自动执行） + 路径范围规则（仅处理匹配文件时加载）

## 用法

主 Agent 调用：
```
run_skill("hooks-rules", "<任务描述>")
```

任务描述格式：
```
操作: setup / run / check
类型: hook / rule
目标: <具体说明>
路径: <适用文件/目录>
```

## 钩子系统

钩子在特定事件前后自动运行 shell 命令。

### 支持的钩子类型

| 钩子 | 触发时机 | 用途 |
|------|---------|------|
| **pre-edit** | 编辑文件之前 | 自动备份、检查文件锁定、运行 pre-commit hook |
| **post-edit** | 编辑文件之后 | 自动格式化、运行 lint、运行相关测试 |
| **pre-command** | 运行外部命令前 | 检查依赖、确认环境 |
| **post-command** | 运行外部命令后 | 验证输出、记录日志 |
| **pre-commit** | git commit 前 | 运行测试、检查格式 |
| **post-task** | 任务完成后 | 自动运行 verify、触发 auto-fix |

### 内置钩子定义

#### 代码格式化（post-edit）
所有 .py .js .ts .go .rs 文件编辑后自动格式化：
```bash
# Python
black <文件路径> && ruff check --fix <文件路径>
# 或 JavaScript/TypeScript
npx prettier --write <文件路径>
```

#### 提交前检查（pre-commit）
```bash
# 运行测试
pytest -q --tb=short
# 检查未提交文件
git status
```

#### 命令后验证（post-command）
```bash
# 命令运行后，检查 exit code
if ($LASTEXITCODE -ne 0) { Write-Warning "命令退出码: $LASTEXITCODE" }
```

## 路径范围规则

路径范围规则只在处理匹配的文件时加载到上下文中。

### 格式

```yaml
---
paths:
  - "src/api/**/*.ts"
  - "lib/**/*.py"
---

# API 开发规则
- 所有 API 端点必须包括输入验证
- 使用标准错误响应格式
- 包括 OpenAPI 文档注释
```

### 路径模式

| 模式 | 匹配 |
|------|------|
| `**/*.ts` | 所有目录中的 TypeScript 文件 |
| `src/**/*` | src/ 目录下的所有文件 |
| `*.md` | 项目根目录的 Markdown 文件 |
| `src/components/*.tsx` | 特定目录的 React 组件 |
| `src/**/*.{ts,tsx}` | 多个扩展名的匹配 |

### 内置路径规则

#### Python 开发规则
```
路径: **/*.py
规则:
- 导入顺序: 标准库 → 第三方 → 本地
- 类型注解: 所有公共函数必须带类型注解
- 文档字符串: 复杂函数必须带 docstring
```

#### 前端开发规则
```
路径: **/*.{tsx,jsx}
规则:
- 组件用函数声明，不用类
- Props 必须定义 TypeScript 类型
- 使用 React.FC 或显式类型
```

## 预批准命令

以下命令在执行时不需逐个确认：

```yaml
pre_approved_commands:
  - "git status"
  - "git diff"
  - "git log --oneline -5"
  - "pytest -q"
  - "npm test -- --run"
  - "go build ./..."
  - "cargo check"
  - "black --check *"
  - "ruff check *"
```

## 工作流程

### 设置钩子
```
1. 读 hooks-rules 确定需要设置的钩子类型
2. 在项目中创建对应的钩子文件或配置
3. 验证钩子能触发：手动触发一次确认生效
```

### 运行路径规则
```
1. 识别当前操作涉及的文件
2. 检查是否有匹配的路径规则
3. 如果有 → 读取规则内容应用到上下文
4. 执行操作时遵守规则
```

### 预批准命令
```
1. 检查命令是否在预批准列表中
2. 如果在 → 直接运行，不确认
3. 如果不在 → 按正常权限流程处理
```

## 约束

- 钩子不能修改项目代码（只做格式化/检查/通知）
- 路径规则只做上下文注入，不修改文件
- 预批准命令限于**无害的只读命令**
- 钩子失败不阻塞主任务（警告即可）
