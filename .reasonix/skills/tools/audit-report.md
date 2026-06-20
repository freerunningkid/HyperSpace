---
name: audit-report
description: 一键生成项目审计报告：文件统计/配置检查/依赖分析/健康评分 + 审计工作流模板。
last_used: 2026-06-20
---
# audit-report — 项目审计报告生成

> 一键扫描 Reasonix 工作区，生成结构化审计报告。

## 使用方法

```powershell
# 完整审计
python D:\Reasonix\scripts\tools\audit-report.py --full D:\Reasonix

# 仅配置检查
python D:\Reasonix\scripts\tools\audit-report.py --config

# 仅依赖分析
python D:\Reasonix\scripts\tools\audit-report.py --deps

# 输出到文件
python D:\Reasonix\scripts\tools\audit-report.py --full D:\Reasonix > audit-$(Get-Date -Format yyyyMMdd).md
```

## 审计维度

| 维度 | 检查项 | 权重 |
|------|--------|------|
| **配置健康** | reasonix.toml 语法 / MCP 注册 / Skills 索引 | 25% |
| **文件结构** | 孤儿文件 / 大文件 / 未跟踪文件 | 20% |
| **依赖状态** | pip 过期包 / npm 过期包 / 缺失依赖 | 20% |
| **Git 状态** | 未提交变更 / 落后远程 / 大文件历史 | 15% |
| **性能指标** | 启动时间 / 响应延迟 / 缓存命中率 | 20% |

## 评分标准

- **A+ (95-100)**: 优秀，无需优化
- **A (90-94)**: 良好，有小改进空间
- **B+ (85-89)**: 良好，建议关注
- **B (80-84)**: 一般，需要优化
- **C (<80)**: 较差，建议全面重构

## 输出示例

```
=== Reasonix 项目审计报告 ===
生成时间: 2026-06-20 15:30:00
工作区: D:\Reasonix

【配置健康】A+ 98/100
  ✓ reasonix.toml 语法正确
  ✓ MCP 服务器 3/3 正常注册
  ✓ Skills 索引完整 (31/31)

【文件结构】A 88/100
  ⚠ 发现 12 个孤儿文件 (>30天未修改)
  ✗ 发现 1 个超大文件 (>100MB): node_modules/.../claude.exe

【综合评分】A- 91/100
```

## 依赖

```powershell
# 脚本位置: scripts/tools/audit-report.py
# 如不存在，先创建该脚本
```

---

## 审计底稿工作流（财务/项目审计）

> 适用于小金东审计部日常工作的审计底稿生成。

### 底稿整理模板

```
## 审计底稿：<项目名称>
- 审计期间：YYYY-MM-DD ~ YYYY-MM-DD
- 审计对象：<部门/项目/合同>
- 审计类别：<财务/合规/绩效>

### 证据清单
| # | 证据名称 | 来源 | 结论 |
|---|---------|------|------|
| 1 | ... | ... | ... |

### 发现问题
- 问题描述：
- 风险等级：[高/中/低]
- 依据条款：
- 整改建议：
```

### 正式报告模板

```
# 审计报告
**审计单位**：[单位名称] · **报告日期**：[日期]

## 一、审计概况
## 二、审计发现
## 三、审计结论
## 四、整改建议
```
