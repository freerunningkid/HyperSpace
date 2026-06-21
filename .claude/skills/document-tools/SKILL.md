---
name: document-tools
description: 文档处理工具集：读取/提取/处理 PDF、Excel、Word 等文件。截图 OCR 的互补技能
last_used: 2026-06-11
---
# document-tools — 文档处理工具集

> 定位：**子代理（subagent）**
> 灵感：Anthropic 官方文档处理 Skill 包 — 让 AI 直接读取、提取和处理 PDF、Excel、Word 等文件

## 用法

主 Agent 调用：
```
run_skill("document-tools", "<任务描述>")
```

任务描述格式：
```
操作: read / extract / convert
文件: <文件路径>
输出: <期望的输出格式/位置>
```

## 支持的文件类型

| 类型 | 扩展名 | 处理方式 |
|------|--------|---------|
| PDF | .pdf | 文本提取、表格提取、图像 OCR 辅助 |
| Excel | .xlsx .xls | 读取表格、提取数据、公式解释 |
| Word | .docx | 文本提取、格式提取、目录提取 |
| CSV | .csv | 表格读取、数据转换 |
| JSON | .json | 解析、格式化、验证 |
| TXT | .txt .md | 直接读取 |

## 处理流程

### Step 1：识别文件类型

根据扩展名判断文件类型，选择合适的处理方式。

### Step 2：选择处理引擎

| 文件类型 | 工具/命令 |
|---------|----------|
| PDF 文本 | `python -c "import PyPDF2; reader = PyPDF2.PdfReader('file'); ..."` 或 `pdftotext` |
| PDF 表格 | `camelot-py` 或 `tabula-py` |
| Excel | `python -c "import openpyxl; wb = openpyxl.load_workbook('file'); ..."` |
| Word | `python -c "import docx; doc = docx.Document('file'); ..."` |
| CSV | `Import-Csv` (PowerShell) 或 `pandas` |

### Step 3：提取内容

根据操作类型：
- **read** — 全文读取 + 摘要
- **extract** — 提取特定内容（表格、关键字段、特定章节）
- **convert** — 转换为其他格式（CSV→JSON、PDF→TXT 等）

### Step 4：格式化输出

```json
{
  "file": "path/to/file.pdf",
  "type": "pdf",
  "pages": 12,
  "text": "提取的文本摘要...",
  "tables": [
    {"name": "Table 1", "rows": 5, "columns": 3, "data": [...]}
  ],
  "images": 2,
  "metadata": {
    "author": "...",
    "created": "2024-01-15",
    "modified": "2024-06-20"
  }
}
```

## 与 screenshot-ocr 配合

完整的文档处理链路：

```
文档 → document-tools 提取文本
     ↗ 如果文本不可读（扫描件/图片 PDF）
     → screenshot-ocr 做 OCR 识别
     → 合并结果
```

## 适用范围

| 场景 | 示例 |
|------|------|
| 读取报告 | "把这个 PDF 报告读一下，摘要主要内容" |
| 提取数据 | "从这张 Excel 表里提取 Q2 的销售数据" |
| 格式转换 | "把这个 CSV 转成 JSON 格式" |
| 文档对比 | "对比两个版本的 Word 文档，标出差异" |
| 模板填充 | "读取模板 docx，填上数据后另存为新文件" |

## 约束

- **只读不写**（除非明确要求 convert 操作）
- **大文件分页处理** — 超过 50 页的 PDF 按页分组提取
- **不可读内容提示** — 扫描件/图片 PDF 提示用 screenshot-ocr
- **依赖检查** — 运行前检查所需 Python 库是否已安装，缺失则报错
