---
name: screenshot-ocr
description: 截图 OCR：Win+Shift+S/Alt+A 截图 → 自动抓剪贴板 → 保存到 截图/ → 多引擎识别 → 输出结果
last_used: 2026-06-04
---
# screenshot-ocr — 截图即识别

> 剪贴板 → 保存 → 多引擎 OCR → 返回结果
> 运行: inline，用户截图后触发

## 核心原则

**截图后一句话触发，零手动操作。** 用户只管截图（Win+Shift+S / Alt+A），剩下的全自动。

---

## 触发条件

- 用户说"识别一下""OCR""看看这个截图""读一下"
- 用户发来图片后要求提取文字
- 用户说"截图了"但没发图片

---

## 执行流程

### Step 1: 抓取剪贴板

```
python D:\Reasonix\scripts\lib\clipboard_ocr.py --model ms-vl-30b
```

脚本自动：从剪贴板读取图片 → 保存到 `D:\Reasonix\screenshots-截图\screenshot_YYYYMMDD_HHMMSS.png`

如果剪贴板为空 → 提示用户"请先截图（Win+Shift+S 或 Alt+A）"

### Step 2: 引擎选择

**默认引擎: ms-vl-30b** — Qwen3-VL 文本识别最强、3-8s 快速、每日 2000 次免费。

特殊场景手动切换：

| 场景 | 命令 |
|------|------|
| 日常截图文字 | 默认（ms-vl-30b） |
| 复杂文档/表格/合同 | `--model paddle`（PaddleOCR-VL-1.6） |
| 超高精度需求 | `--model ms-vl-235b`（慢但最准） |
| 纯英文/数字 | `--model deepseek-ocr`（最快 1-4s） |

### Step 3: 输出结果

```
📸 截图已保存: D:\Reasonix\screenshots-截图\screenshot_20260603_143021.png

[OCR 结果]
...
```

---

## 反模式

- ❌ 用户说"识别截图"但剪贴板空的 → 先让他截图，不要反复重试
- ❌ 对同一张截图跑两次 OCR → 图片已保存，直接搜 `screenshots-截图/` 目录
- ❌ 用户没说 OCR，不要主动抓剪贴板

## 引擎快速参考

| 引擎 | 速度 | 精度 | 免费 | 适用 |
|------|------|------|------|------|
| ms-vl-30b | 3-8s | 高 | ✅ | **默认首选** |
| ms-vl-235b | 8-20s | 最高 | ✅ | 复杂文档 |
| paddle | 10-30s | 版面 | ✅ | 表格/合同 |
| deepseek-ocr | 1-4s | 中 | ✅ | 纯文字 |
| gpt-4o | 5-15s | 最高 | — | 综合理解 |
