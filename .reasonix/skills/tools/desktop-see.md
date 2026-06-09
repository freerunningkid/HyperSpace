---
name: desktop-see
description: 截图当前屏幕或窗口 → OCR 识别 → 返回屏幕上的文字内容。Agent 的眼睛。
last_used: 2026-06-08
---
# desktop-see — Agent 的桌面眼睛

> 组合工具：截图 (mcp-os-control) + OCR (ocr.py)
> 适用场景：不知道当前屏幕上有什么 → 截图 → OCR → 文字化反馈

## 使用方法

```
run_skill("desktop-see", "region: full | active_window")
```

或者调用已有 MCP 工具：
1. `mcp__os-control__get_screenshot` — 截图获取 base64
2. 将截图传给 `scripts/lib/ocr.py` 做 OCR

## 快速命令

```powershell
# 截全屏 + OCR
python D:\Reasonix\scripts\mcp\os_control_server.py  # via MCP get_screenshot

# OCR 直接调用
python D:\Reasonix\scripts\lib\ocr.py <image_path>
```

## 典型场景

| 场景 | 步骤 |
|------|------|
| 不知道当前打开了什么窗口 | `list_windows` → 确认 → `get_screenshot active_window` → OCR |
| 需要看屏幕上的错误信息 | `get_screenshot full` → OCR → 识别错误文字 |
| 操作完成后确认结果 | `get_screenshot active_window` → OCR → 对比期望 |
