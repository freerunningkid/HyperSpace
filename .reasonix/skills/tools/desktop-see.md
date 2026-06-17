---
name: desktop-see
description: PowerShell 原生截屏 + ocr.py 识别。Agent 的桌面眼睛，零 MCP 依赖。
last_used: 2026-06-09
---
# desktop-see — Agent 的桌面眼睛

> 截图：PowerShell CopyFromScreen（零依赖） | OCR：ocr.py（多引擎可选）
> 纯 CLI，不经过任何 MCP。

## 使用方法

### 截全屏 → OCR

```powershell
# Step 1: 截屏
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; `$b = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); `$g = [System.Drawing.Graphics]::FromImage(`$b); `$g.CopyFromScreen(0,0,0,0,`$b.Size); `$b.Save('D:\Reasonix\截图\desktop.png'); `$g.Dispose(); `$b.Dispose()"

# Step 2: OCR 识别
python D:\Reasonix\scripts\lib\ocr.py D:\Reasonix\截图\desktop.png
```

### 指定 OCR 引擎

```powershell
# 版式/表格专用
python D:\Reasonix\scripts\lib\ocr.py D:\Reasonix\截图\desktop.png --model paddle

# 高精度
python D:\Reasonix\scripts\lib\ocr.py D:\Reasonix\截图\desktop.png --model ms-vl-235b

# 快速
python D:\Reasonix\scripts\lib\ocr.py D:\Reasonix\截图\desktop.png --model ms-vl-30b
```

## 典型场景

| 场景 | 步骤 |
|------|------|
| 不知道当前屏幕上有什么 | 截屏 → ocr.py 识别 → 读结果 |
| 操作后确认结果 | 截屏 → ocr.py → 对比期望 |
| 抓取无法选中的文字 | 截屏 → ocr.py |

## 注意事项

- PowerShell 截屏是 Windows GDI 原生 API，零第三方依赖
- 不弹窗、不抢焦点、不干扰热键
- OCR 引擎选型：默认竞速模式(gpt-4o+deepseek) / paddle(表格) / ms-vl(高精度)
