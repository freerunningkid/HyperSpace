---
name: playwright-cli
description: 浏览器自动化：导航/点击/填表/截图/表单填写。CLI 模式，比 MCP 省 token。
last_used: 2026-06-09
---
# playwright-cli — 浏览器 CLI 自动化

> 定位：基于 `@playwright/cli` 的浏览器操控技能。
> 比 MCP 版本更省 token（不把大量 tool schema 塞进上下文），适合编码场景。
> 安装方式: `npm install -g @playwright/cli@latest`

## 使用方法

```
playwright-cli open [url]        — 打开浏览器（首次或断连时）
playwright-cli goto <url>        — 导航到 URL
playwright-cli click <target>    — 点击元素（用无障碍快照中的编号）
playwright-cli type <text>       — 输入文本
playwright-cli fill <target> <text> — 填写表单字段
playwright-cli screenshot        — 截图当前页面
playwright-cli snapshot          — 获取无障碍快照（定位元素首选）
playwright-cli close             — 关闭浏览器
playwright-cli evaluate <js>     — 执行 JS
playwright-cli wait <seconds>    — 等待
```

## 典型场景

| 场景 | 步骤 |
|------|------|
| **网页截图** | `open` → `goto url` → `screenshot` → `close` |
| **表单填写** | `open` → `goto url` → `snapshot` 定位 → `fill` → `click submit` → `screenshot` 确认 |
| **数据抓取** | `open` → `goto url` → `evaluate` 提取数据 → `close` |
| **登录流程** | `open` → `goto url` → `fill 账号` → `fill 密码` → `click 登录按钮` → `screenshot` |

## CLI vs MCP 对比

| 维度 | `@playwright/cli` | `@playwright/mcp` |
|------|------------------|-------------------|
| Token 开销 | 低（精简命令） | 高（全量工具 schema） |
| 上下文影响 | 几乎不占 | 每次注入大量定义 |
| 适合场景 | 编程 Agent / 短任务 | 专有 Agent 循环 / 持久连接 |
| 安装 | `npm install -g @playwright/cli` | 已在 reasonix.toml 配置 |

## 注意事项

- 首次使用确保 chromium 已安装: `playwright-cli open` 会自动检测
- `snapshot` 命令比 CSS 选择器定位更可靠（使用无障碍树编号）
- 每个连贯操作建议用 `session` 参数保持同一个浏览器实例: `playwright-cli -s=main goto ...`
