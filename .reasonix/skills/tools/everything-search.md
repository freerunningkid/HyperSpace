---
name: everything-search
description: Everything 极速文件搜索 — 毫秒级全盘搜索，替代 Windows 遍历
last_used: 2026-06-09
---
# everything-search — 文件秒搜

> 基于 Voidtools Everything CLI（`es.exe`）。
> 路径: `D:\软件\Everything\es.exe`
> 首次使用前确保 Everything 桌面程序已运行。

## 用法

```
es.exe [选项] <搜索词>
```

### 常用选项

| 选项 | 用途 |
|------|------|
| (无选项) | 搜索文件名 |
| `-w` | 匹配整个单词 |
| `-r` | 正则表达式 |
| `-n <数量>` | 限制结果数 |
| `-sort` | 排序 |
| `-date-modified` | 按修改日期排序 |

### 示例

```powershell
# 搜文件名
D:\软件\Everything\es.exe "*.xlsx"

# 搜路径+关键词
D:\软件\Everything\es.exe "report 2024 D:\"

# 限制结果数
D:\软件\Everything\es.exe -n 20 "*.md"

# 正则搜索
D:\软件\Everything\es.exe -r ".*evolve.*\.md"
```

## 注意事项

- es.exe 需要 Everything 桌面程序在后台运行（`D:\软件\Everything\Everything.exe`）
- 搜索语法同 Everything 桌面版：支持通配符 `*` `?`，空格分隔多个关键词
- 结果比 Windows 搜索快 100-1000 倍
